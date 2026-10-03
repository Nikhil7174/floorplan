from pathlib import Path

import numpy as np

from floorplan.config import AppConfig
from floorplan.pipeline import process_capture
from floorplan.reconstruction.depth_model import (
    DoorPixels,
    backproject_depth,
    fit_affine_door,
    metric_cloud,
    sane_depth_map,
)
from floorplan.schema.validate import validate_plan


def _cfg() -> AppConfig:
    cfg = AppConfig()
    cfg.photos.use_depth_model = True
    cfg.photos.depth_stride = 2
    cfg.photos.depth_min_inliers = 80
    cfg.photos.depth_residual_m = 0.12
    return cfg


def test_affine_door_uses_floor_anchor_not_door_width() -> None:
    """Second constraint is floor-band camera height (different d), not door width."""

    h, w = 80, 100
    vs = np.arange(h)[:, None]
    z_true = 2.0 + 0.02 * vs
    z_true = np.repeat(z_true, w, axis=1)
    a_true, b_true = 1.5, 0.4
    depth = ((z_true - b_true) / a_true).astype(np.float32)
    door = DoorPixels(
        top=np.array([40.0, 15.0]),
        bottom=np.array([40.0, 55.0]),
        left=np.array([32.0, 35.0]),
        right=np.array([48.0, 35.0]),
    )
    fx = fy = float(max(w, h))
    cx, cy = w * 0.5, h * 0.5
    cfg = _cfg()
    pixel_h = 40.0
    z_door = 2.0 + 0.02 * 35.0
    cfg.photos.door_height_m = z_door * pixel_h / fy
    vs_f = np.arange(int(h * 0.86), h, 4)
    v_floor = float(np.median(vs_f))
    z_floor = 2.0 + 0.02 * v_floor
    cfg.photos.camera_height_prior_m = z_floor * (v_floor - cy) / fy

    a, b, ok = fit_affine_door(depth, door, cfg, fx, fy, cx, cy)
    assert ok
    assert abs(a - a_true) / a_true < 0.12
    assert abs(b - b_true) < 0.15


def test_sane_depth_map_rejects_flat_and_planar() -> None:
    flat = np.full((40, 50), 2.0, dtype=np.float32)
    assert sane_depth_map(flat) is False
    ys = np.linspace(0, 1, 60)[:, None]
    xs = np.linspace(0, 1, 80)[None, :]
    planar = (2.0 + 0.3 * xs + 0.2 * ys).astype(np.float32)
    assert sane_depth_map(planar) is False
    room = np.zeros((60, 80), dtype=np.float32)
    room[:30, :] = 1.2 + 0.05 * xs
    room[30:, :] = 3.8 + 0.4 * (ys[30:] ** 2)
    room[20:40, 25:55] = 2.4
    assert sane_depth_map(room) is True


def test_backproject_positive_z_and_count() -> None:
    depth = np.full((40, 50), 2.0, dtype=np.float32)
    xyz = backproject_depth(depth, scale=1.0, shift=0.5, config=_cfg())
    assert len(xyz) > 50
    assert float(xyz[:, 2].min()) > 0.2


def test_metric_cloud_door_reason() -> None:
    h, w = 60, 80
    depth = np.full((h, w), 2.0, dtype=np.float32)
    depth[20:50, 30:50] = 3.0
    depth[50:, :] = 3.4
    door = DoorPixels(
        top=np.array([40.0, 12.0]),
        bottom=np.array([40.0, 48.0]),
        left=np.array([34.0, 30.0]),
        right=np.array([46.0, 30.0]),
    )
    xyz, reason, extra = metric_cloud(depth, door, _cfg())
    assert len(xyz) > 100
    assert reason in {"door_height_2.032m", "ceiling_prior_no_door"}
    assert "depth_affine_door" in extra or "depth_affine_prior" in extra


def test_photo_pipeline_uses_depth_polygon(tmp_path: Path, monkeypatch) -> None:
    """Wrapper path: mocked depth room becomes PropertyPlan at ±8%, not VP."""

    import floorplan.reconstruction.sfm as sfm_mod

    room = tmp_path / "living"
    room.mkdir()
    (room / "00.jpg").write_bytes(b"x")
    (room / "01.jpg").write_bytes(b"x")
    polygon = np.array([[0.0, 0.0], [4.0, 0.0], [4.0, 3.5], [0.0, 3.5]], dtype=np.float64)

    def _depth(_image, _config, label: str = "still"):
        return 10.0, polygon.copy(), [[], [], [], []], 2.4, "door_height_2.032m", ["depth_anything_v2"]

    monkeypatch.setattr(sfm_mod, "reconstruct_from_depth", _depth)
    monkeypatch.setattr(sfm_mod, "load_image", lambda _p: np.zeros((32, 32, 3), dtype=np.uint8))
    cfg = _cfg()
    plan = process_capture(tmp_path, cfg)
    validate_plan(plan)
    assert plan.tier == "photos"
    wall = plan.rooms[0].walls[0].length_m
    assert wall.reason == "door_height_2.032m"
    span = (wall.hi - wall.lo) / max(wall.value, 1e-3)
    assert 0.07 <= span <= 0.17
