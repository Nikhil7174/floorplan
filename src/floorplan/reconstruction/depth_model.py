"""Monocular depth → metric PointCloud → the existing RANSAC room.

Depth Anything V2 gives relative depth (affine-ambiguous). We fit scale+shift
from two known lengths in frame — door height and door width — then hand the
cloud to plane_fitting unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np
from floorplan.config import AppConfig
from floorplan.exceptions import EmptyCaptureError
from floorplan.models import Opening, PointCloud
from floorplan.reconstruction.plane_fitting import (
    classify_planes,
    extract_planes,
    recover_vertical_walls,
)
from floorplan.reconstruction.room import polygon_from_planes
from floorplan.reconstruction.vanishing import detect_segments

logger = logging.getLogger(__name__)

_PIPE = None


@dataclass
class DoorPixels:
    top: np.ndarray
    bottom: np.ndarray
    left: np.ndarray
    right: np.ndarray


def infer_relative_depth(image_bgr: np.ndarray, config: AppConfig) -> np.ndarray:
    """HxW float32 relative depth, resized to the input image."""

    from PIL import Image

    pipe = _depth_pipeline(config.photos.depth_model_id)
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    out = pipe(Image.fromarray(rgb))
    pred = out.get("predicted_depth")
    if pred is None:
        depth_img = out.get("depth")
        if depth_img is None:
            raise EmptyCaptureError("Depth pipeline returned neither predicted_depth nor depth.")
        arr = np.asarray(depth_img, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr.mean(axis=2)
    else:
        arr = np.asarray(pred, dtype=np.float32)
        if hasattr(pred, "detach"):
            arr = pred.detach().cpu().numpy().astype(np.float32)
    if arr.ndim != 2:
        raise EmptyCaptureError(f"Unexpected depth shape {arr.shape}")
    h, w = image_bgr.shape[:2]
    if arr.shape != (h, w):
        arr = cv2.resize(arr, (w, h), interpolation=cv2.INTER_LINEAR)
    return arr


def reconstruct_from_depth(
    image_bgr: np.ndarray,
    config: AppConfig,
    label: str = "frame",
) -> tuple[float, np.ndarray, list[list[Opening]], float, str, list[str]] | None:
    """One still → (score, polygon, openings, ceiling, reason, warnings) or None."""

    try:
        depth = infer_relative_depth(image_bgr, config)
    except Exception as exc:
        logger.warning("Depth inference failed on %s: %s", label, exc)
        return None
    if not sane_depth_map(depth):
        logger.warning("Photo %s depth map is not a 3D scene; skipped", label)
        return None
    door = detect_door_pixels(image_bgr, config)
    try:
        xyz, reason, extra = metric_cloud(depth, door, config)
    except Exception as exc:
        logger.warning("Depth affine/backproject failed on %s: %s", label, exc)
        return None
    extra = list(extra)
    extra.append("depth_anything_v2")
    cloud = PointCloud(xyz=xyz)
    photo_cfg = _photo_ransac_config(config)
    try:
        planes_raw = extract_planes(cloud, photo_cfg)
        origins = np.zeros((1, 3), dtype=np.float64)
        planes = classify_planes(planes_raw, origins, photo_cfg)
        if len(planes.walls) < 3:
            planes = recover_vertical_walls(cloud.xyz, planes, photo_cfg)
        polygon = polygon_from_planes(planes)
    except Exception as exc:
        logger.warning("Depth plane fit failed on %s: %s", label, exc)
        return None
    if not sane_plane_layout(planes):
        logger.warning("Photo %s planes are not a room (floor/walls); skipped", label)
        return None
    if len(polygon) < 3:
        logger.warning("Depth recon on %s produced no closed polygon", label)
        return None
    if planes.ceiling is not None:
        origin = -planes.floor.offset * planes.floor.normal
        ceiling = abs(float(planes.ceiling.normal @ origin + planes.ceiling.offset))
    else:
        ceiling = config.photos.ceiling_prior_m
        extra.append("no_ceiling_from_depth")
    openings = _placeholder_door(polygon, config) if door is not None else [[] for _ in range(len(polygon))]
    score = planes.floor.inlier_count / 100.0 + sum(w.inlier_count for w in planes.walls) / 100.0
    if door is not None:
        score += 50.0
    logger.info(
        "Depth recon %s: reason=%s walls=%d area≈%.2f ceil=%.2f",
        label,
        reason,
        len(polygon),
        abs(_shoelace(polygon)),
        ceiling,
    )
    return score, polygon, openings, ceiling, reason, extra


def metric_cloud(
    depth: np.ndarray,
    door: DoorPixels | None,
    config: AppConfig,
) -> tuple[np.ndarray, str, list[str]]:
    """Back-project with Z = a * d + b. Door height+width is the two-length fit."""

    h, w = depth.shape
    fx, fy, cx, cy = _intrinsics(w, h)
    extra: list[str] = []
    if door is not None:
        a, b, ok = fit_affine_door(depth, door, config, fx, fy, cx, cy)
        if ok:
            extra.append("depth_affine_door")
            reason = "door_height_2.032m"
        else:
            extra.append("depth_affine_door_failed")
            a, b = _affine_from_priors(depth, config, fx, fy, cx, cy)
            reason = "ceiling_prior_no_door"
            extra.append("depth_affine_prior")
    else:
        a, b = _affine_from_priors(depth, config, fx, fy, cx, cy)
        reason = "ceiling_prior_no_door"
        extra.append("depth_affine_prior")
        extra.append("no_door_or_door_rejected")
    xyz = backproject_depth(depth, a, b, config)
    if len(xyz) < 200:
        raise EmptyCaptureError("Back-projected cloud is too thin.")
    return xyz, reason, extra


def fit_affine_door(
    depth: np.ndarray,
    door: DoorPixels,
    config: AppConfig,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
) -> tuple[float, float, bool]:
    """Closed-form Z = a*d + b from two depth anchors.

    Door height+width are the same plane (one Z). The second anchor is the
    floor band at camera-height (different d). That is what separates a,b.
    """

    d_door = float(
        np.median(
            [
                _sample_depth(depth, door.top),
                _sample_depth(depth, door.bottom),
            ]
        )
    )
    pixel_h = abs(float(door.bottom[1] - door.top[1]))
    if pixel_h < 8:
        return 1.0, 0.0, False
    z_door = config.photos.door_height_m * fy / pixel_h
    us_f, vs_f, ds_f = _floor_band(depth)
    if ds_f.size < 8:
        return 1.0, 0.0, False
    d_floor = float(np.median(ds_f))
    v_floor = float(np.median(vs_f))
    denom = (v_floor - cy) / fy
    if abs(denom) < 0.05:
        return 1.0, 0.0, False
    z_floor = config.photos.camera_height_prior_m / denom
    if abs(d_door - d_floor) < 0.02 * max(abs(d_door), abs(d_floor), 1.0):
        logger.info("Depth affine: door and floor d too close (%.3f vs %.3f)", d_door, d_floor)
        return 1.0, 0.0, False
    if z_door <= 0.2 or z_floor <= 0.2:
        return 1.0, 0.0, False
    a = (z_door - z_floor) / (d_door - d_floor)
    b = z_door - a * d_door
    ok = (a * d_door + b) > 0.05 and (a * d_floor + b) > 0.05 and np.isfinite([a, b]).all()
    logger.info(
        "Depth affine two-anchor: a=%.4f b=%.4f z_door=%.2f z_floor=%.2f d_door=%.3f d_floor=%.3f ok=%s",
        a,
        b,
        z_door,
        z_floor,
        d_door,
        d_floor,
        ok,
    )
    return float(a), float(b), bool(ok)


def sane_depth_map(depth: np.ndarray) -> bool:
    """Reject near-uniform or single-plane depth (cards, screenshots, logos)."""

    finite = np.isfinite(depth)
    if int(finite.sum()) < 400:
        logger.info("sane_depth reject: too few finite pixels")
        return False
    d = depth[finite]
    med = float(np.median(d))
    if med <= 1e-6:
        return False
    spread = float(np.percentile(d, 90) - np.percentile(d, 10))
    if spread / med < 0.12:
        logger.info("sane_depth reject: flat spread=%.3f med=%.3f", spread, med)
        return False
    ys, xs = np.nonzero(finite)
    pts = np.stack([xs.astype(np.float64), ys.astype(np.float64), d.astype(np.float64)], axis=1)
    rng = np.random.default_rng(0)
    take = min(2500, len(pts))
    sample = pts[rng.choice(len(pts), size=take, replace=False)]
    centered = sample - sample.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    resid = np.abs(centered @ vh[-1])
    rmse = float(np.sqrt(np.mean(resid**2)))
    scale = float(np.linalg.norm(np.std(sample, axis=0))) + 1e-6
    if rmse / scale < 0.0012:
        logger.info("sane_depth reject: planar rmse/scale=%.4f", rmse / scale)
        return False
    return True


def sane_plane_layout(planes) -> bool:
    """Floor near-horizontal, ≥2 walls near-vertical, walls not all parallel."""

    up = planes.up
    if abs(float(planes.floor.normal @ up)) < 0.80:
        logger.info("sane_planes reject: floor not horizontal")
        return False
    walls = planes.walls
    if len(walls) < 2:
        logger.info("sane_planes reject: wall_count=%d", len(walls))
        return False
    upright = [w for w in walls if abs(float(w.normal @ up)) <= 0.50]
    if len(upright) < 2:
        logger.info("sane_planes reject: upright_walls=%d", len(upright))
        return False
    best = 0.0
    for i, a in enumerate(upright):
        na = a.normal - (a.normal @ up) * up
        if np.linalg.norm(na) < 1e-8:
            continue
        na = na / np.linalg.norm(na)
        for b in upright[i + 1 :]:
            nb = b.normal - (b.normal @ up) * up
            if np.linalg.norm(nb) < 1e-8:
                continue
            nb = nb / np.linalg.norm(nb)
            ang = float(np.degrees(np.arccos(np.clip(abs(float(na @ nb)), 0.0, 1.0))))
            best = max(best, ang)
    if best < 40.0:
        logger.info("sane_planes reject: max_wall_angle=%.1f", best)
        return False
    return True


def backproject_depth(
    depth: np.ndarray,
    scale: float,
    shift: float,
    config: AppConfig,
) -> np.ndarray:
    """Camera-frame XYZ, Y down, Z forward. Strided, Z-clipped, voxel-thinned."""

    h, w = depth.shape
    fx, fy, cx, cy = _intrinsics(w, h)
    stride = max(int(config.photos.depth_stride), 1)
    vs, us = np.mgrid[0:h:stride, 0:w:stride]
    d = depth[::stride, ::stride]
    z = scale * d + shift
    min_z = config.photos.depth_min_z_m
    max_z = config.photos.depth_max_z_m
    valid = np.isfinite(z) & (z > min_z) & (z < max_z)
    x = (us - cx) / fx * z
    y = (vs - cy) / fy * z
    xyz = np.stack([x, y, z], axis=-1)[valid].reshape(-1, 3).astype(np.float64)
    voxel = config.photos.depth_voxel_m
    if voxel > 0 and len(xyz) > 0:
        xyz = _voxel_downsample(xyz, voxel)
    return xyz


def detect_door_pixels(image_bgr: np.ndarray, config: AppConfig) -> DoorPixels | None:
    """Image-vertical segment pair with a door aspect. No vanishing points."""

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    min_len = max(float(config.photos.line_min_length_px), config.photos.line_min_length_frac * max(gray.shape))
    segs = detect_segments(gray, min_len)
    verticals = []
    for seg in segs:
        if seg.length < 40:
            continue
        if abs(seg.x2 - seg.x1) / max(seg.length, 1.0) > 0.25:
            continue
        verticals.append(seg)
    best = None
    best_score = 0.0
    for i, a in enumerate(verticals):
        for b in verticals[i + 1 :]:
            gap = abs(float(a.midpoint[0] - b.midpoint[0]))
            if gap < 20 or gap > 220:
                continue
            ha, hb = a.length, b.length
            if min(ha, hb) / max(ha, hb) < 0.55:
                continue
            height = 0.5 * (ha + hb)
            if height / gap < 1.6 or height / gap > 4.5:
                continue
            top = min(a.y1, a.y2, b.y1, b.y2)
            bot = max(a.y1, a.y2, b.y1, b.y2)
            if height > best_score:
                best_score = height
                left = a if a.midpoint[0] < b.midpoint[0] else b
                right = b if left is a else a
                mid_x = 0.5 * (left.midpoint[0] + right.midpoint[0])
                mid_y = 0.5 * (top + bot)
                best = DoorPixels(
                    top=np.array([mid_x, top], dtype=np.float64),
                    bottom=np.array([mid_x, bot], dtype=np.float64),
                    left=np.array([left.midpoint[0], mid_y], dtype=np.float64),
                    right=np.array([right.midpoint[0], mid_y], dtype=np.float64),
                )
    return best


def _affine_from_priors(
    depth: np.ndarray,
    config: AppConfig,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
) -> tuple[float, float]:
    """Level-camera linear solve: camera height + ceiling prior as the two lengths."""

    h, w = depth.shape
    v_floor = int(h * 0.92)
    v_ceil = int(h * 0.08)
    u = int(w * 0.50)
    d_f = _sample_depth(depth, np.array([u, v_floor], dtype=np.float64))
    d_c = _sample_depth(depth, np.array([u, v_ceil], dtype=np.float64))
    h_cam = config.photos.camera_height_prior_m
    h_ceil = config.photos.ceiling_prior_m
    # Y-down: floor Y = +h_cam, ceiling Y = h_cam - h_ceil
    row0 = np.array([(v_floor - cy) / fy * d_f, (v_floor - cy) / fy])
    row1 = np.array([(v_ceil - cy) / fy * d_c, (v_ceil - cy) / fy])
    rhs = np.array([h_cam, h_cam - h_ceil])
    try:
        a, b = np.linalg.lstsq(np.stack([row0, row1]), rhs, rcond=None)[0]
    except np.linalg.LinAlgError:
        a, b = 3.0 / max(float(np.median(depth)), 1e-3), 0.0
    z_f = a * d_f + b
    z_c = a * d_c + b
    if min(z_f, z_c) <= 0.05 or not np.isfinite([a, b]).all():
        a, b = 3.0 / max(float(np.median(depth)), 1e-3), 0.0
    return float(a), float(b)


def _intrinsics(width: int, height: int) -> tuple[float, float, float, float]:
    focal = float(max(width, height))
    return focal, focal, width * 0.5, height * 0.5


def _floor_band(depth: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pixels in the lower-middle of the frame — expected floor, different d from a door."""

    h, w = depth.shape
    vs, us = np.mgrid[int(h * 0.86) : h : 4, int(w * 0.22) : int(w * 0.78) : 4]
    ds = depth[vs, us]
    ok = np.isfinite(ds)
    return us[ok].astype(np.float64), vs[ok].astype(np.float64), ds[ok].astype(np.float64)


def _sample_depth(depth: np.ndarray, uv: np.ndarray, radius: int = 2) -> float:
    u = int(np.clip(round(float(uv[0])), 0, depth.shape[1] - 1))
    v = int(np.clip(round(float(uv[1])), 0, depth.shape[0] - 1))
    patch = depth[max(0, v - radius) : v + radius + 1, max(0, u - radius) : u + radius + 1]
    return float(np.median(patch))


def _voxel_downsample(xyz: np.ndarray, voxel: float) -> np.ndarray:
    keys = np.floor(xyz / voxel).astype(np.int64)
    _, idx = np.unique(keys, axis=0, return_index=True)
    return xyz[idx]


def _photo_ransac_config(config: AppConfig) -> AppConfig:
    return config.model_copy(
        update={
            "ransac": config.ransac.model_copy(
                update={
                    "residual_m": config.photos.depth_residual_m,
                    "min_inliers": config.photos.depth_min_inliers,
                }
            )
        }
    )


def _depth_pipeline(model_id: str):
    global _PIPE
    if _PIPE is not None:
        return _PIPE
    import torch
    from transformers import pipeline

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = 0
    else:
        device = -1
    logger.info("Loading depth model %s on %s", model_id, device)
    _PIPE = pipeline("depth-estimation", model=model_id, device=device)
    return _PIPE


def _placeholder_door(polygon: np.ndarray, config: AppConfig) -> list[list[Opening]]:
    from floorplan.confidence.scoring import interval_calibrated

    width = config.photos.door_width_m
    openings: list[list[Opening]] = [[] for _ in range(len(polygon))]
    lengths = [float(np.linalg.norm(polygon[(i + 1) % len(polygon)] - polygon[i])) for i in range(len(polygon))]
    wall_i = int(np.argmax(lengths))
    length = lengths[wall_i]
    t0 = max(0.1, 0.5 * length - 0.5 * width)
    t1 = min(length - 0.1, t0 + width)
    openings[wall_i].append(
        Opening(
            kind="door",
            width_m=interval_calibrated(t1 - t0, config.photos.door_scale_frac, "m", "door_height_scale"),
            t0_m=t0,
            t1_m=t1,
        )
    )
    return openings


def _shoelace(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
