"""Metric scale. LiDAR is already meters; photos use a reference door height."""

from __future__ import annotations

from floorplan.exceptions import EmptyCaptureError
from floorplan.models import PointCloud


def identity_scale(cloud: PointCloud) -> PointCloud:
    """LiDAR depth is millimeters converted to meters at backprojection. No scale guess."""

    return cloud


def scale_from_door_height(unscaled_height: float, door_height_m: float) -> float:
    """s = door_m / reconstructed_door. Why: no depth, so the door is the meter stick."""

    if unscaled_height <= 1e-6:
        raise EmptyCaptureError("Door height in the reconstruction is degenerate.")
    return float(door_height_m / unscaled_height)


def recover_scale_from_reference(cloud: PointCloud, reference_height_m: float) -> PointCloud:
    """Scale an arbitrary-unit cloud so a measured vertical equals the reference."""

    raise EmptyCaptureError(
        f"Point-cloud reference scale needs a detected vertical of {reference_height_m} m; "
        "photo-tier uses scale_from_door_height on the vanishing reconstruction instead."
    )
