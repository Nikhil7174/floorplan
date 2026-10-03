from pathlib import Path

import cv2
import numpy as np

from floorplan.config import AppConfig
from floorplan.models import Opening, RoomGeometry, Wall
from floorplan.pipeline import process_capture
from floorplan.schema.validate import validate_plan
from floorplan.stitching.multi_room import stitch_rooms


def _synthetic_interior(path: Path) -> None:
    """Perspective box + door. Why: unit-test VP/scale without a real iPhone still."""

    img = np.full((720, 960, 3), 230, dtype=np.uint8)
    # Back wall
    cv2.rectangle(img, (280, 160), (680, 420), (200, 195, 190), -1)
    cv2.rectangle(img, (280, 160), (680, 420), (40, 40, 40), 3)
    # Floor trapezoid
    floor = np.array([[80, 700], [880, 700], [680, 420], [280, 420]], dtype=np.int32)
    cv2.fillConvexPoly(img, floor, (170, 165, 160))
    cv2.polylines(img, [floor], True, (30, 30, 30), 3)
    # Side walls
    cv2.line(img, (80, 700), (280, 160), (30, 30, 30), 3)
    cv2.line(img, (880, 700), (680, 160), (30, 30, 30), 3)
    cv2.line(img, (280, 160), (680, 160), (30, 30, 30), 3)
    # Door on the back wall (vertical pair + header)
    cv2.rectangle(img, (430, 230), (530, 418), (90, 70, 50), -1)
    cv2.rectangle(img, (430, 230), (530, 418), (20, 20, 20), 3)
    cv2.imwrite(str(path), img)


def test_photo_pipeline_synthetic_room(tmp_path: Path) -> None:
    room = tmp_path / "living"
    room.mkdir()
    for i in range(3):
        _synthetic_interior(room / f"{i:02d}.jpg")
    plan = process_capture(tmp_path, AppConfig())
    validate_plan(plan)
    assert plan.tier == "photos"
    assert len(plan.rooms) == 1
    geom = plan.rooms[0]
    assert len(geom.walls) >= 3
    assert geom.floor_area_m2.value > 0
    half = geom.walls[0].length_m
    assert half.lo < half.value < half.hi
    assert (half.hi - half.lo) / max(half.value, 1e-3) >= 0.07
    assert geom.ceiling_height_m.reason in {
        "door_height_2.032m",
        "ceiling_prior_no_door",
        "fallback_prior",
    }


def test_multi_room_photo_folders_do_not_overlap(tmp_path: Path) -> None:
    for name in ("a", "b"):
        folder = tmp_path / name
        folder.mkdir()
        _synthetic_interior(folder / "00.jpg")
        _synthetic_interior(folder / "01.jpg")
    plan = process_capture(tmp_path, AppConfig())
    assert len(plan.rooms) == 2
    a, b = plan.rooms

    def aabb(room: RoomGeometry) -> tuple[float, float, float, float]:
        xs = [p[0] for p in room.polygon_xy]
        ys = [p[1] for p in room.polygon_xy]
        return min(xs), min(ys), max(xs), max(ys)

    aa, bb = aabb(a), aabb(b)
    overlap = aa[0] < bb[2] and aa[2] > bb[0] and aa[1] < bb[3] and aa[3] > bb[1]
    assert not overlap


def test_photo_proxy_from_lidar_video(single_room, tmp_path: Path) -> None:
    video = single_room / "rgb.mp4"
    if not video.is_file():
        return
    dest = tmp_path / "proxy" / "room"
    dest.mkdir(parents=True)
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if n < 4:
        cap.release()
        return
    for i, idx in enumerate(np.linspace(n * 0.2, n * 0.8, 4).astype(int)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if ok:
            cv2.imwrite(str(dest / f"{i:02d}.jpg"), frame)
    cap.release()
    plan = process_capture(dest.parent, AppConfig())
    validate_plan(plan)
    assert plan.tier == "photos"
    assert plan.rooms[0].walls


def test_stitch_resolves_overlap() -> None:
    def box(room_id: str, x0: float) -> RoomGeometry:
        from floorplan.confidence.scoring import interval_calibrated

        ci = interval_calibrated(4.0, 0.08, "m", "test")
        walls = [
            Wall(wall_id=f"wall_{i:02d}", length_m=ci, heading_deg=90.0 * i, openings=[])
            for i in range(4)
        ]
        walls[0] = walls[0].model_copy(
            update={
                "openings": [
                    Opening(kind="door", width_m=interval_calibrated(0.9, 0.08, "m", "test"), t0_m=1.0, t1_m=1.9)
                ]
            }
        )
        return RoomGeometry(
            room_id=room_id,
            tier="photos",
            polygon_xy=[(x0, 0.0), (x0 + 4.0, 0.0), (x0 + 4.0, 3.0), (x0, 3.0)],
            walls=walls,
            ceiling_height_m=ci,
            floor_area_m2=interval_calibrated(12.0, 0.16, "m2", "test"),
            warnings=[],
        )

    plan = stitch_rooms([box("r1", 0.0), box("r2", 0.0)], "prop", "photos")
    assert len(plan.adjacencies) == 1
    xs1 = [p[0] for p in plan.rooms[0].polygon_xy]
    xs2 = [p[0] for p in plan.rooms[1].polygon_xy]
    assert max(xs1) <= min(xs2) + 1e-6 or max(xs2) <= min(xs1) + 1e-6
