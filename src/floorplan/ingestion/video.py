"""Video-tier ingest: one clip per room, or one top-level mp4/mov."""

from __future__ import annotations

import logging
from pathlib import Path

from floorplan.exceptions import EmptyCaptureError
from floorplan.models import VideoCapture, VideoRoom

logger = logging.getLogger(__name__)

VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v"}


def list_videos(folder: Path) -> list[Path]:
    """Clips directly in this folder, not recursive."""

    if not folder.is_dir():
        return []
    found = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    ]
    return sorted(found)


def ingest_video(capture_dir: Path) -> VideoCapture:
    """Collect one clip per room. Why: a property-length walk needs room cuts we will not invent."""

    capture_dir = capture_dir.resolve()
    rooms = _rooms_from_tree(capture_dir)
    if not rooms:
        raise EmptyCaptureError(
            f"No video rooms in {capture_dir}. "
            "Need a .mp4/.mov at the top level, or one clip per room subfolder."
        )
    logger.info("Ingested %d video room(s) from %s", len(rooms), capture_dir.name)
    return VideoCapture(root=capture_dir, rooms=tuple(rooms))


def _rooms_from_tree(capture_dir: Path) -> list[VideoRoom]:
    nested: list[VideoRoom] = []
    for folder in sorted(p for p in capture_dir.iterdir() if p.is_dir()):
        clips = list_videos(folder)
        if clips:
            nested.append(VideoRoom(room_id=folder.name, clip=clips[0]))
            if len(clips) > 1:
                logger.warning("Room %s has %d clips; using %s", folder.name, len(clips), clips[0].name)
    if nested:
        return nested
    top = list_videos(capture_dir)
    if top:
        if len(top) > 1:
            logger.warning("Multiple top-level clips; using %s", top[0].name)
        return [VideoRoom(room_id=capture_dir.name, clip=top[0])]
    return []
