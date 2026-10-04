"""Load the single YAML config. Why: every scored threshold must have one address."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class LidarSettings(BaseModel):
    frame_stride: int = 12
    pixel_stride: int = 4
    min_confidence: int = 1
    max_depth_m: float = 8.0
    min_depth_m: float = 0.15
    voxel_m: float = 0.04
    rgb_size: tuple[int, int] = (1920, 1440)


class RansacSettings(BaseModel):
    residual_m: float = 0.02
    iterations: int = 350
    min_inliers: int = 400
    max_planes: int = 10


class PlaneSettings(BaseModel):
    horizontal_align: float = 0.88
    vertical_align: float = 0.45
    wall_merge_angle_deg: float = 12.0
    wall_merge_offset_m: float = 0.12
    manhattan_snap: bool = True
    min_ceiling_height_m: float = 1.8
    max_ceiling_height_m: float = 4.0


class OpeningSettings(BaseModel):
    min_width_m: float = 0.55
    max_width_m: float = 2.4
    door_width_min_m: float = 0.7
    door_width_max_m: float = 1.15
    bin_m: float = 0.05
    min_points_per_bin: int = 3
    wall_band_m: float = 0.08


class PhotoSettings(BaseModel):
    min_images: int = 2
    max_use_images: int = 8
    door_height_m: float = 2.032
    ceiling_prior_m: float = 2.4
    line_min_length_px: int = 40
    line_min_length_frac: float = 0.08
    max_long_edge_px: int = 1600
    pre_blur_px: int = 5
    vp_iterations: int = 250
    vp_inlier_px: float = 4.0
    min_intersect_angle_deg: float = 8.0
    family_parallel_max_deg: float = 25.0
    min_sane_stills: int = 3
    use_depth_model: bool = True
    depth_model_id: str = "depth-anything/Depth-Anything-V2-Small-hf"
    depth_stride: int = 4
    depth_residual_m: float = 0.08
    depth_min_inliers: int = 200
    depth_voxel_m: float = 0.05
    depth_min_z_m: float = 0.2
    depth_max_z_m: float = 12.0
    door_width_m: float = 0.90
    camera_height_prior_m: float = 1.50
    # Calibrated half-width as a fraction of the value (photo gate is ±8%).
    door_scale_frac: float = 0.08
    prior_scale_frac: float = 0.18
    failed_scale_frac: float = 0.30
    fallback_width_m: float = 4.0
    fallback_depth_m: float = 5.0


class VideoSettings(BaseModel):
    keyframe_count: int = 16
    skip_start_frac: float = 0.10
    skip_end_frac: float = 0.10
    min_sane_frames: int = 3
    consensus_frac: float = 0.03
    thin_frac: float = 0.08
    midpoint_bias: bool = True


class DamageSettings(BaseModel):
    enabled: bool = True
    # Conservative: prefer false negatives. Draft — precision not benchmarked.
    stain_min_area_frac: float = 0.008
    stain_max_area_frac: float = 0.06
    stain_sat_min: int = 40
    crack_min_length_frac: float = 0.18
    crack_max_width_px: int = 6
    crack_min_aspect: float = 10.0


class ConfidenceSettings(BaseModel):
    wall_base_half_m: float = 0.015
    height_base_half_m: float = 0.01
    area_base_half_m2: float = 0.15
    residual_gain: float = 1.5
    sparse_gain: float = 0.04
    missing_ceiling_prior_m: float = 2.4
    missing_ceiling_half_m: float = 0.8


class AppConfig(BaseModel):
    seed: int = 42
    lidar: LidarSettings = Field(default_factory=LidarSettings)
    ransac: RansacSettings = Field(default_factory=RansacSettings)
    planes: PlaneSettings = Field(default_factory=PlaneSettings)
    openings: OpeningSettings = Field(default_factory=OpeningSettings)
    photos: PhotoSettings = Field(default_factory=PhotoSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    damage: DamageSettings = Field(default_factory=DamageSettings)
    confidence: ConfidenceSettings = Field(default_factory=ConfidenceSettings)


def default_config_path() -> Path:
    """Prefer cwd, then walk parents of this file. Why: the installed package is not the repo."""

    cwd_candidate = Path.cwd() / "configs" / "default.yaml"
    if cwd_candidate.is_file():
        return cwd_candidate
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "configs" / "default.yaml"
        if candidate.is_file():
            return candidate
    return Path("configs/default.yaml")


def load_config(path: Path | None = None) -> AppConfig:
    """Parse YAML into AppConfig. Missing file uses defaults so tests stay self-contained."""

    cfg_path = path or default_config_path()
    if not cfg_path.is_file():
        return AppConfig()
    with cfg_path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    return AppConfig.model_validate(raw)
