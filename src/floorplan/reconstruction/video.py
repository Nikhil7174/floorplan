"""Video-tier: midpoint-biased keyframes + photo recon + explicit consensus guards."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from scipy.stats import beta

from floorplan.config import AppConfig
from floorplan.models import Opening, VideoRoom
from floorplan.reconstruction.sfm import reconstruct_from_bgr, _fallback_box

logger = logging.getLogger(__name__)


@dataclass
class SaneFrame:
    score: float
    polygon: np.ndarray
    openings: list[list[Opening]]
    ceiling_m: float
    reason: str
    extra: list[str]


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
        return _median_box(sane, config, extra_warnings=sane[0].extra)
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
    """Explicit branch: mismatched wall counts never enter a median.

    Why: a naive index-wise median on 3-wall vs 4-wall polygons is silent garbage.
    """

    if not sane:
        return "fallback"
    counts = {len(frame.polygon) for frame in sane}
    if len(sane) >= config.video.min_sane_frames and len(counts) == 1:
        return "consensus"
    return "thin"


def _median_box(
    frames: list[SaneFrame],
    config: AppConfig,
    extra_warnings: list[str],
) -> tuple[np.ndarray, list[list[Opening]], float, str, list[str]]:
    """Median width/depth AABB. Why: vertex-index median is garbage if order differs."""

    widths: list[float] = []
    depths: list[float] = []
    ceilings: list[float] = []
    for frame in frames:
        width, depth = _aabb_wh(frame.polygon)
        widths.append(width)
        depths.append(depth)
        ceilings.append(frame.ceiling_m)
    width = float(np.median(widths))
    depth = float(np.median(depths))
    ceiling = float(np.median(ceilings))
    polygon = np.array(
        [[0.0, 0.0], [width, 0.0], [width, depth], [0.0, depth]],
        dtype=np.float64,
    )
    best = max(frames, key=lambda item: item.score)
    openings = best.openings if len(best.openings) == 4 else [[] for _ in range(4)]
    warnings = list(extra_warnings) + [f"video_consensus_n={len(frames)}"]
    return polygon, openings, ceiling, "video_keyframe_consensus", warnings


def _aabb_wh(polygon: np.ndarray) -> tuple[float, float]:
    xs = polygon[:, 0]
    ys = polygon[:, 1]
    return float(xs.max() - xs.min()), float(ys.max() - ys.min())
