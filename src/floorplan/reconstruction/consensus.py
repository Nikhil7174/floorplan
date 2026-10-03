"""Shared multi-view median. Why: photo stills and video keyframes use the same rule."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from floorplan.models import Opening


@dataclass
class SaneFrame:
    score: float
    polygon: np.ndarray
    openings: list[list[Opening]]
    ceiling_m: float
    reason: str
    extra: list[str]


def consensus_mode(sane: list[SaneFrame], min_sane: int) -> str:
    """Explicit branch: mismatched wall counts never enter a median.

    Why: a naive index-wise median on 3-wall vs 4-wall polygons is silent garbage.
    """

    if not sane:
        return "fallback"
    counts = {len(frame.polygon) for frame in sane}
    if len(sane) >= min_sane and len(counts) == 1:
        return "consensus"
    return "thin"


def median_box(
    frames: list[SaneFrame],
    extra_warnings: list[str],
    reason: str,
    tag: str,
) -> tuple[np.ndarray, list[list[Opening]], float, str, list[str]]:
    """Median width/depth AABB. Why: vertex-index median is garbage if order differs."""

    widths: list[float] = []
    depths: list[float] = []
    ceilings: list[float] = []
    for frame in frames:
        width, depth = aabb_wh(frame.polygon)
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
    warnings = list(extra_warnings) + [f"{tag}_consensus_n={len(frames)}"]
    return polygon, openings, ceiling, reason, warnings


def aabb_wh(polygon: np.ndarray) -> tuple[float, float]:
    xs = polygon[:, 0]
    ys = polygon[:, 1]
    return float(xs.max() - xs.min()), float(ys.max() - ys.min())
