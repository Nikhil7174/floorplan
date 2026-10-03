"""Map evidence quality to interval width. Thin data must widen, never tighten."""

from __future__ import annotations

from floorplan.config import ConfidenceSettings
from floorplan.models import ConfidenceInterval


def interval_from_evidence(
    value: float,
    residual_rmse: float,
    inlier_count: int,
    base_half: float,
    settings: ConfidenceSettings,
    unit: str,
    reason: str,
) -> ConfidenceInterval:
    """Grow half-width from residual and sparsity. Why: confident garbage is capped."""

    sparse = 1.0 / max(inlier_count, 1)
    half = base_half + settings.residual_gain * residual_rmse + settings.sparse_gain * (sparse * 200.0)
    if inlier_count < 150:
        half *= 1.8
        reason = f"{reason}+sparse"
    half = abs(half)
    return ConfidenceInterval(
        value=float(value),
        lo=float(value - half),
        hi=float(value + half),
        unit=unit,
        reason=reason,
    )


def interval_calibrated(
    value: float,
    frac: float,
    unit: str,
    reason: str,
    min_half: float = 0.04,
) -> ConfidenceInterval:
    """Half-width is a fraction of the value. Why: the photo gate is ±8%, not 1.5 cm."""

    half = max(abs(value) * abs(frac), min_half)
    lo = float(value - half)
    # Lengths and areas must not go negative; widen upward instead.
    if lo < 0 and unit in {"m", "m2"}:
        lo = 0.0
    return ConfidenceInterval(
        value=float(value),
        lo=lo,
        hi=float(value + half),
        unit=unit,
        reason=reason,
    )


def missing_ceiling_interval(settings: ConfidenceSettings) -> ConfidenceInterval:
    """Prior height with a wide band. Why: floor-only scans must not invent 1.5cm."""

    value = settings.missing_ceiling_prior_m
    half = settings.missing_ceiling_half_m
    return ConfidenceInterval(
        value=value,
        lo=value - half,
        hi=value + half,
        unit="m",
        reason="no_ceiling_returns",
    )
