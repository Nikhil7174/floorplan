# Compliance matrix

| Requirement | Path | Artifact | Status |
|---|---|---|---|
| One command per capture | `src/floorplan/cli.py` | `uv run floorplan process <dir> --out <dir>` | done (LiDAR / photos / video) |
| LiDAR ingest (depth, poses, K) | `src/floorplan/ingestion/lidar.py` | `LidarCapture` | done |
| Photo tier | `src/floorplan/ingestion/photos.py`, `reconstruction/sfm.py`, `vanishing.py` | `RoomGeometry` + ±8% CIs | done |
| Opening widths ≤ 2 cm on ≥ 85% | LiDAR: `reconstruction/room.py` occupancy gaps. Photo: placeholder leaf on longest wall (`sfm._door_openings`) | **Judgment call:** spec loosens walls to ±8% for photos but lists no photo exception on the opening gate. We treat opening *detection/width* as scaling with tier confidence (photo openings are not independently gated at 2 cm). Position is not measured. Ask Siva if a channel exists. | documented |
| Video tier | `ingestion/video.py`, `reconstruction/video.py` | keyframe sample + photo recon + consensus / thin / fallback | done (synthetic; own clips not shot) |
| Plane fitting / room polygon | `src/floorplan/reconstruction/plane_fitting.py`, `room.py` | `RoomGeometry` | done (single room) |
| Scale recovery hook | `src/floorplan/reconstruction/scale_recovery.py` | identity on LiDAR | done |
| SfM | `src/floorplan/reconstruction/sfm.py` | vanishing-point Manhattan, not COLMAP | done (photos) |
| Photo whole-property stitch | `src/floorplan/stitching/` | door-match + non-overlap pack | done (no pose-graph drift) |
| Damage + concealed rules | `src/floorplan/damage/` | stub | not_started |
| Confidence on every metric | `src/floorplan/confidence/scoring.py` | `ConfidenceInterval` | done |
| JSON schema | `src/floorplan/schema/property_plan.json` | `plan.json` (our schema; none published in PDF/Drive) | done |
| Raw benchmark data ships | `data/README.md`, `.gitignore` | our captures + `data/ground_truth/` tracked; vendor samples ignored | done |
| Rendered plan | `src/floorplan/render/plan.py` | `plan.png` | done |
| Config, no magic numbers | `configs/default.yaml` | thresholds | done |
| Capture protocol + device matrix | `README.md` | Route 2 Stray Scanner + photo/video Camera protocol | done |
| Benchmark gates | `scripts/benchmark.py` | stub | not_started |
| Fix loop | `fix_loop/` | placeholder | not_started |
| Repeatability / golden JSON | `tests/` | after first good run | not_started |
