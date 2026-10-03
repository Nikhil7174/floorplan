"""Door-width adjacency. Thin photo evidence: match openings, otherwise do not invent walls."""

from __future__ import annotations

import logging

from floorplan.models import Adjacency, Opening, RoomGeometry

logger = logging.getLogger(__name__)


def infer_adjacencies(rooms: list[RoomGeometry]) -> list[Adjacency]:
    """Pair rooms whose door widths agree within 20%. Why: no poses between photo folders."""

    if len(rooms) < 2:
        return []
    used: set[tuple[str, str]] = set()
    adjacencies: list[Adjacency] = []
    for i, room_a in enumerate(rooms):
        for room_b in rooms[i + 1 :]:
            match = _best_door_pair(room_a, room_b)
            if match is None:
                continue
            wall_a, wall_b, _ = match
            key = tuple(sorted((room_a.room_id, room_b.room_id)))
            if key in used:
                continue
            used.add(key)
            adjacencies.append(
                Adjacency(
                    room_a=room_a.room_id,
                    room_b=room_b.room_id,
                    via="door",
                    shared_wall_a=wall_a,
                    shared_wall_b=wall_b,
                )
            )
            logger.info("Adjacency %s — %s via doors", room_a.room_id, room_b.room_id)
    return adjacencies


def _best_door_pair(
    room_a: RoomGeometry, room_b: RoomGeometry
) -> tuple[str, str, float] | None:
    best: tuple[str, str, float] | None = None
    best_diff = 1e9
    for wall_a in room_a.walls:
        for opening_a in wall_a.openings:
            if opening_a.kind != "door":
                continue
            for wall_b in room_b.walls:
                for opening_b in wall_b.openings:
                    if opening_b.kind != "door":
                        continue
                    diff = abs(opening_a.width_m.value - opening_b.width_m.value)
                    rel = diff / max(opening_a.width_m.value, 1e-3)
                    if rel <= 0.20 and diff < best_diff:
                        best_diff = diff
                        best = (wall_a.wall_id, wall_b.wall_id, opening_a.width_m.value)
    return best


def doors_of(room: RoomGeometry) -> list[tuple[str, Opening]]:
    return [(wall.wall_id, opening) for wall in room.walls for opening in wall.openings]
