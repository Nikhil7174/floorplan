"""Video-tier: midpoint-biased keyframes + photo recon + explicit consensus guards."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from scipy.stats import beta

from floorplan.config import AppConfig
from floorplan.models import Opening, VideoRoom
from floorplan.reconstruction.consensus import (
    SaneFrame,
    consensus_mode as shared_consensus_mode,
    median_box,
)
from floorplan.reconstruction.sfm import reconstruct_from_bgr, _fallback_box

logger = logging.getLogger(__name__)


def sample_keyframe_indices(
    frame_count: int,
    config: AppConfig,
) -> list[int]:
    """Index list, biased toward mid-clip. Why: the walker is more often centered there."""

    if frame_count <= 0:
        return []
    count = min(config.video.keyframe_count, frame_count)
    lo = int(frame_count * config.video.skip_start_frac)
    hi = int(frame_count * (1.0 - config.video.skip_end_frac))
    if hi <= lo:
        lo, hi = 0, frame_count
    span = max(hi - lo, 1)
    u = (np.arange(count) + 0.5) / count
    if config.video.midpoint_bias:
        frac = beta.ppf(u, 2.2, 2.2)
    else:
        frac = u
    idxs = np.clip((lo + frac * span).astype(int), 0, frame_count - 1)
    return sorted(set(int(i) for i in idxs))


def extract_keyframes(clip: Path, config: AppConfig) -> list[tuple[int, np.ndarray]]:
    """Decode selected frames. HEVC failure is logged so the protocol can say H.264."""

    cap = cv2.VideoCapture(str(clip))
    if not cap.isOpened():
        logger.error(
            "Could not open %s. Re-export as H.264 (iPhone: Camera → Formats → Most Compatible).",
            clip,
        )
        return []
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    frames: list[tuple[int, np.ndarray]] = []
    for idx in sample_keyframe_indices(n, config):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, image = cap.read()
        if ok and image is not None:
            frames.append((idx, image))
    cap.release()
    logger.info("Sampled %d keyframes from %s (%d total)", len(frames), clip.name, n)
    return frames


def reconstruct_video_room(
    room: VideoRoom,
    config: AppConfig,
) -> tuple[np.ndarray, list[list[Opening]], float, str, list[str]]:
    """Consensus only when every sane keyframe has the same wall count."""

    frames = extract_keyframes(room.clip, config)
    sane: list[SaneFrame] = []
    for idx, image in frames:
        result = reconstruct_from_bgr(image, config, label=f"{room.clip.name}:{idx}")
        if result is None:
            continue
        score, polygon, openings, ceiling, reason, extra = result
        sane.append(
            SaneFrame(
                score=score,
                polygon=polygon,
                openings=openings,
                ceiling_m=ceiling,
                reason=reason,
                extra=extra,
            )
        )
    mode = consensus_mode(sane, config)
    wall_counts = {len(frame.polygon) for frame in sane}
    if mode == "consensus":
        logger.info(
            "Video consensus on %s: %d frames, %d walls",
            room.room_id,
            len(sane),
            next(iter(wall_counts)),
        )
        return median_box(
            sane,
            extra_warnings=sane[0].extra,
            reason="video_keyframe_consensus",
            tag="video",
        )
    if mode == "thin":
        logger.warning(
            "Video thin consensus on %s: sane=%d wall_counts=%s",
            room.room_id,
            len(sane),
            sorted(wall_counts),
        )
        best = max(sane, key=lambda item: item.score)
        warnings = list(best.extra) + ["video_thin_consensus"]
        if len(wall_counts) > 1 and len(sane) >= config.video.min_sane_frames:
            warnings.append("video_wall_count_mismatch")
        return best.polygon, best.openings, best.ceiling_m, "video_thin_consensus", warnings
    logger.warning("No sane video keyframes for %s; fallback prior", room.room_id)
    polygon = _fallback_box(config)
    return (
        polygon,
        [[] for _ in range(len(polygon))],
        config.photos.ceiling_prior_m,
        "fallback_prior",
        ["manhattan_vp_failed", "video_no_sane_keyframes"],
    )


def consensus_mode(sane: list[SaneFrame], config: AppConfig) -> str:
    """Video wrapper: same wall-count guard as photos, video min_sane_frames."""

    return shared_consensus_mode(sane, config.video.min_sane_frames)
