"""Conservative 2-class damage: stain (compact discoloration) and crack (long thin run).

Draft: thresholds prefer false negatives. Precision is not benchmarked.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from floorplan.config import AppConfig
from floorplan.models import DamageRegion

logger = logging.getLogger(__name__)

DRAFT_WARNING = "damage_detector_draft:precision_not_benchmarked"


def detect_damage(
    images: list[Path] | list[np.ndarray],
    config: AppConfig,
    wall_id: str | None = None,
) -> tuple[list[DamageRegion], list[str]]:
    """Return regions plus warnings. Empty regions is 'none found', not 'room is clean'."""

    warnings = [DRAFT_WARNING]
    if not config.damage.enabled:
        warnings.append("damage_disabled")
        return [], warnings
    regions: list[DamageRegion] = []
    for item in images:
        if isinstance(item, Path):
            image = cv2.imread(str(item), cv2.IMREAD_COLOR)
            name = item.name
        else:
            image = item
            name = "array"
        if image is None:
            logger.warning("Could not read damage still %s", name)
            continue
        regions.extend(_detect_stains(image, config, name, wall_id))
        regions.extend(_detect_cracks(image, config, name, wall_id))
    if not regions:
        warnings.append("no_damage_detected")
        logger.info("Damage detector: no stain/crack passed conservative gates")
    else:
        logger.info("Damage detector: %d region(s) (draft)", len(regions))
    return regions, warnings


def _detect_stains(
    image: np.ndarray,
    config: AppConfig,
    image_name: str,
    wall_id: str | None,
) -> list[DamageRegion]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    # Saturated, not-too-bright patch vs a pale wall.
    mask = (sat >= config.damage.stain_sat_min) & (val < 200) & (val > 30)
    mask_u8 = mask.astype(np.uint8) * 255
    mask_u8 = cv2.medianBlur(mask_u8, 5)
    n_pix = image.shape[0] * image.shape[1]
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out: list[DamageRegion] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        frac = area / max(n_pix, 1)
        if frac < config.damage.stain_min_area_frac or frac > config.damage.stain_max_area_frac:
            continue
        _x, _y, w, h = cv2.boundingRect(contour)
        if max(w, h) / max(min(w, h), 1) > 6:
            continue
        out.append(
            DamageRegion(
                kind="stain",
                wall_id=wall_id,
                t0_m=0.0,
                t1_m=0.0,
                area_frac=frac,
                confidence=min(0.55, 0.25 + 8.0 * frac),
                reason="hsv_stain_blob",
                image_name=image_name,
            )
        )
    return out[:2]


def _detect_cracks(
    image: np.ndarray,
    config: AppConfig,
    image_name: str,
    wall_id: str | None,
) -> list[DamageRegion]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 80, 180)
    min_len = int(config.damage.crack_min_length_frac * max(gray.shape))
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180.0,
        threshold=60,
        minLineLength=min_len,
        maxLineGap=6,
    )
    if lines is None:
        return []
    out: list[DamageRegion] = []
    long_edge = max(gray.shape)
    for row in lines:
        x1, y1, x2, y2 = [int(v) for v in row.reshape(-1)[:4]]
        length = float(np.hypot(x2 - x1, y2 - y1))
        # Thickness proxy: a Hough line is already thin; reject near-horizontal
        # furniture edges by requiring some vertical component.
        if abs(x2 - x1) > 0 and abs(y2 - y1) / max(abs(x2 - x1), 1) < 0.15:
            continue
        aspect = length / max(config.damage.crack_max_width_px, 1)
        if aspect < config.damage.crack_min_aspect:
            continue
        frac = length / long_edge
        out.append(
            DamageRegion(
                kind="crack",
                wall_id=wall_id,
                t0_m=0.0,
                t1_m=0.0,
                area_frac=frac * (config.damage.crack_max_width_px / long_edge),
                confidence=min(0.50, 0.20 + 0.4 * frac),
                reason="hough_thin_run",
                image_name=image_name,
            )
        )
    return out[:1]
