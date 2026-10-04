from pathlib import Path

import numpy as np

from floorplan.config import AppConfig
from floorplan.pipeline import process_capture
from floorplan.schema.validate import validate_plan


def test_same_stills_same_seed_same_walls(tmp_path: Path, monkeypatch) -> None:
    """Repeatability: identical input + seed 42 must not wander."""

    import floorplan.reconstruction.sfm as sfm_mod

    room = tmp_path / "bedroom"
    room.mkdir()
    (room / "00.jpg").write_bytes(b"x")
    (room / "01.jpg").write_bytes(b"x")
    polygon = np.array([[0.0, 0.0], [4.01, 0.0], [4.01, 3.31], [0.0, 3.31]], dtype=np.float64)

    def _fixed(_image, _config, label: str = "still"):
        return 2.0, polygon.copy(), [[], [], [], []], 2.4, "door_height_2.032m", []

    monkeypatch.setattr(sfm_mod, "reconstruct_from_bgr", _fixed)
    monkeypatch.setattr(sfm_mod, "load_image", lambda _p: np.zeros((32, 32, 3), dtype=np.uint8))
    cfg = AppConfig()
    cfg.photos.use_depth_model = True
    cfg.damage.enabled = False
    a = process_capture(tmp_path, cfg)
    b = process_capture(tmp_path, cfg)
    validate_plan(a)
    validate_plan(b)
    wa = [w.length_m.value for w in a.rooms[0].walls]
    wb = [w.length_m.value for w in b.rooms[0].walls]
    assert wa == wb
    assert a.rooms[0].polygon_xy == b.rooms[0].polygon_xy
