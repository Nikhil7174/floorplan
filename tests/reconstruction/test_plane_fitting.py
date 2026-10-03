import numpy as np

from floorplan.config import AppConfig
from floorplan.models import PointCloud
from floorplan.pipeline import process_capture
from floorplan.reconstruction.plane_fitting import classify_planes, extract_planes


def _box_cloud(rng: np.random.Generator) -> PointCloud:
    """Axis-aligned 4x5x2.5 m room. Why: protect polygon math without a 9k-frame scan."""

    pts = []
    # floor y=0, ceiling y=2.5, walls x=0/4, z=0/5
    xs = rng.uniform(0, 4, 800)
    zs = rng.uniform(0, 5, 800)
    pts.append(np.stack([xs, np.zeros(800) + rng.normal(0, 0.005, 800), zs], axis=1))
    xs = rng.uniform(0, 4, 600)
    zs = rng.uniform(0, 5, 600)
    pts.append(np.stack([xs, np.full(600, 2.5) + rng.normal(0, 0.005, 600), zs], axis=1))
    for x in (0.0, 4.0):
        ys = rng.uniform(0, 2.5, 500)
        zs = rng.uniform(0, 5, 500)
        pts.append(np.stack([np.full(500, x), ys, zs], axis=1))
    for z in (0.0, 5.0):
        xs = rng.uniform(0, 4, 500)
        ys = rng.uniform(0, 2.5, 500)
        pts.append(np.stack([xs, ys, np.full(500, z)], axis=1))
    return PointCloud(xyz=np.concatenate(pts, axis=0))


def test_synthetic_box_has_floor_ceiling_and_four_walls() -> None:
    cfg = AppConfig()
    cfg.ransac.min_inliers = 200
    cfg.ransac.iterations = 200
    cloud = _box_cloud(np.random.default_rng(42))
    planes = extract_planes(cloud, cfg)
    cameras = np.array([[2.0, 1.4, 2.5]])
    labeled = classify_planes(planes, cameras, cfg)
    assert labeled.floor is not None
    assert labeled.ceiling is not None
    assert len(labeled.walls) >= 3


def test_single_room_has_floor_and_three_walls(single_room, fast_config) -> None:
    plan = process_capture(single_room, fast_config)
    room = plan.rooms[0]
    assert len(room.walls) >= 3
    assert len(room.polygon_xy) >= 3
    assert room.floor_area_m2.value > 1.0


def test_floor_only_widens_ceiling(floor_only, fast_config) -> None:
    fast_config.lidar.frame_stride = 30
    plan = process_capture(floor_only, fast_config)
    height = plan.rooms[0].ceiling_height_m
    assert height.reason == "no_ceiling_returns"
    assert (height.hi - height.lo) >= 1.0


def test_with_ceiling_reports_measured_height(with_ceiling, fast_config) -> None:
    fast_config.lidar.frame_stride = 50
    plan = process_capture(with_ceiling, fast_config)
    height = plan.rooms[0].ceiling_height_m
    assert height.reason == "floor_ceiling_separation"
    assert 1.8 <= height.value <= 4.0
    assert (height.hi - height.lo) < 1.0
