"""Decide which tier a capture folder is. Why: one CLI entry, no user flag required."""

from __future__ import annotations

from pathlib import Path

from floorplan.exceptions import EmptyCaptureError
from floorplan.models import Tier


def detect_tier(capture_dir: Path) -> Tier:
    """Classify a folder as lidar, video, or photos from its files."""

    if not capture_dir.is_dir():
        raise EmptyCaptureError(f"Capture path is not a directory: {capture_dir}")
    has_odom = (capture_dir / "odometry.csv").is_file()
    has_depth = (capture_dir / "depth").is_dir()
    if has_odom and has_depth:
        return "lidar"
    from floorplan.ingestion.photos import list_images
    from floorplan.ingestion.video import list_videos

    room_dirs = [
        path
        for path in capture_dir.iterdir()
        if path.is_dir()
        and path.name not in {"depth", "confidence", "distortion"}
        and list_images(path)
    ]
    if room_dirs or len(list_images(capture_dir)) >= 1:
        return "photos"
    video_dirs = [
        path
        for path in capture_dir.iterdir()
        if path.is_dir() and list_videos(path)
    ]
    if video_dirs or list_videos(capture_dir):
        return "video"
    raise EmptyCaptureError(
        f"Could not detect a capture tier in {capture_dir}. "
        "LiDAR needs odometry.csv and depth/; photos need stills or per-room folders; "
        "video needs a .mp4/.mov at the top level or one clip per room folder."
    )
