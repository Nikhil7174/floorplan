"""Per-surface damage regions. Stubbed this increment."""

from __future__ import annotations

from floorplan.exceptions import UnsupportedTierError
from floorplan.models import RoomGeometry


def detect_damage(_room: RoomGeometry) -> None:
    raise UnsupportedTierError("Damage detection is not implemented yet.")
