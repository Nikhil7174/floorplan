"""Photo-tier room reconstruction: vanishing points + door-height scale.

COLMAP is skipped on purpose: 2–8 stills usually fail SfM, and it is a
painful clean-machine dependency. Manhattan VPs run on a single strong view.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from floorplan.config import AppConfig
from floorplan.exceptions import EmptyCaptureError
from floorplan.models import Opening, PhotoRoom
from floorplan.reconstruction.scale_recovery import scale_from_door_height
from floorplan.reconstruction.vanishing import (
    LineSegment,
    VanishingFrame,
    assign_vertical,
    detect_segments,
    fit_vanishing_points,
    focal_from_orthogonal_vps,
)

logger = logging.getLogger(__name__)


def load_image(path: Path) -> np.ndarray | None:
    """BGR uint8. HEIC goes through Pillow if OpenCV cannot read it."""

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is not None:
        return image
    try:
        from PIL import Image

        with Image.open(path) as pil:
            rgb = np.array(pil.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except Exception:
        logger.warning("Could not read %s", path)
        return None


def reconstruct_from_bgr(
    image: np.ndarray,
    config: AppConfig,
    label: str = "frame",
) -> tuple[float, np.ndarray, list[list[Opening]], float, str, list[str]] | None:
    """Run the photo recon on an in-memory BGR frame. None if VP/sanity fails."""

    try:
        polygon, openings, ceiling, reason, score, extra = _reconstruct_one(image, config)
    except Exception as exc:
        logger.warning("Photo %s failed: %s", label, exc)
        return None
    if not _sane_room(polygon, ceiling):
        logger.warning("Photo %s produced a degenerate room; skipped", label)
        return None
    return score, polygon, openings, ceiling, reason, extra


def reconstruct_photo_room(
    room: PhotoRoom,
    config: AppConfig,
) -> tuple[np.ndarray, list[list[Opening]], float, str, list[str]]:
    """Return (polygon_xy meters, openings per wall, ceiling_m, scale_reason, warnings)."""

    best: tuple[float, np.ndarray, list[list[Opening]], float, str, list[str]] | None = None
    for image_path in room.images:
        image = load_image(image_path)
        if image is None:
            continue
        result = reconstruct_from_bgr(image, config, label=image_path.name)
        if result is None:
            continue
        if best is None or result[0] > best[0]:
            best = result
    if best is None:
        logger.warning("No Manhattan reconstruction for %s; emitting prior box", room.room_id)
        polygon = _fallback_box(config)
        n = len(polygon)
        return (
            polygon,
            [[] for _ in range(n)],
            config.photos.ceiling_prior_m,
            "fallback_prior",
            ["manhattan_vp_failed"],
        )
    _, polygon, openings, ceiling, reason, extra = best
    return polygon, openings, ceiling, reason, extra


def _reconstruct_one(
    image: np.ndarray,
    config: AppConfig,
) -> tuple[np.ndarray, list[list[Opening]], float, str, float, list[str]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    principal = np.array([w * 0.5, h * 0.5], dtype=np.float64)
    segments = detect_segments(gray, config.photos.line_min_length_px)
    if len(segments) < 8:
        raise EmptyCaptureError("Too few line segments for vanishing points.")
    rng = np.random.default_rng(config.seed)
    fitted = fit_vanishing_points(
        segments,
        rng,
        config.photos.vp_iterations,
        config.photos.vp_inlier_px,
    )
    if len(fitted) < 2:
        raise EmptyCaptureError("Need at least two vanishing points.")
    vps = [item[0] for item in fitted]
    membership = [item[1] for item in fitted]
    while len(vps) < 3:
        # Third axis: a distant VP along the remaining direction.
        vps.append(principal + np.array([0.0, 1e5]))
        membership.append([])
    vertical_i = assign_vertical(vps, segments, membership, principal)
    horiz = [i for i in range(3) if i != vertical_i][:2]
    focal = None
    if len(horiz) == 2:
        focal = focal_from_orthogonal_vps(vps[horiz[0]], vps[horiz[1]], principal)
    if focal is None:
        focal = focal_from_orthogonal_vps(vps[0], vps[1], principal)
    if focal is None:
        focal = float(max(w, h))
    frame = VanishingFrame(
        vps=(vps[0], vps[1], vps[2]),
        vertical_index=vertical_i,
        focal=focal,
        principal=principal,
        inlier_counts=(len(membership[0]), len(membership[1]), len(membership[2])),
        segments=segments,
    )
    polygon_u, floor_d, up, k_inv = _unscaled_floor_polygon(frame, segments, membership, w, h)
    door = _detect_door(segments, frame)
    extra: list[str] = []
    candidates: list[tuple[np.ndarray, list[list[Opening]], float, str, float, list[str]]] = []
    long_v = _longest_vertical(segments, frame)
    if door is not None:
        try:
            unscaled = _vertical_span(door[0], door[1], k_inv, up, floor_d)
            scale = scale_from_door_height(unscaled, config.photos.door_height_m)
            polygon = polygon_u * scale
            ceiling = config.photos.ceiling_prior_m
            note = ["door_detected"]
            if long_v is not None:
                ceil_u = _vertical_span(long_v[0], long_v[1], k_inv, up, floor_d)
                measured = float(ceil_u * scale)
                if 1.8 <= measured <= 4.0:
                    ceiling = measured
                    note.append("ceiling_from_vertical_span")
            openings = _door_openings(door, polygon, config)
            if _sane_room(polygon, ceiling):
                score = float(sum(frame.inlier_counts)) + 50.0
                candidates.append((polygon, openings, ceiling, "door_height_2.032m", score, note))
        except EmptyCaptureError:
            extra.append("door_scale_failed")
    if long_v is not None:
        try:
            unscaled = _vertical_span(long_v[0], long_v[1], k_inv, up, floor_d)
            scale = scale_from_door_height(unscaled, config.photos.ceiling_prior_m)
            polygon = polygon_u * scale
            openings = [[] for _ in range(len(polygon))]
            if _sane_room(polygon, config.photos.ceiling_prior_m):
                score = float(sum(frame.inlier_counts))
                candidates.append(
                    (
                        polygon,
                        openings,
                        config.photos.ceiling_prior_m,
                        "ceiling_prior_no_door",
                        score,
                        ["no_door_or_door_rejected"],
                    )
                )
        except EmptyCaptureError:
            extra.append("ceiling_scale_failed")
    if not candidates:
        raise EmptyCaptureError("No sane metric room from this still.")
    candidates.sort(key=lambda item: item[4], reverse=True)
    return candidates[0]


def _k_inv(focal: float, principal: np.ndarray) -> np.ndarray:
    k = np.array(
        [[focal, 0.0, principal[0]], [0.0, focal, principal[1]], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    return np.linalg.inv(k)


def _unscaled_floor_polygon(
    frame: VanishingFrame,
    segments: list[LineSegment],
    membership: list[list[int]],
    width: int,
    height: int,
) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    k_inv = _k_inv(frame.focal, frame.principal)
    dirs = []
    for vp in frame.vps:
        ray = k_inv @ np.array([vp[0], vp[1], 1.0])
        ray = ray / (np.linalg.norm(ray) + 1e-12)
        dirs.append(ray)
    up = dirs[frame.vertical_index]
    # Floor is below the camera: up · X + d = 0 with d chosen so the plane is in front.
    floor_d = 1.0
    horiz_idx = [i for i in range(3) if i != frame.vertical_index][:2]
    lines_2d: list[np.ndarray] = []
    for hid in horiz_idx:
        family = [segments[i] for i in membership[hid]] or segments
        extremes = _extreme_family_lines(family, frame.vps[hid], height)
        lines_2d.extend(extremes)
    if len(lines_2d) < 4:
        # Image-border fallback quad in the lower 60%.
        lines_2d = _border_quad_lines(width, height)
    corners_img = _intersect_quad(lines_2d[:4])
    corners_3d = []
    for uv in corners_img:
        ray = k_inv @ np.array([uv[0], uv[1], 1.0])
        denom = float(up @ ray)
        if abs(denom) < 1e-8:
            raise EmptyCaptureError("Floor ray parallel to plane.")
        lam = -floor_d / denom
        if lam <= 0:
            lam = abs(lam) + 1e-3
        corners_3d.append(lam * ray)
    pts = np.stack(corners_3d, axis=0)
    e0 = dirs[horiz_idx[0]]
    e1 = np.cross(up, e0)
    e1 = e1 / (np.linalg.norm(e1) + 1e-12)
    e0 = np.cross(e1, up)
    e0 = e0 / (np.linalg.norm(e0) + 1e-12)
    origin = pts.mean(axis=0)
    poly = np.stack([(p - origin) @ e0 for p in pts], axis=0)
    poly = np.stack([poly, [(p - origin) @ e1 for p in pts]], axis=1)
    if _shoelace(poly) < 0:
        poly = poly[::-1]
    return poly, floor_d, up, k_inv


def _extreme_family_lines(
    family: list[LineSegment], vp: np.ndarray, image_h: int
) -> list[np.ndarray]:
    """Two parallel walls sharing a VP: pick the two extremes by signed offset."""

    offsets = []
    lines = []
    for seg in family:
        line = seg.homogeneous()
        line = line / (np.hypot(line[0], line[1]) + 1e-12)
        # Prefer lower-half segments (wall–floor more than wall–ceiling).
        if seg.midpoint[1] < image_h * 0.25:
            continue
        offsets.append(float(line[2]))
        lines.append(line)
    if len(lines) < 2:
        for seg in family:
            line = seg.homogeneous()
            line = line / (np.hypot(line[0], line[1]) + 1e-12)
            offsets.append(float(line[2]))
            lines.append(line)
    if len(lines) < 2:
        return []
    order = np.argsort(offsets)
    return [lines[int(order[0])], lines[int(order[-1])]]


def _border_quad_lines(width: int, height: int) -> list[np.ndarray]:
    y0, y1 = height * 0.55, height * 0.95
    x0, x1 = width * 0.1, width * 0.9
    pts = [
        ((x0, y1), (x1, y1)),
        ((x1, y1), (x1, y0)),
        ((x1, y0), (x0, y0)),
        ((x0, y0), (x0, y1)),
    ]
    out = []
    for (a, b) in pts:
        out.append(np.cross(np.array([a[0], a[1], 1.0]), np.array([b[0], b[1], 1.0])))
    return out


def _intersect_quad(lines: list[np.ndarray]) -> np.ndarray:
    corners = []
    for i in range(4):
        p = np.cross(lines[i], lines[(i + 1) % 4])
        if abs(p[2]) < 1e-10:
            continue
        corners.append(p[:2] / p[2])
    if len(corners) < 4:
        raise EmptyCaptureError("Could not intersect a floor quad from vanishing lines.")
    pts = np.stack(corners, axis=0)
    if abs(_shoelace(pts)) < 1e-3:
        raise EmptyCaptureError("Floor quad is degenerate.")
    return pts


def _sane_room(polygon: np.ndarray, ceiling_m: float) -> bool:
    """Reject slivers and non-physical heights. Why: a tight wrong number is a scored miss."""

    if polygon.shape[0] < 3:
        return False
    edges = [
        float(np.linalg.norm(polygon[(i + 1) % len(polygon)] - polygon[i]))
        for i in range(len(polygon))
    ]
    area = abs(_shoelace(polygon))
    if min(edges) < 0.6 or max(edges) > 18.0:
        return False
    if area < 2.0 or area > 80.0:
        return False
    if min(edges) / max(edges) < 0.2:
        return False
    if not (1.7 <= ceiling_m <= 4.2):
        return False
    return True


def _detect_door(segments: list[LineSegment], frame: VanishingFrame) -> tuple[np.ndarray, np.ndarray] | None:
    """Pair of near-vertical segments with a plausible door aspect."""

    vertical_vp = frame.vps[frame.vertical_index]
    verticals = []
    for seg in segments:
        if _points_at_vp(seg, vertical_vp, 8.0) or _is_image_vertical(seg):
            if seg.length >= 40:
                verticals.append(seg)
    best = None
    best_score = 0.0
    for i, a in enumerate(verticals):
        for b in verticals[i + 1 :]:
            gap = abs(float(a.midpoint[0] - b.midpoint[0]))
            if gap < 20 or gap > 220:
                continue
            ha = a.length
            hb = b.length
            if min(ha, hb) / max(ha, hb) < 0.55:
                continue
            height = 0.5 * (ha + hb)
            if height / gap < 1.6 or height / gap > 4.5:
                continue
            top = min(a.y1, a.y2, b.y1, b.y2)
            bot = max(a.y1, a.y2, b.y1, b.y2)
            score = height
            if score > best_score:
                best_score = score
                mid_x = 0.5 * (a.midpoint[0] + b.midpoint[0])
                best = (np.array([mid_x, bot]), np.array([mid_x, top]))
    return best


def _longest_vertical(
    segments: list[LineSegment], frame: VanishingFrame
) -> tuple[np.ndarray, np.ndarray] | None:
    vertical_vp = frame.vps[frame.vertical_index]
    best = None
    best_len = 0.0
    for seg in segments:
        if not (_points_at_vp(seg, vertical_vp, 10.0) or _is_image_vertical(seg)):
            continue
        if seg.length > best_len:
            best_len = seg.length
            y_lo = max(seg.y1, seg.y2)
            y_hi = min(seg.y1, seg.y2)
            x = 0.5 * (seg.x1 + seg.x2)
            best = (np.array([x, y_lo]), np.array([x, y_hi]))
    return best


def _vertical_span(
    bottom: np.ndarray,
    top: np.ndarray,
    k_inv: np.ndarray,
    up: np.ndarray,
    floor_d: float,
) -> float:
    ray_b = k_inv @ np.array([bottom[0], bottom[1], 1.0])
    ray_t = k_inv @ np.array([top[0], top[1], 1.0])
    denom = float(up @ ray_b)
    if abs(denom) < 1e-8:
        raise EmptyCaptureError("Door bottom ray is parallel to the floor.")
    lam_b = -floor_d / denom
    p_b = lam_b * ray_b
    matrix = np.stack([up, -ray_t], axis=1)
    try:
        ts = np.linalg.lstsq(matrix, -p_b, rcond=None)[0]
    except np.linalg.LinAlgError as exc:
        raise EmptyCaptureError("Could not intersect door top ray with the vertical.") from exc
    return abs(float(ts[0]))


def _door_openings(
    door: tuple[np.ndarray, np.ndarray],
    polygon: np.ndarray,
    config: AppConfig,
) -> list[list[Opening]]:
    """Put the detected door on the longest wall as a wide-interval opening."""

    from floorplan.confidence.scoring import interval_calibrated
    from floorplan.models import Opening

    _ = door
    width = 0.9
    openings: list[list[Opening]] = [[] for _ in range(len(polygon))]
    # Place at the midpoint of the longest wall — honest unknown position, known-ish width.
    lengths = [float(np.linalg.norm(polygon[(i + 1) % len(polygon)] - polygon[i])) for i in range(len(polygon))]
    wall_i = int(np.argmax(lengths))
    length = lengths[wall_i]
    t0 = max(0.1, 0.5 * length - 0.45)
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


def _points_at_vp(seg: LineSegment, vp: np.ndarray, tol_px: float) -> bool:
    from floorplan.reconstruction.vanishing import _point_line_distance

    return _point_line_distance(vp, seg) <= tol_px


def _is_image_vertical(seg: LineSegment, min_ratio: float = 3.0) -> bool:
    dx = abs(seg.x2 - seg.x1)
    dy = abs(seg.y2 - seg.y1)
    return dy >= min_ratio * max(dx, 1.0)


def _fallback_box(config: AppConfig) -> np.ndarray:
    w = config.photos.fallback_width_m
    d = config.photos.fallback_depth_m
    return np.array([[0.0, 0.0], [w, 0.0], [w, d], [0.0, d]], dtype=np.float64)


def _shoelace(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
