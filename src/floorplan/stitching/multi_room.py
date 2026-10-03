"""Place independently reconstructed rooms so they do not overlap."""

from __future__ import annotations

import logging

import numpy as np

from floorplan.models import PropertyPlan, RoomGeometry
from floorplan.stitching.adjacency import infer_adjacencies

logger = logging.getLogger(__name__)


def stitch_rooms(rooms: list[RoomGeometry], capture_id: str, tier: str) -> PropertyPlan:
    """Translate rooms into a shared frame. Door matches sit adjacent; otherwise pack in a row.

    Why: photo folders have no shared poses. Inventing a pose graph would be confident garbage.
    Drift correction is a later LiDAR increment; here we only guarantee no overlaps.
    """

    if not rooms:
        raise ValueError("stitch_rooms requires at least one room.")
    placed = [_shift_to_origin(rooms[0])]
    adjacencies = infer_adjacencies(rooms)
    cursor_x = _aabb(placed[0])[2] + 0.4
    matched_ids = {(a.room_a, a.room_b) for a in adjacencies} | {
        (a.room_b, a.room_a) for a in adjacencies
    }
    for room in rooms[1:]:
        partner = None
        for already in placed:
            if (room.room_id, already.room_id) in matched_ids:
                partner = already
                break
        if partner is not None:
            placed.append(_place_against(room, partner))
        else:
            shifted = _translate(room, np.array([cursor_x - _aabb(room)[0], 0.0]))
            placed.append(shifted)
            cursor_x = _aabb(shifted)[2] + 0.4
            logger.warning("No door match for %s; packed without overlap", room.room_id)
    placed = _resolve_overlaps(placed)
    warnings = []
    for room in placed:
        warnings.extend(room.warnings)
    if len(placed) > 1 and not adjacencies:
        warnings.append("photo_stitch_unmatched_doors")
    return PropertyPlan(
        tier=tier,  # type: ignore[arg-type]
        capture_id=capture_id,
        rooms=placed,
        adjacencies=adjacencies,
        warnings=warnings,
    )


def _shift_to_origin(room: RoomGeometry) -> RoomGeometry:
    poly = np.array(room.polygon_xy, dtype=np.float64)
    return _translate(room, -poly.min(axis=0))


def _place_against(room: RoomGeometry, partner: RoomGeometry) -> RoomGeometry:
    """Put `room` to the right of `partner` with a 0.15 m gap (door-aligned later)."""

    _x0, _y0, x1, _y1 = _aabb(partner)
    rx0, ry0, _rx1, _ry1 = _aabb(room)
    delta = np.array([x1 + 0.15 - rx0, _aabb(partner)[1] - ry0])
    return _translate(room, delta)


def _resolve_overlaps(rooms: list[RoomGeometry]) -> list[RoomGeometry]:
    placed = [rooms[0]]
    for room in rooms[1:]:
        current = room
        for _ in range(12):
            hit = False
            for other in placed:
                if _aabb_overlap(_aabb(current), _aabb(other)):
                    ox0, _oy0, ox1, _oy1 = _aabb(other)
                    cx0, cy0, _cx1, _cy1 = _aabb(current)
                    current = _translate(current, np.array([ox1 + 0.2 - cx0, 0.0]))
                    hit = True
                    break
            if not hit:
                break
        placed.append(current)
    return placed


def _translate(room: RoomGeometry, delta: np.ndarray) -> RoomGeometry:
    poly = [(x + float(delta[0]), y + float(delta[1])) for x, y in room.polygon_xy]
    return room.model_copy(update={"polygon_xy": poly})


def _aabb(room: RoomGeometry) -> tuple[float, float, float, float]:
    xs = [p[0] for p in room.polygon_xy]
    ys = [p[1] for p in room.polygon_xy]
    return min(xs), min(ys), max(xs), max(ys)


def _aabb_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    eps: float = 1e-3,
) -> bool:
    return a[0] < b[2] - eps and a[2] > b[0] + eps and a[1] < b[3] - eps and a[3] > b[1] + eps
