"""Orchestrate ingest → reconstruct → score → validate for one capture folder."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from floorplan.config import AppConfig
from floorplan.exceptions import UnsupportedTierError
from floorplan.ingestion.detect import detect_tier
from floorplan.ingestion.lidar import backproject, ingest_lidar
from floorplan.ingestion.photos import ingest_photos
from floorplan.ingestion.video import ingest_video
from floorplan.models import PropertyPlan
from floorplan.reconstruction.plane_fitting import (
    classify_planes,
    extract_planes,
    recover_vertical_walls,
)
from floorplan.reconstruction.room import build_room, build_room_from_polygon
from floorplan.reconstruction.scale_recovery import identity_scale
from floorplan.reconstruction.sfm import reconstruct_photo_room
from floorplan.reconstruction.video import reconstruct_video_room
from floorplan.schema.validate import validate_plan
from floorplan.stitching.multi_room import stitch_rooms

logger = logging.getLogger(__name__)


def process_capture(capture_dir: Path, config: AppConfig) -> PropertyPlan:
    """One capture in, one PropertyPlan out."""

    capture_id = capture_dir.name
    capture_dir = capture_dir.resolve()
    tier = detect_tier(capture_dir)
    logger.info("Stage ingest: tier=%s path=%s", tier, capture_dir)
    if tier == "photos":
        plan = _process_photos(capture_dir, capture_id, config)
    elif tier == "lidar":
        plan = _process_lidar(capture_dir, capture_id, config)
    elif tier == "video":
        plan = _process_video(capture_dir, capture_id, config)
    else:
        raise UnsupportedTierError(f"Unsupported tier '{tier}'")
    validate_plan(plan)
    logger.info(
        "Stage output: rooms=%d adjacencies=%d",
        len(plan.rooms),
        len(plan.adjacencies),
    )
    return plan


def _process_lidar(capture_dir: Path, capture_id: str, config: AppConfig) -> PropertyPlan:
    capture = ingest_lidar(capture_dir, config)
    cloud = identity_scale(backproject(capture, config))
    logger.info("Stage reconstruction: %d points", len(cloud.xyz))
    planes_raw = extract_planes(cloud, config)
    origins = np.stack([frame.T_wc[:3, 3] for frame in capture.frames])
    planes = classify_planes(planes_raw, origins, config)
    if len(planes.walls) < 3:
        planes = recover_vertical_walls(cloud.xyz, planes, config)
    room = build_room(planes, config, room_id=capture_id, tier="lidar")
    return PropertyPlan(
        tier="lidar",
        capture_id=capture_id,
        rooms=[room],
        adjacencies=[],
        warnings=list(room.warnings),
    )


def _process_photos(capture_dir: Path, capture_id: str, config: AppConfig) -> PropertyPlan:
    capture = ingest_photos(capture_dir, config)
    rooms = []
    for photo_room in capture.rooms:
        logger.info("Stage reconstruction: photos room=%s n=%d", photo_room.room_id, len(photo_room.images))
        polygon, openings, ceiling, reason, warnings = reconstruct_photo_room(photo_room, config)
        rooms.append(
            build_room_from_polygon(
                polygon,
                config,
                room_id=photo_room.room_id,
                tier="photos",
                ceiling_m=ceiling,
                openings_by_wall=openings,
                length_frac=_interval_frac(reason, config),
                reason=reason,
                warnings=warnings,
            )
        )
    return stitch_rooms(rooms, capture_id, "photos")


def _process_video(capture_dir: Path, capture_id: str, config: AppConfig) -> PropertyPlan:
    capture = ingest_video(capture_dir)
    rooms = []
    for video_room in capture.rooms:
        logger.info("Stage reconstruction: video room=%s clip=%s", video_room.room_id, video_room.clip.name)
        polygon, openings, ceiling, reason, warnings = reconstruct_video_room(video_room, config)
        rooms.append(
            build_room_from_polygon(
                polygon,
                config,
                room_id=video_room.room_id,
                tier="video",
                ceiling_m=ceiling,
                openings_by_wall=openings,
                length_frac=_interval_frac(reason, config),
                reason=reason,
                warnings=warnings,
            )
        )
    return stitch_rooms(rooms, capture_id, "video")


def _interval_frac(reason: str, config: AppConfig) -> float:
    if reason == "video_keyframe_consensus":
        return config.video.consensus_frac
    if reason == "video_thin_consensus":
        return config.video.thin_frac
    if reason.startswith("door_height"):
        return config.photos.door_scale_frac
    if "fallback" in reason:
        return config.photos.failed_scale_frac
    if "prior" in reason:
        return config.photos.prior_scale_frac
    return config.photos.prior_scale_frac
