"""Turn classified planes into a closed room polygon with openings."""

from __future__ import annotations

import logging

import numpy as np

from floorplan.confidence.scoring import (
    interval_calibrated,
    interval_from_evidence,
    missing_ceiling_interval,
)
from floorplan.config import AppConfig
from floorplan.exceptions import InsufficientPlanesError
from floorplan.models import Opening, OpeningKind, Plane, PlaneSet, RoomGeometry, Wall

logger = logging.getLogger(__name__)


def build_room(
    planes: PlaneSet,
    config: AppConfig,
    room_id: str,
    tier: str = "lidar",
) -> RoomGeometry:
    """Intersect walls on the floor plane and attach per-wall openings.

    Why: downstream stitching and the JSON schema both consume RoomGeometry.
    """

    basis = _floor_basis(planes.up)
    polygon = _oriented_bounds(planes, basis)
    if len(polygon) < 3:
        raise InsufficientPlanesError("Could not form a closed room polygon from wall extents.")

    warnings: list[str] = ["manhattan_oriented_bounds"]
    if not planes.walls:
        logger.warning("No wall planes; footprint is the floor-return AABB")
        warnings.append("no_wall_planes")
    walls_out: list[Wall] = []
    for i in range(len(polygon)):
        a = polygon[i]
        b = polygon[(i + 1) % len(polygon)]
        length = float(np.linalg.norm(b - a))
        heading = float(np.degrees(np.arctan2(b[1] - a[1], b[0] - a[0])) % 360.0)
        if planes.walls:
            wall = _nearest_wall(planes.walls, a, b, planes.up, basis)
            openings = detect_openings(wall, a, b, planes.up, basis, config)
            rmse = wall.rmse
            inliers = wall.inlier_count
            reason = "lidar_wall_ransac"
        else:
            openings = []
            rmse = planes.floor.rmse
            inliers = 50
            reason = "floor_aabb_no_walls"
        if not openings and inliers < 200:
            logger.warning("Thin wall evidence on wall_%02d; skipped openings", i)
            warnings.append(f"thin_wall_evidence:wall_{i:02d}")
        walls_out.append(
            Wall(
                wall_id=f"wall_{i:02d}",
                length_m=interval_from_evidence(
                    value=length,
                    residual_rmse=rmse,
                    inlier_count=inliers,
                    base_half=config.confidence.wall_base_half_m,
                    settings=config.confidence,
                    unit="m",
                    reason=reason,
                ),
                heading_deg=heading,
                openings=openings,
            )
        )

    area = _shoelace(polygon)
    height_ci = _ceiling_interval(planes, config, warnings)
    return RoomGeometry(
        room_id=room_id,
        tier=tier,  # type: ignore[arg-type]
        polygon_xy=[(float(x), float(y)) for x, y in polygon],
        walls=walls_out,
        ceiling_height_m=height_ci,
        floor_area_m2=interval_from_evidence(
            value=area,
            residual_rmse=planes.floor.rmse,
            inlier_count=planes.floor.inlier_count,
            base_half=config.confidence.area_base_half_m2,
            settings=config.confidence,
            unit="m2",
            reason="polygon_shoelace",
        ),
        warnings=warnings,
    )


def build_room_from_polygon(
    polygon: np.ndarray,
    config: AppConfig,
    room_id: str,
    tier: str,
    ceiling_m: float,
    openings_by_wall: list[list[Opening]],
    length_frac: float,
    reason: str,
    warnings: list[str],
) -> RoomGeometry:
    """Same RoomGeometry as LiDAR, from a 2D metric polygon. Photo/video land here."""

    if len(polygon) < 3:
        raise InsufficientPlanesError("Photo reconstruction produced fewer than 3 vertices.")
    if _shoelace(polygon) < 0:
        polygon = polygon[::-1]
        openings_by_wall = list(reversed(openings_by_wall))
    walls_out: list[Wall] = []
    n = len(polygon)
    while len(openings_by_wall) < n:
        openings_by_wall.append([])
    for i in range(n):
        a = polygon[i]
        b = polygon[(i + 1) % n]
        length = float(np.linalg.norm(b - a))
        heading = float(np.degrees(np.arctan2(b[1] - a[1], b[0] - a[0])) % 360.0)
        walls_out.append(
            Wall(
                wall_id=f"wall_{i:02d}",
                length_m=interval_calibrated(length, length_frac, "m", reason),
                heading_deg=heading,
                openings=openings_by_wall[i],
            )
        )
    area = abs(_shoelace(polygon))
    return RoomGeometry(
        room_id=room_id,
        tier=tier,  # type: ignore[arg-type]
        polygon_xy=[(float(x), float(y)) for x, y in polygon],
        walls=walls_out,
        ceiling_height_m=interval_calibrated(ceiling_m, length_frac, "m", reason, min_half=0.08),
        floor_area_m2=interval_calibrated(area, length_frac * 2.0, "m2", reason, min_half=0.2),
        warnings=warnings,
    )


def detect_openings(
    wall: Plane,
    start: np.ndarray,
    end: np.ndarray,
    up: np.ndarray,
    basis: np.ndarray,
    config: AppConfig,
) -> list[Opening]:
    """Find occupancy gaps along a wall. Conservative to avoid phantom openings."""

    length = float(np.linalg.norm(end - start))
    if length < config.openings.min_width_m:
        return []
    direction = (end - start) / length
    pts2 = _project(wall.inlier_points, up, basis)
    t = (pts2 - start) @ direction
    n2 = np.array([-direction[1], direction[0]])
    lateral = (pts2 - start) @ n2
    on_seg = (
        (t >= -0.05)
        & (t <= length + 0.05)
        & (np.abs(lateral) <= config.openings.wall_band_m + 0.5)
    )
    t = t[on_seg]
    if len(t) < 10:
        return []

    bin_m = config.openings.bin_m
    n_bins = max(int(np.ceil(length / bin_m)), 1)
    hist, _ = np.histogram(t, bins=n_bins, range=(0.0, length))
    occupied = hist >= config.openings.min_points_per_bin
    openings: list[Opening] = []
    i = 0
    while i < n_bins:
        if occupied[i]:
            i += 1
            continue
        j = i
        while j < n_bins and not occupied[j]:
            j += 1
        width = (j - i) * bin_m
        # Ignore empty ends: they are usually unscanned corners, not openings.
        if i == 0 or j == n_bins:
            i = j
            continue
        if config.openings.min_width_m <= width <= config.openings.max_width_m:
            kind = _opening_kind(width, config)
            openings.append(
                Opening(
                    kind=kind,
                    width_m=interval_from_evidence(
                        value=width,
                        residual_rmse=wall.rmse,
                        inlier_count=int(hist[i:j].sum()) + 1,
                        base_half=config.confidence.wall_base_half_m,
                        settings=config.confidence,
                        unit="m",
                        reason="wall_occupancy_gap",
                    ),
                    t0_m=i * bin_m,
                    t1_m=j * bin_m,
                )
            )
        i = j
    if openings:
        logger.info("Wall gap openings: %d", len(openings))
    return openings


def _opening_kind(width: float, config: AppConfig) -> OpeningKind:
    if config.openings.door_width_min_m <= width <= config.openings.door_width_max_m:
        return "door"
    return "unknown"


def _floor_basis(up: np.ndarray) -> np.ndarray:
    helper = np.array([1.0, 0.0, 0.0]) if abs(float(up[0])) < 0.9 else np.array([0.0, 1.0, 0.0])
    e0 = np.cross(up, helper)
    e0 = e0 / np.linalg.norm(e0)
    e1 = np.cross(up, e0)
    e1 = e1 / np.linalg.norm(e1)
    return np.stack([e0, e1], axis=1)


def _project(points: np.ndarray, up: np.ndarray, basis: np.ndarray) -> np.ndarray:
    pts = np.atleast_2d(np.asarray(points, dtype=np.float64))
    projected = pts @ basis
    if np.asarray(points).ndim == 1:
        return projected.reshape(-1)
    return projected


def _oriented_bounds(planes: PlaneSet, basis: np.ndarray) -> np.ndarray:
    """Manhattan box from wall heading + inlier extents.

    Why: parallel walls make a line-intersection cycle drop corners; an OBB always closes.
    """

    chunks = [planes.floor.inlier_points] + [w.inlier_points for w in planes.walls]
    pts2 = _project(np.concatenate(chunks, axis=0), planes.up, basis)
    if planes.walls:
        heading = np.asarray(
            _project(planes.walls[0].normal, planes.up, basis), dtype=np.float64
        ).reshape(2)
    else:
        centered = pts2 - pts2.mean(axis=0)
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        heading = vh[0]
    if np.linalg.norm(heading) < 1e-8:
        heading = np.array([1.0, 0.0])
    heading = heading / np.linalg.norm(heading)
    rot = np.stack([heading, np.array([-heading[1], heading[0]])], axis=1)
    local = pts2 @ rot
    lo = local.min(axis=0)
    hi = local.max(axis=0)
    if hi[0] - lo[0] < 0.4 or hi[1] - lo[1] < 0.4:
        return np.zeros((0, 2))
    corners_local = np.array(
        [
            [lo[0], lo[1]],
            [hi[0], lo[1]],
            [hi[0], hi[1]],
            [lo[0], hi[1]],
        ]
    )
    poly = corners_local @ rot.T
    if _shoelace(poly) < 0:
        poly = poly[::-1]
    return poly


def _nearest_wall(
    walls: list[Plane],
    start: np.ndarray,
    end: np.ndarray,
    up: np.ndarray,
    basis: np.ndarray,
) -> Plane:
    mid = 0.5 * (start + end)
    edge = end - start
    edge_n = np.array([-edge[1], edge[0]], dtype=np.float64)
    edge_n = edge_n / (np.linalg.norm(edge_n) + 1e-12)
    best = walls[0]
    best_score = -1.0
    for wall in walls:
        n2 = np.asarray(_project(wall.normal, up, basis), dtype=np.float64).reshape(2)
        if np.linalg.norm(n2) < 1e-8:
            continue
        n2 = n2 / np.linalg.norm(n2)
        align = abs(float(n2 @ edge_n))
        centroid = np.asarray(
            _project(wall.inlier_points.mean(axis=0), up, basis), dtype=np.float64
        ).reshape(2)
        dist = abs(float((centroid - mid) @ n2))
        score = align * 2.0 - dist
        if score > best_score:
            best_score = score
            best = wall
    return best


def _shoelace(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _ceiling_interval(planes: PlaneSet, config: AppConfig, warnings: list[str]):
    if planes.ceiling is None:
        logger.warning("No ceiling plane; widening height interval")
        warnings.append("no_ceiling_returns")
        return missing_ceiling_interval(config.confidence)
    origin = -planes.floor.offset * planes.floor.normal
    height = abs(float(planes.ceiling.normal @ origin + planes.ceiling.offset))
    rmse = max(planes.floor.rmse, planes.ceiling.rmse)
    return interval_from_evidence(
        value=height,
        residual_rmse=rmse,
        inlier_count=min(planes.floor.inlier_count, planes.ceiling.inlier_count),
        base_half=config.confidence.height_base_half_m,
        settings=config.confidence,
        unit="m",
        reason="floor_ceiling_separation",
    )
