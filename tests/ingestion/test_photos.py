from pathlib import Path

import cv2
import numpy as np

from floorplan.config import AppConfig
from floorplan.ingestion.detect import detect_tier
from floorplan.ingestion.photos import ingest_photos


def _write_jpg(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.full((48, 64, 3), 180, dtype=np.uint8))


def test_detect_flat_photo_folder(tmp_path: Path) -> None:
    _write_jpg(tmp_path / "a.jpg")
    _write_jpg(tmp_path / "b.jpg")
    assert detect_tier(tmp_path) == "photos"


def test_detect_per_room_folders(tmp_path: Path) -> None:
    _write_jpg(tmp_path / "kitchen" / "1.jpg")
    _write_jpg(tmp_path / "kitchen" / "2.jpg")
    _write_jpg(tmp_path / "bath" / "1.jpg")
    assert detect_tier(tmp_path) == "photos"
    capture = ingest_photos(tmp_path, AppConfig())
    assert {room.room_id for room in capture.rooms} == {"kitchen", "bath"}
    assert len(capture.rooms[0].images) >= 1
