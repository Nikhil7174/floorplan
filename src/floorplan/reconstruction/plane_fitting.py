"""Seeded RANSAC planes and floor/wall/ceiling classification."""

from __future__ import annotations

import logging

import numpy as np

from floorplan.config import AppConfig
from floorplan.exceptions import NoFloorPlaneError
from floorplan.models import Plane, PlaneSet, PointCloud

logger = logging.getLogger(__name__)


def fit_plane_ransac(
    points: np.ndarray,
    residual_m: float,
    iterations: int,
    rng: np.random.Generator,
    min_inliers: int,
    normal_hint: np.ndarray | None = None,
    align_min: float = 0.0,
    vertical_to: np.ndarray | None = None,
    vertical_max_align: float = 0.45,
) -> Plane | None:
    """Fit one plane. Why: a seeded sampler makes the repeatability gate testable."""

    if len(points) < 3:
        return None
    best_count = 0
    best_inliers: np.ndarray | None = None
    n_pts = len(points)
    for _ in range(iterations):
        idx = rng.choice(n_pts, size=3, replace=False)
        p0, p1, p2 = points[idx]
        normal = np.cross(p1 - p0, p2 - p0)
        norm = float(np.linalg.norm(normal))
        if norm < 1e-8:
            continue
        normal = normal / norm
        if normal_hint is not None and abs(float(normal @ normal_hint)) < align_min:
            continue
        if vertical_to is not None and abs(float(normal @ vertical_to)) > vertical_max_align:
            continue
        offset = -float(normal @ p0)
        dist = np.abs(points @ normal + offset)
        inliers = dist < residual_m
        count = int(inliers.sum())
        if count > best_count:
            best_count = count
            best_inliers = inliers
    if best_inliers is None or best_count < min_inliers:
        return None
    return _refit(points, best_inliers)


def extract_planes(cloud: PointCloud, config: AppConfig) -> list[Plane]:
    """Peel dominant planes off the cloud until leftover mass is too small."""

    rng = np.random.default_rng(config.seed)
    remaining = cloud.xyz
    planes: list[Plane] = []
    min_inliers = config.ransac.min_inliers
    for _ in range(config.ransac.max_planes):
        if len(remaining) < min_inliers:
            break
        plane = fit_plane_ransac(
            remaining,
            residual_m=config.ransac.residual_m,
            iterations=config.ransac.iterations,
            rng=rng,
            min_inliers=min_inliers,
        )
        if plane is None:
            break
        planes.append(plane)
        dist = np.abs(remaining @ plane.normal + plane.offset)
        remaining = remaining[dist >= config.ransac.residual_m]
    logger.info("Extracted %d raw planes", len(planes))
    return planes


def classify_planes(
    planes: list[Plane],
    camera_origins: np.ndarray,
    config: AppConfig,
) -> PlaneSet:
    """Label floor, optional ceiling, and walls. Missing ceiling is allowed."""

    if not planes:
        raise NoFloorPlaneError("RANSAC returned no planes.")
    up = _infer_up(planes, camera_origins)
    labeled: list[Plane] = []
    for plane in planes:
        align = abs(float(plane.normal @ up))
        kind: str
        if align >= config.planes.horizontal_align:
            kind = "unknown"
        elif align <= config.planes.vertical_align:
            kind = "wall"
        else:
            kind = "unknown"
        labeled.append(_with_kind(plane, kind))

    horizontals = [p for p in labeled if abs(float(p.normal @ up)) >= config.planes.horizontal_align]
    if not horizontals:
        raise NoFloorPlaneError("No near-horizontal plane for a floor.")

    cam = camera_origins.mean(axis=0)
    floor = min(horizontals, key=lambda p: _signed_height(p, cam, up))
    # Floor normal should point toward the cameras (up).
    floor = _orient_toward(floor, cam)
    floor = _with_kind(floor, "floor")

    ceiling: Plane | None = None
    unused: list[Plane] = []
    for plane in horizontals:
        if plane is floor or (
            plane.inlier_count == floor.inlier_count and np.allclose(plane.offset, floor.offset)
        ):
            continue
        oriented = _orient_toward(plane, cam)
        height = _plane_separation(floor, oriented, up)
        if config.planes.min_ceiling_height_m <= height <= config.planes.max_ceiling_height_m:
            if ceiling is None or oriented.inlier_count > ceiling.inlier_count:
                ceiling = _with_kind(oriented, "ceiling")
        else:
            unused.append(plane)

    walls = [p for p in labeled if p.kind == "wall"]
    walls = _merge_walls(walls, config)
    if config.planes.manhattan_snap and walls:
        walls = _manhattan_snap(walls, up)
    leftover = [p for p in labeled if p.kind == "unknown" and p is not floor]
    if len(walls) < 2:
        promoted: list[Plane] = []
        still_unused: list[Plane] = []
        for plane in leftover + unused:
            if abs(float(plane.normal @ up)) < 0.65:
                promoted.append(_with_kind(plane, "wall"))
            else:
                still_unused.append(plane)
        if promoted:
            walls = _merge_walls(walls + promoted, config)
            leftover = still_unused
            unused = []
            logger.info("Promoted %d mid-tilt planes to walls", len(promoted))
    unused.extend(leftover)
    logger.info(
        "Classified floor=%d inliers, ceiling=%s, walls=%d",
        floor.inlier_count,
        "yes" if ceiling else "no",
        len(walls),
    )
    return PlaneSet(floor=floor, ceiling=ceiling, walls=walls, up=up, unused=unused)


def recover_vertical_walls(
    xyz: np.ndarray,
    planes: PlaneSet,
    config: AppConfig,
) -> PlaneSet:
    """Second RANSAC pass constrained to near-vertical planes.

    Why: unconstrained peel eats floor, ceiling, and tabletops first; walls lose.
    """

    remaining = xyz
    exclude = [planes.floor]
    if planes.ceiling is not None:
        exclude.append(planes.ceiling)
    for plane in exclude:
        dist = np.abs(remaining @ plane.normal + plane.offset)
        remaining = remaining[dist >= config.ransac.residual_m * 1.5]
    rng = np.random.default_rng(config.seed + 1)
    found: list[Plane] = list(planes.walls)
    min_inliers = max(150, config.ransac.min_inliers // 2)
    for _ in range(6):
        if len(remaining) < min_inliers:
            break
        plane = fit_plane_ransac(
            remaining,
            residual_m=config.ransac.residual_m,
            iterations=config.ransac.iterations,
            rng=rng,
            min_inliers=min_inliers,
            vertical_to=planes.up,
            vertical_max_align=config.planes.vertical_align,
        )
        if plane is None:
            break
        found.append(_with_kind(plane, "wall"))
        dist = np.abs(remaining @ plane.normal + plane.offset)
        remaining = remaining[dist >= config.ransac.residual_m]
    walls = _merge_walls(found, config)
    if config.planes.manhattan_snap and walls:
        walls = _manhattan_snap(walls, planes.up)
    logger.info("Vertical pass: %d walls", len(walls))
    return PlaneSet(
        floor=planes.floor,
        ceiling=planes.ceiling,
        walls=walls,
        up=planes.up,
        unused=planes.unused,
    )


def camera_origins_from_cloud_fallback(xyz: np.ndarray) -> np.ndarray:
    """When poses are unavailable, use the cloud centroid as a camera proxy."""

    return xyz.mean(axis=0, keepdims=True)


def _refit(points: np.ndarray, inliers: np.ndarray) -> Plane:
    subset = points[inliers]
    centroid = subset.mean(axis=0)
    centered = subset - centroid
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = vh[-1]
    normal = normal / np.linalg.norm(normal)
    offset = -float(normal @ centroid)
    residual = subset @ normal + offset
    rmse = float(np.sqrt(np.mean(residual**2)))
    return Plane(
        normal=normal.astype(np.float64),
        offset=offset,
        inlier_count=int(len(subset)),
        rmse=rmse,
        inlier_points=subset,
    )


def _with_kind(plane: Plane, kind: str) -> Plane:
    return Plane(
        normal=plane.normal,
        offset=plane.offset,
        inlier_count=plane.inlier_count,
        rmse=plane.rmse,
        inlier_points=plane.inlier_points,
        kind=kind,  # type: ignore[arg-type]
    )


def _infer_up(planes: list[Plane], camera_origins: np.ndarray) -> np.ndarray:
    axes = [
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
    ]
    cam = camera_origins.mean(axis=0)
    best_up = np.array([0.0, 1.0, 0.0])
    best_score = -1.0
    for axis in axes:
        for plane in planes:
            align = abs(float(plane.normal @ axis))
            if align < 0.85:
                continue
            height = float(plane.normal @ cam + plane.offset)
            n = plane.normal if height >= 0 else -plane.normal
            score = plane.inlier_count * align
            if 0.3 < abs(height) < 2.8:
                score *= 2.0
            if score > best_score:
                best_score = score
                best_up = n / np.linalg.norm(n)
    return best_up


def _signed_height(plane: Plane, point: np.ndarray, up: np.ndarray) -> float:
    n = plane.normal if float(plane.normal @ up) >= 0 else -plane.normal
    off = plane.offset if float(plane.normal @ up) >= 0 else -plane.offset
    return float(n @ point + off)


def _orient_toward(plane: Plane, point: np.ndarray) -> Plane:
    if float(plane.normal @ point + plane.offset) >= 0:
        return plane
    return Plane(
        normal=-plane.normal,
        offset=-plane.offset,
        inlier_count=plane.inlier_count,
        rmse=plane.rmse,
        inlier_points=plane.inlier_points,
        kind=plane.kind,
    )


def _plane_separation(floor: Plane, other: Plane, up: np.ndarray) -> float:
    origin = -floor.offset * floor.normal
    return abs(float(other.normal @ origin + other.offset))


def _merge_walls(walls: list[Plane], config: AppConfig) -> list[Plane]:
    if not walls:
        return []
    used = [False] * len(walls)
    merged: list[Plane] = []
    angle_tol = np.deg2rad(config.planes.wall_merge_angle_deg)
    offset_tol = config.planes.wall_merge_offset_m
    for i, wall in enumerate(walls):
        if used[i]:
            continue
        group = [wall]
        used[i] = True
        for j, other in enumerate(walls):
            if used[j]:
                continue
            dot = abs(float(np.clip(wall.normal @ other.normal, -1.0, 1.0)))
            angle = np.arccos(dot)
            same_offset = _offset_gap(wall, other) < offset_tol
            if angle <= angle_tol and same_offset:
                group.append(other)
                used[j] = True
        pts = np.concatenate([g.inlier_points for g in group], axis=0)
        inliers = np.ones(len(pts), dtype=bool)
        merged.append(_with_kind(_refit(pts, inliers), "wall"))
    merged.sort(key=lambda p: p.inlier_count, reverse=True)
    return merged


def _offset_gap(a: Plane, b: Plane) -> float:
    if float(a.normal @ b.normal) >= 0:
        return abs(a.offset - b.offset)
    return abs(a.offset + b.offset)


def _manhattan_snap(walls: list[Plane], up: np.ndarray) -> list[Plane]:
    """Snap wall normals to a 90-degree pair in the floor plane. Why: indoor rooms are Manhattan."""

    dominant = walls[0].normal - (walls[0].normal @ up) * up
    if np.linalg.norm(dominant) < 1e-8:
        dominant = walls[0].normal
    dominant = dominant / np.linalg.norm(dominant)
    snapped: list[Plane] = []
    for wall in walls:
        n = wall.normal - (wall.normal @ up) * up
        if np.linalg.norm(n) < 1e-8:
            n = wall.normal
        n = n / np.linalg.norm(n)
        if abs(float(n @ dominant)) >= 0.5:
            target = dominant if float(n @ dominant) >= 0 else -dominant
        else:
            target = np.cross(up, dominant)
            target = target / (np.linalg.norm(target) + 1e-12)
            if float(n @ target) < 0:
                target = -target
        # Keep the original offset by projecting the centroid onto the snapped plane.
        centroid = wall.inlier_points.mean(axis=0)
        offset = -float(target @ centroid)
        snapped.append(
            Plane(
                normal=target,
                offset=offset,
                inlier_count=wall.inlier_count,
                rmse=wall.rmse,
                inlier_points=wall.inlier_points,
                kind="wall",
            )
        )
    return snapped
