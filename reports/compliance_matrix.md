# Compliance matrix

| Requirement | Path | Artifact | Status |
|---|---|---|---|
| One command per capture | `src/floorplan/cli.py` | `uv run floorplan process <dir> --out <dir>` | done (LiDAR / photos / video) |
| LiDAR ingest (depth, poses, K) | `src/floorplan/ingestion/lidar.py` | `LidarCapture` | done |
| Photo tier | `src/floorplan/ingestion/photos.py`, `reconstruction/sfm.py`, `depth_model.py` | DA-V2 + RANSAC, VP fallback, ±8% CIs | done |
| Opening widths ≤ 2 cm on ≥ 85% | LiDAR: `reconstruction/room.py` occupancy gaps. Photo: placeholder leaf on longest wall (`sfm._door_openings`) | **Assumption (Siva 3 Oct: list at submission):** 2 cm gate is LiDAR-only. Photo/video openings widen with the tier, same as walls. Position not measured. | documented |
| Video tier | `ingestion/video.py`, `reconstruction/video.py` | keyframe sample + photo recon + consensus / thin / fallback | done (synthetic; own clips not shot) |
| Plane fitting / room polygon | `src/floorplan/reconstruction/plane_fitting.py`, `room.py` | `RoomGeometry` | done (single room) |
| Scale recovery hook | `src/floorplan/reconstruction/scale_recovery.py` | identity on LiDAR | done |
| SfM | `src/floorplan/reconstruction/depth_model.py`, `sfm.py` | DA-V2 cloud + RANSAC; VP fallback; not COLMAP | done (photos) |
| Photo whole-property stitch | `src/floorplan/stitching/` | door-match + non-overlap pack | done (no pose-graph drift) |
| Damage + concealed rules | `src/floorplan/damage/` | 2-class stain/crack (draft, FN-leaning); concealed flags | done (draft; staged stills pending) |
| Confidence on every metric | `src/floorplan/confidence/scoring.py` | `ConfidenceInterval` | done |
| JSON schema | `src/floorplan/schema/property_plan.json` | `plan.json` (our schema; none published in PDF/Drive) | done |
| Raw benchmark data ships | `data/README.md`, `.gitignore` | **Siva 3 Oct (cleared):** no GT on Drive samples. Our tape is `home_room.csv`. LiDAR vendor zips = smoke only. | in_progress (photo scored; video original still missing) |
| Rendered plan | `src/floorplan/render/plan.py` | `plan.png` | done |
| Config, no magic numbers | `configs/default.yaml` | thresholds | done |
| Capture protocol + device matrix | `README.md` | Route 2 Stray Scanner + photo/video Camera protocol | done |
| Benchmark gates | `scripts/benchmark.py` | tape CSV vs plan.json; report in `reports/benchmark_report.md` | `201935`/`014706` PASS ±8%; `214550` FAIL |
| Fix loop | `fix_loop/diff.md` | VP guard + DA-V2 two-anchor; prediction then after on tape | done (photo walls; stop recon tonight) |
| Repeatability / golden JSON | `tests/reconstruction/test_repeatability.py` | same input + seed 42 → same walls | unit done; second shoot pending |
