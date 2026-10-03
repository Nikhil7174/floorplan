"""Manhattan vanishing points from stills. Why: 2–8 photos are too thin for COLMAP."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class LineSegment:
    x1: float
    y1: float
    x2: float
    y2: float

    def as_array(self) -> np.ndarray:
        return np.array([self.x1, self.y1, self.x2, self.y2], dtype=np.float64)

    @property
    def length(self) -> float:
        return float(np.hypot(self.x2 - self.x1, self.y2 - self.y1))

    @property
    def midpoint(self) -> np.ndarray:
        return np.array([(self.x1 + self.x2) * 0.5, (self.y1 + self.y2) * 0.5])

    def homogeneous(self) -> np.ndarray:
        return np.cross(
            np.array([self.x1, self.y1, 1.0]),
            np.array([self.x2, self.y2, 1.0]),
        )


@dataclass
class VanishingFrame:
    vps: tuple[np.ndarray, np.ndarray, np.ndarray]
    vertical_index: int
    focal: float
    principal: np.ndarray
    inlier_counts: tuple[int, int, int]
    segments: list[LineSegment]


def detect_segments(gray: np.ndarray, min_length: float) -> list[LineSegment]:
    """LSD if present, otherwise Canny+Hough. Why: opencv-python often ships without LSD."""

    segs: list[LineSegment] = []
    if hasattr(cv2, "createLineSegmentDetector"):
        try:
            lsd = cv2.createLineSegmentDetector()
            detected = lsd.detect(gray)[0]
            if detected is not None:
                for row in detected:
                    x1, y1, x2, y2 = [float(v) for v in row.reshape(-1)[:4]]
                    seg = LineSegment(x1, y1, x2, y2)
                    if seg.length >= min_length:
                        segs.append(seg)
        except cv2.error:
            segs = []
    if len(segs) >= 8:
        return segs
    edges = cv2.Canny(gray, 50, 150)
    hough = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180.0,
        threshold=50,
        minLineLength=int(min_length),
        maxLineGap=12,
    )
    if hough is None:
        return segs
    for row in hough:
        x1, y1, x2, y2 = [float(v) for v in row.reshape(-1)[:4]]
        seg = LineSegment(x1, y1, x2, y2)
        if seg.length >= min_length:
            segs.append(seg)
    return segs


def fit_vanishing_points(
    segments: list[LineSegment],
    rng: np.random.Generator,
    iterations: int,
    inlier_px: float,
) -> list[tuple[np.ndarray, list[int]]]:
    """Sequential RANSAC of line intersections. Distant VPs (near-parallel lines) are allowed."""

    remaining = list(range(len(segments)))
    found: list[tuple[np.ndarray, list[int]]] = []
    for _ in range(3):
        if len(remaining) < 2:
            break
        vp, inliers = _fit_one_vp(segments, remaining, rng, iterations, inlier_px)
        if vp is None or len(inliers) < 3:
            break
        found.append((vp, inliers))
        inlier_set = set(inliers)
        remaining = [i for i in remaining if i not in inlier_set]
    return found


def assign_vertical(
    vps: list[np.ndarray],
    segments: list[LineSegment],
    membership: list[list[int]],
    principal: np.ndarray,
) -> int:
    """Vertical VP is the one whose inlier segments are most image-vertical."""

    best_i = 0
    best_score = -1.0
    for i, members in enumerate(membership):
        if not members:
            continue
        verticalness = []
        for idx in members:
            dx = segments[idx].x2 - segments[idx].x1
            dy = segments[idx].y2 - segments[idx].y1
            verticalness.append(abs(dy) / (abs(dx) + 1e-6))
        score = float(np.median(verticalness))
        # Prefer a VP near the image x-center as well (typical interior photo).
        score += 0.15 * (1.0 / (1.0 + abs(vps[i][0] - principal[0]) / 200.0))
        if score > best_score:
            best_score = score
            best_i = i
    return best_i


def focal_from_orthogonal_vps(vp_a: np.ndarray, vp_b: np.ndarray, principal: np.ndarray) -> float | None:
    """f^2 = - (va-p)·(vb-p) for two orthogonal vanishing points."""

    f2 = -float((vp_a - principal) @ (vp_b - principal))
    if f2 <= 100.0:
        return None
    return float(np.sqrt(f2))


def _fit_one_vp(
    segments: list[LineSegment],
    indices: list[int],
    rng: np.random.Generator,
    iterations: int,
    inlier_px: float,
) -> tuple[np.ndarray | None, list[int]]:
    best_vp: np.ndarray | None = None
    best_inliers: list[int] = []
    n = len(indices)
    if n < 2:
        return None, []
    for _ in range(iterations):
        i, j = rng.choice(n, size=2, replace=False)
        vp = _intersect(segments[indices[i]], segments[indices[j]])
        if vp is None:
            continue
        inliers = [indices[k] for k in range(n) if _point_line_distance(vp, segments[indices[k]]) <= inlier_px]
        if len(inliers) > len(best_inliers):
            best_inliers = inliers
            best_vp = vp
    return best_vp, best_inliers


def _intersect(a: LineSegment, b: LineSegment) -> np.ndarray | None:
    p = np.cross(a.homogeneous(), b.homogeneous())
    if abs(p[2]) < 1e-10:
        return None
    point = p[:2] / p[2]
    if not np.all(np.isfinite(point)):
        return None
    if np.linalg.norm(point) > 1e7:
        return None
    return point


def _point_line_distance(point: np.ndarray, seg: LineSegment) -> float:
    line = seg.homogeneous()
    return abs(float(line @ np.array([point[0], point[1], 1.0]))) / (
        np.hypot(line[0], line[1]) + 1e-12
    )
