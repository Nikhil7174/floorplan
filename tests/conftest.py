"""Shared capture paths. Tests skip if the local symlinks are missing."""

from __future__ import annotations

from pathlib import Path

import pytest

from floorplan.config import AppConfig

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
SINGLE_ROOM = RAW / "single_room"
FLOOR_ONLY = RAW / "floor_only"
WITH_CEILING = RAW / "with_ceiling"


def _require(path: Path) -> Path:
    if not (path / "odometry.csv").is_file():
        pytest.skip(f"Capture not linked: {path}")
    return path


@pytest.fixture
def single_room() -> Path:
    return _require(SINGLE_ROOM)


@pytest.fixture
def floor_only() -> Path:
    return _require(FLOOR_ONLY)


@pytest.fixture
def with_ceiling() -> Path:
    return _require(WITH_CEILING)


@pytest.fixture
def fast_config() -> AppConfig:
    """Fewer frames so stage tests stay short while remaining deterministic."""

    cfg = AppConfig()
    cfg.seed = 42
    cfg.lidar.frame_stride = 20
    cfg.lidar.pixel_stride = 6
    cfg.lidar.voxel_m = 0.05
    cfg.ransac.iterations = 220
    cfg.ransac.min_inliers = 250
    return cfg
