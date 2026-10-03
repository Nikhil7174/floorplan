"""Photo-tier ingest: one folder of stills, or one subfolder per room."""

from __future__ import annotations

import logging
from pathlib import Path

from floorplan.config import AppConfig
from floorplan.exceptions import EmptyCaptureError
from floorplan.models import PhotoCapture, PhotoRoom

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}


def list_images(folder: Path) -> list[Path]:
    """Images directly in this folder, not in depth/confidence dumps."""

    if not folder.is_dir():
        return []
    found = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    return sorted(found)


def ingest_photos(capture_dir: Path, config: AppConfig) -> PhotoCapture:
    """Collect 2–8 stills per room. Why: the walk-in test hands per-room photo folders."""

    capture_dir = capture_dir.resolve()
    rooms = _rooms_from_tree(capture_dir, config)
    if not rooms:
        raise EmptyCaptureError(
            f"No photo rooms in {capture_dir}. "
            "Need 2+ stills at the top level, or one subfolder of stills per room."
        )
    logger.info("Ingested %d photo room(s) from %s", len(rooms), capture_dir.name)
    return PhotoCapture(root=capture_dir, rooms=tuple(rooms))


def _rooms_from_tree(capture_dir: Path, config: AppConfig) -> list[PhotoRoom]:
    subdirs = sorted(
        path
        for path in capture_dir.iterdir()
        if path.is_dir() and path.name not in {"depth", "confidence", "distortion"}
    )
    nested = []
    for folder in subdirs:
        images = list_images(folder)
        if len(images) >= 1:
            nested.append(_clip_room(folder.name, images, config))
    if nested:
        return nested
    top = list_images(capture_dir)
    if len(top) >= 1:
        return [_clip_room(capture_dir.name, top, config)]
    return []


def _clip_room(room_id: str, images: list[Path], config: AppConfig) -> PhotoRoom:
    use = images[: config.photos.max_use_images]
    if len(images) > config.photos.max_use_images:
        logger.warning(
            "Room %s has %d stills; using the first %d",
            room_id,
            len(images),
            config.photos.max_use_images,
        )
    if len(use) < config.photos.min_images:
        logger.warning(
            "Room %s has %d stills (protocol asks for %d–%d); intervals will widen",
            room_id,
            len(use),
            config.photos.min_images,
            config.photos.max_use_images,
        )
    return PhotoRoom(room_id=room_id, images=tuple(use))
