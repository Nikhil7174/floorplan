"""Stray Scanner ingest and metric backprojection."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from floorplan.config import AppConfig
from floorplan.exceptions import EmptyCaptureError
from floorplan.models import LidarCapture, LidarFrame, PointCloud

logger = logging.getLogger(__name__)

_COMMON_RGB = (
    (1920, 1440),
    (1440, 1920),
    (1920, 1080),
    (1080, 1920),
    (1280, 960),
    (960, 1280),
)


def ingest_lidar(capture_dir: Path, config: AppConfig) -> LidarCapture:
    """Parse a Stray Scanner folder into typed frames, then subsample.

    Why: odometry already carries per-frame K; camera_matrix.csv is legacy fallback.
    """

    capture_dir = capture_dir.resolve()
    odom_path = capture_dir / "odometry.csv"
    depth_dir = capture_dir / "depth"
    conf_dir = capture_dir / "confidence"
    if not odom_path.is_file() or not depth_dir.is_dir():
        raise EmptyCaptureError(f"Not a Stray Scanner capture: {capture_dir}")

    camera_matrix = _read_camera_matrix(capture_dir / "camera_matrix.csv")
    frames: list[LidarFrame] = []
    with odom_path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        reader.fieldnames = [name.strip() for name in (reader.fieldnames or [])]
        for raw in reader:
            row = {k.strip(): (v.strip() if v is not None else "") for k, v in raw.items()}
            frame_id = row["frame"].zfill(6)
            depth_path = depth_dir / f"{frame_id}.png"
            if not depth_path.is_file():
                continue
            conf_path = conf_dir / f"{frame_id}.png"
            T_wc = _pose_matrix(row)
            fx, fy, cx, cy = _intrinsics(row, camera_matrix)
            frames.append(
                LidarFrame(
                    frame_id=frame_id,
                    timestamp_s=float(row["timestamp"]),
                    T_wc=T_wc,
                    fx=fx,
                    fy=fy,
                    cx=cx,
                    cy=cy,
                    depth_path=depth_path,
                    confidence_path=conf_path if conf_path.is_file() else depth_path,
                )
            )

    if not frames:
        raise EmptyCaptureError(f"No depth frames matched odometry in {capture_dir}")

    stride = max(1, config.lidar.frame_stride)
    subsampled = tuple(frames[::stride])
    rgb_size = _infer_rgb_size(subsampled[0], config.lidar.rgb_size)
    logger.info(
        "Ingested %d / %d frames from %s (stride=%d)",
        len(subsampled),
        len(frames),
        capture_dir.name,
        stride,
    )
    return LidarCapture(
        root=capture_dir,
        camera_matrix=camera_matrix,
        frames=subsampled,
        rgb_size=rgb_size,
    )


def backproject(capture: LidarCapture, config: AppConfig) -> PointCloud:
    """Lift depth pixels to world XYZ. Metric because LiDAR depth is millimeters."""

    chunks: list[np.ndarray] = []
    pixel_stride = max(1, config.lidar.pixel_stride)
    rgb_w, rgb_h = capture.rgb_size
    for frame in capture.frames:
        depth = cv2.imread(str(frame.depth_path), cv2.IMREAD_UNCHANGED)
        if depth is None:
            logger.warning("Skipped unreadable depth %s", frame.depth_path)
            continue
        if depth.ndim == 3:
            depth = depth[:, :, 0]
        confidence = _read_confidence(frame.confidence_path, depth.shape)
        dh, dw = depth.shape[:2]
        scale_x = dw / rgb_w
        scale_y = dh / rgb_h
        fx = frame.fx * scale_x
        fy = frame.fy * scale_y
        cx = frame.cx * scale_x
        cy = frame.cy * scale_y

        vs = np.arange(0, dh, pixel_stride)
        us = np.arange(0, dw, pixel_stride)
        uu, vv = np.meshgrid(us, vs)
        z_mm = depth[vv, uu].astype(np.float32)
        conf = confidence[vv, uu]
        z_m = z_mm / 1000.0
        valid = (
            (z_m >= config.lidar.min_depth_m)
            & (z_m <= config.lidar.max_depth_m)
            & (conf >= config.lidar.min_confidence)
        )
        if not np.any(valid):
            continue
        u = uu[valid].astype(np.float32)
        v = vv[valid].astype(np.float32)
        z = z_m[valid]
        x = (u - cx) * z / fx
        y = (v - cy) * z / fy
        cam = np.stack([x, y, z], axis=1)
        R = frame.T_wc[:3, :3]
        t = frame.T_wc[:3, 3]
        world = cam @ R.T + t
        chunks.append(world.astype(np.float32))

    if not chunks:
        raise EmptyCaptureError("Backprojection produced no points after confidence/depth filters.")
    xyz = np.concatenate(chunks, axis=0)
    xyz = _voxel_downsample(xyz, config.lidar.voxel_m)
    logger.info("Point cloud: %d points after voxel=%.3fm", len(xyz), config.lidar.voxel_m)
    return PointCloud(xyz=xyz)


def _read_camera_matrix(path: Path) -> np.ndarray:
    if not path.is_file():
        return np.eye(3, dtype=np.float64)
    return np.loadtxt(path, delimiter=",", dtype=np.float64).reshape(3, 3)


def _pose_matrix(row: dict[str, str]) -> np.ndarray:
    quat = np.array(
        [float(row["qx"]), float(row["qy"]), float(row["qz"]), float(row["qw"])],
        dtype=np.float64,
    )
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = Rotation.from_quat(quat).as_matrix()
    T[:3, 3] = [float(row["x"]), float(row["y"]), float(row["z"])]
    return T


def _intrinsics(row: dict[str, str], camera_matrix: np.ndarray) -> tuple[float, float, float, float]:
    if row.get("fx"):
        return float(row["fx"]), float(row["fy"]), float(row["cx"]), float(row["cy"])
    return (
        float(camera_matrix[0, 0]),
        float(camera_matrix[1, 1]),
        float(camera_matrix[0, 2]),
        float(camera_matrix[1, 2]),
    )


def _infer_rgb_size(frame: LidarFrame, fallback: tuple[int, int]) -> tuple[int, int]:
    target = np.array([2.0 * frame.cx, 2.0 * frame.cy])
    best = fallback
    best_err = float("inf")
    for size in (fallback, *_COMMON_RGB):
        err = float(np.linalg.norm(np.array(size, dtype=np.float64) - target))
        if err < best_err:
            best_err = err
            best = size
    return best


def _read_confidence(path: Path, shape: tuple[int, ...]) -> np.ndarray:
    if not path.is_file() or path.suffix.lower() != ".png":
        return np.full(shape, 2, dtype=np.uint8)
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        return np.full(shape, 2, dtype=np.uint8)
    if image.ndim == 3:
        image = image[:, :, 0]
    if image.shape[:2] != shape[:2]:
        image = cv2.resize(image, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return image


def _voxel_downsample(xyz: np.ndarray, voxel_m: float) -> np.ndarray:
    if voxel_m <= 0 or len(xyz) == 0:
        return xyz
    keys = np.floor(xyz / voxel_m).astype(np.int32)
    _, index = np.unique(keys, axis=0, return_index=True)
    return xyz[np.sort(index)]
