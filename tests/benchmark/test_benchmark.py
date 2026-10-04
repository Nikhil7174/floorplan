from pathlib import Path

from floorplan.confidence.scoring import interval_calibrated
from floorplan.models import PropertyPlan, RoomGeometry, Wall
from scripts.benchmark import load_tape, score_room, wall_frac_for_plan


def test_load_home_room_tape() -> None:
    tape = load_tape(Path("data/ground_truth/home_room.csv"))
    assert len(tape.walls) == 4
    assert tape.walls[0] == 3.31
    assert tape.area_m2 is not None
    assert abs(tape.area_m2 - 13.2964) < 1e-4
    assert tape.ceiling_m == 2.76


def test_score_sorted_walls_pass_and_fail(tmp_path: Path) -> None:
    tape = load_tape(Path("data/ground_truth/home_room.csv"))
    ci = interval_calibrated(3.35, 0.08, "m", "door_height_2.032m")
    walls = [
        Wall(wall_id=f"wall_{i:02d}", length_m=ci, heading_deg=90.0 * i, openings=[])
        for i in range(4)
    ]
    # Sorted preds ~ tape except last wall blown out.
    lengths = [3.35, 3.40, 3.90, 8.00]
    walls = [
        Wall(
            wall_id=f"wall_{i:02d}",
            length_m=interval_calibrated(lengths[i], 0.08, "m", "door_height_2.032m"),
            heading_deg=90.0 * i,
            openings=[],
        )
        for i in range(4)
    ]
    room = RoomGeometry(
        room_id="home_room",
        tier="photos",
        polygon_xy=[(0, 0), (4, 0), (4, 3), (0, 3)],
        walls=walls,
        ceiling_height_m=interval_calibrated(2.4, 0.08, "m", "door_height_2.032m"),
        floor_area_m2=interval_calibrated(13.3, 0.16, "m2", "door_height_2.032m"),
    )
    plan = PropertyPlan(tier="photos", capture_id="home_room", rooms=[room])
    assert wall_frac_for_plan(plan) == 0.08
    text = "\n".join(score_room(plan, tape))
    assert "PASS" in text
    assert "FAIL" in text
    assert "8.00" in text
