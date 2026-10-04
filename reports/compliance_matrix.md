# Compliance matrix

| Requirement | Path | Artifact | Status |
|---|---|---|---|
| One command per capture | `src/floorplan/cli.py` | `uv run floorplan process <dir> --out <dir>` | **done** (LiDAR / photos / video) |
| LiDAR ingest | `ingestion/lidar.py` | `LidarCapture` | **done** |
| Photo tier | `sfm.py`, `depth_model.py` | DA-V2 + two-anchor; VP fallback; ±8% | **done** |
| Opening widths ≤ 2 cm ≥ 85% | LiDAR occupancy; photo placeholder leaf | **Assumption:** 2 cm is LiDAR-only (Siva 3 Oct) | documented |
| Video tier | `video.py` | keyframes + consensus / thin / fallback | **done** (own clips thin/fallback; ±3% unproven on our walks) |
| Plane fitting / room polygon | `plane_fitting.py`, `room.py` | `RoomGeometry` | **done** |
| Scale recovery | `scale_recovery.py` / depth affine | LiDAR identity; photo door+floor anchors | **done** |
| SfM | depth + VP fallback | not COLMAP | **done** |
| Multi-room stitch | `stitching/` | bedroom+kitchen; door = connector | **partial** — 2 rooms + door adjacency implemented and scored; literal “3+ rooms plus connector” composition not captured due to time; architecture (`stitch_rooms`, `infer_adjacencies`) supports a 3rd room/connector folder without code changes if captured |
| Damage + concealed | `damage/` | stain/crack draft; concealed flags | **partial** — stain stills in; crack stills **not shot**; precision not benchmarked |
| Confidence on every metric | `confidence/scoring.py` | `ConfidenceInterval` | **done** |
| JSON schema | `schema/property_plan.json` | ours (none published in PDF/Drive) | **done** |
| Raw benchmark data ships | `data/raw/`, `data/ground_truth/` | our captures committed | **done** for bedroom+kitchen+stains; repeat folder empty |
| Rendered plan | `render/plan.py` | `plan.png` | **done** |
| Config, no magic numbers | `configs/default.yaml` | thresholds | **done** |
| Capture protocol + device matrix | `README.md` | AirDrop/USB + folder shape | **done** |
| Benchmark gates | `scripts/benchmark.py` | vs `home_room.csv` | **done** — bedroom PASS ±8% on `home_property` |
| Fix loop | `fix_loop/diff.md` | prediction then after | **done** |
| Repeatability | `test_repeatability.py` | seed 42 unit test | **partial** — unit done; second bedroom shoot **not done** |
| Head-to-head vs consumer app | — | no export on Drive | **assumption** — listed, not scored |
| Clean-machine < 15 min | README smoke | timed ~4 min clean clone | **done** (documented) |
| LiDAR multi-room drift | — | no LiDAR phone | **out of scope** (assumption) |

## Open capture checklist (if time)

1. 3rd room and/or connector folder → drop under `data/raw/home_property/` (no code change)
2. Crack stills → `data/raw/home_room_damage/` + fill table in `home_room_damage.md`
3. Second bedroom pass → `data/raw/home_room_photos_repeat/`
4. Optional: kitchen tape CSV → `data/ground_truth/home_property.csv`
5. Push `main` when remote should match local (reproduction clone)
