"""Typed objects that flow between pipeline stages.

Confidence is a field on every metric so thin evidence widens intervals
instead of inventing a tight number at the end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

Tier = Literal["photos", "video", "lidar"]
OpeningKind = Literal["door", "window", "unknown"]


class ConfidenceInterval(BaseModel):
    """A measured value plus an honest interval and the reason it is that wide."""

    value: float
    lo: float
    hi: float
    unit: str
    reason: str


class Opening(BaseModel):
    kind: OpeningKind
    width_m: ConfidenceInterval
    t0_m: float = Field(description="Start along the wall from the first vertex, meters.")
    t1_m: float


class Wall(BaseModel):
    wall_id: str
    length_m: ConfidenceInterval
    heading_deg: float
    openings: list[Opening] = Field(default_factory=list)


class RoomGeometry(BaseModel):
    """Same object from every tier so downstream stages do not branch on sensor type."""

    room_id: str
    tier: Tier
    polygon_xy: list[tuple[float, float]]
    walls: list[Wall]
    ceiling_height_m: ConfidenceInterval
    floor_area_m2: ConfidenceInterval
    warnings: list[str] = Field(default_factory=list)


class Adjacency(BaseModel):
    room_a: str
    room_b: str
    via: Literal["door", "opening", "unknown"] = "unknown"
    shared_wall_a: str | None = None
    shared_wall_b: str | None = None


class PropertyPlan(BaseModel):
    schema_version: str = "1.0.0"
    tier: Tier
    capture_id: str
    rooms: list[RoomGeometry]
    adjacencies: list[Adjacency] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class LidarFrame:
    """One Stray Scanner frame. Why: keep pose, K, and paths together for backprojection."""

    frame_id: str
    timestamp_s: float
    T_wc: np.ndarray
    fx: float
    fy: float
    cx: float
    cy: float
    depth_path: Path
    confidence_path: Path


@dataclass(frozen=True)
class LidarCapture:
    root: Path
    camera_matrix: np.ndarray
    frames: tuple[LidarFrame, ...]
    rgb_size: tuple[int, int]


@dataclass(frozen=True)
class PhotoRoom:
    """One room's stills. Why: the photo contract is per-room folders, not a single dump."""

    room_id: str
    images: tuple[Path, ...]


@dataclass(frozen=True)
class PhotoCapture:
    root: Path
    rooms: tuple[PhotoRoom, ...]


@dataclass(frozen=True)
class VideoRoom:
    """One room's handheld clip. Why: protocol is one mp4 per room, not a property-length walk."""

    room_id: str
    clip: Path


@dataclass(frozen=True)
class VideoCapture:
    root: Path
    rooms: tuple[VideoRoom, ...]


@dataclass
class PointCloud:
    xyz: np.ndarray
    confidence: np.ndarray | None = None


@dataclass
class Plane:
    normal: np.ndarray
    offset: float
    inlier_count: int
    rmse: float
    inlier_points: np.ndarray
    kind: Literal["floor", "ceiling", "wall", "unknown"] = "unknown"


@dataclass
class PlaneSet:
    floor: Plane
    ceiling: Plane | None
    walls: list[Plane]
    up: np.ndarray
    unused: list[Plane] = field(default_factory=list)
