from floorplan.config import AppConfig
from floorplan.ingestion.detect import detect_tier
from floorplan.ingestion.lidar import ingest_lidar


def test_detect_lidar_tier(single_room) -> None:
    assert detect_tier(single_room) == "lidar"


def test_ingest_matches_depth_and_k(single_room) -> None:
    cfg = AppConfig()
    cfg.lidar.frame_stride = 1
    capture = ingest_lidar(single_room, cfg)
    assert capture.camera_matrix.shape == (3, 3)
    assert len(capture.frames) > 100
    frame = capture.frames[0]
    assert frame.depth_path.is_file()
    assert frame.fx > 0 and frame.fy > 0
    assert capture.rgb_size[0] > capture.frames[0].cx
