"""Named failures at stage boundaries. Why: silent bad geometry is a scored miss."""


class FloorplanError(Exception):
    """Base error for the graded pipeline."""


class EmptyCaptureError(FloorplanError):
    """Capture folder has no usable frames or depth."""


class UnsupportedTierError(FloorplanError):
    """This increment only runs the LiDAR path."""


class NoFloorPlaneError(FloorplanError):
    """RANSAC found no floor; cannot project walls to a plan."""


class InsufficientPlanesError(FloorplanError):
    """Fewer than three walls after merging; cannot close a room polygon."""


class SchemaValidationError(FloorplanError):
    """Output JSON failed our internal PropertyPlan schema."""
