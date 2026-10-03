from pathlib import Path

import cv2
import numpy as np

from floorplan.ingestion.detect import detect_tier
from floorplan.ingestion.video import ingest_video


def _tiny_mp4(path: Path, frames: int = 4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 8.0, (64, 48))
    assert writer.isOpened(), f"could not open VideoWriter for {path}"
    blank = np.full((48, 64, 3), 90, dtype=np.uint8)
    for _ in range(frames):
        writer.write(blank)
    writer.release()


def test_detect_nested_clips_is_video(tmp_path: Path) -> None:
    _tiny_mp4(tmp_path / "living" / "walk.mp4")
    _tiny_mp4(tmp_path / "kitchen" / "walk.mp4")
    assert detect_tier(tmp_path) == "video"
    capture = ingest_video(tmp_path)
    assert {room.room_id for room in capture.rooms} == {"living", "kitchen"}


def test_detect_top_level_clip_is_video(tmp_path: Path) -> None:
    _tiny_mp4(tmp_path / "walk.mp4")
    assert detect_tier(tmp_path) == "video"
    capture = ingest_video(tmp_path)
    assert len(capture.rooms) == 1
    assert capture.rooms[0].room_id == tmp_path.name


def test_lidar_folder_with_rgb_mp4_stays_lidar(single_room) -> None:
    assert (single_room / "rgb.mp4").is_file()
    assert detect_tier(single_room) == "lidar"
