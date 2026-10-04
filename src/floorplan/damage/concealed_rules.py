"""Concealed-damage flags. Rules on missing evidence — not a detector."""

from __future__ import annotations

from floorplan.models import RoomGeometry


def apply_concealed_rules(room: RoomGeometry) -> list[str]:
    """Flags where we cannot see a surface. Never claim a hidden stain exists."""

    flags: list[str] = []
    blob = " ".join(room.warnings)
    reason = room.ceiling_height_m.reason
    if "no_ceiling" in blob or reason in {"no_ceiling_returns", "fallback_prior"}:
        flags.append("concealed_possible:no_ceiling")
    if any("thin_wall" in w for w in room.warnings):
        flags.append("concealed_possible:occluded_wall")
    return flags
