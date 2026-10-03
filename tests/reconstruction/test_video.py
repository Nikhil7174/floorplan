from pathlib import Path

import cv2
import numpy as np

from floorplan.config import AppConfig
from floorplan.models import VideoRoom
from floorplan.pipeline import process_capture
from floorplan.reconstruction.video import (
    SaneFrame,
    consensus_mode,
    reconstruct_video_room,
    sample_keyframe_indices,
)
from floorplan.schema.validate import validate_plan


def _write_mp4(path: Path, n: int = 12, size: tuple[int, int] = (128, 96)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (w, h))
    assert writer.isOpened(), f"could not open VideoWriter for {path}"
    blank = np.full((h, w, 3), 80, dtype=np.uint8)
    for _ in range(n):
        writer.write(blank)
    writer.release()


def _box(width: float, depth: float, n_walls: int = 4) -> np.ndarray:
    polygon = np.array(
        [[0.0, 0.0], [width, 0.0], [width, depth], [0.0, depth]],
        dtype=np.float64,
    )
    return polygon[:n_walls]


def _sane(n_walls: int = 4, score: float = 1.0, width: float = 5.0, depth: float = 4.0) -> SaneFrame:
    polygon = _box(width, depth, n_walls)
    return SaneFrame(
        score=score,
        polygon=polygon,
        openings=[[] for _ in range(n_walls)],
        ceiling_m=2.4,
        reason="door_height_2.032m",
        extra=[],
    )


def test_midpoint_bias_clusters_near_center() -> None:
    cfg = AppConfig()
    cfg.video.keyframe_count = 16
    idxs = sample_keyframe_indices(1000, cfg)
    mid = sum(1 for i in idxs if 333 <= i <= 666)
    edge = sum(1 for i in idxs if i < 150 or i > 850)
    assert mid > edge
    assert min(idxs) >= 100
    assert max(idxs) <= 899


def test_wall_count_mismatch_never_enters_consensus() -> None:
    cfg = AppConfig()
    cfg.video.min_sane_frames = 3
    assert consensus_mode([], cfg) == "fallback"
    assert consensus_mode([_sane(4), _sane(4)], cfg) == "thin"
    assert consensus_mode([_sane(4)] * 3, cfg) == "consensus"
    assert consensus_mode([_sane(4), _sane(3), _sane(4)], cfg) == "thin"


def test_video_pipeline_consensus_when_keyframes_agree(tmp_path: Path, monkeypatch) -> None:
    """Wrapper path: same wall count on enough frames → ±3%, not a mismatched median."""

    import floorplan.reconstruction.video as video_mod

    clip = tmp_path / "living" / "walk.mp4"
    _write_mp4(clip)
    polygon = _box(5.0, 4.0)

    def _agree(_image, _config, label: str = "frame"):
        return 2.0, polygon.copy(), [[], [], [], []], 2.4, "door_height_2.032m", ["door_detected"]

    monkeypatch.setattr(video_mod, "reconstruct_from_bgr", _agree)
    cfg = AppConfig()
    cfg.video.keyframe_count = 6
    plan = process_capture(tmp_path, cfg)
    validate_plan(plan)
    assert plan.tier == "video"
    wall = plan.rooms[0].walls[0].length_m
    assert wall.reason == "video_keyframe_consensus"
    span = (wall.hi - wall.lo) / max(wall.value, 1e-3)
    assert 0.029 <= span <= 0.061


def test_video_pipeline_mismatch_is_thin(tmp_path: Path, monkeypatch) -> None:
    import floorplan.reconstruction.video as video_mod

    clip = tmp_path / "walk.mp4"
    _write_mp4(clip)
    state = {"n": 0}

    def _mismatch(_image, _config, label: str = "frame"):
        state["n"] += 1
        if state["n"] % 2:
            return 3.0, _box(5.0, 4.0, 4), [[], [], [], []], 2.4, "door_height_2.032m", []
        return 1.0, _box(5.0, 4.0, 3), [[], [], []], 2.4, "door_height_2.032m", []

    monkeypatch.setattr(video_mod, "reconstruct_from_bgr", _mismatch)
    cfg = AppConfig()
    cfg.video.keyframe_count = 6
    plan = process_capture(tmp_path, cfg)
    validate_plan(plan)
    wall = plan.rooms[0].walls[0].length_m
    assert wall.reason == "video_thin_consensus"
    assert "video_wall_count_mismatch" in plan.rooms[0].warnings
    span = (wall.hi - wall.lo) / max(wall.value, 1e-3)
    assert span >= 0.07


def test_blur_clip_does_not_claim_three_percent(tmp_path: Path) -> None:
    noise = [
        np.random.default_rng(i).integers(0, 255, (96, 128, 3), dtype=np.uint8) for i in range(6)
    ]
    path = tmp_path / "blur.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (128, 96))
    assert writer.isOpened()
    for frame in noise:
        writer.write(frame)
    writer.release()
    cfg = AppConfig()
    cfg.video.keyframe_count = 4
    plan = process_capture(tmp_path, cfg)
    validate_plan(plan)
    reason = plan.rooms[0].walls[0].length_m.reason
    assert reason in {"fallback_prior", "video_thin_consensus"}
    span = (
        plan.rooms[0].walls[0].length_m.hi - plan.rooms[0].walls[0].length_m.lo
    ) / max(plan.rooms[0].walls[0].length_m.value, 1e-3)
    assert span >= 0.07


def test_unreadable_clip_falls_back() -> None:
    cfg = AppConfig()
    room = VideoRoom(room_id="gone", clip=Path("/tmp/does-not-exist.mp4"))
    polygon, openings, ceiling, reason, warnings = reconstruct_video_room(room, cfg)
    assert reason == "fallback_prior"
    assert "video_no_sane_keyframes" in warnings
    assert len(polygon) == 4
    assert ceiling == cfg.photos.ceiling_prior_m
    assert openings == [[], [], [], []]
