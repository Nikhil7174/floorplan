import cv2
import numpy as np

from floorplan.config import AppConfig
from floorplan.confidence.scoring import interval_calibrated
from floorplan.damage.concealed_rules import apply_concealed_rules
from floorplan.damage.detection import DRAFT_WARNING, detect_damage
from floorplan.models import RoomGeometry, Wall


def _cfg() -> AppConfig:
    return AppConfig()


def test_stain_blob_detected() -> None:
    img = np.full((240, 320, 3), 230, dtype=np.uint8)
    cv2.ellipse(img, (160, 120), (28, 22), 0, 0, 360, (20, 70, 160), -1)
    regions, warnings = detect_damage([img], _cfg())
    kinds = {r.kind for r in regions}
    assert "stain" in kinds
    assert DRAFT_WARNING in warnings


def test_crack_line_detected() -> None:
    img = np.full((240, 320, 3), 230, dtype=np.uint8)
    cv2.line(img, (160, 20), (168, 220), (10, 10, 10), 2)
    regions, warnings = detect_damage([img], _cfg())
    kinds = {r.kind for r in regions}
    assert "crack" in kinds
    assert DRAFT_WARNING in warnings


def test_blank_wall_finds_nothing() -> None:
    img = np.full((240, 320, 3), 230, dtype=np.uint8)
    regions, warnings = detect_damage([img], _cfg())
    assert regions == []
    assert "no_damage_detected" in warnings
    assert DRAFT_WARNING in warnings


def test_concealed_no_ceiling_flag() -> None:
    ci = interval_calibrated(2.4, 0.30, "m", "fallback_prior")
    room = RoomGeometry(
        room_id="r",
        tier="photos",
        polygon_xy=[(0, 0), (4, 0), (4, 3), (0, 3)],
        walls=[
            Wall(wall_id=f"wall_{i:02d}", length_m=ci, heading_deg=90.0 * i, openings=[])
            for i in range(4)
        ],
        ceiling_height_m=ci,
        floor_area_m2=ci,
        warnings=["no_ceiling_from_depth", "thin_wall_evidence:wall_00"],
    )
    flags = apply_concealed_rules(room)
    assert "concealed_possible:no_ceiling" in flags
    assert "concealed_possible:occluded_wall" in flags
