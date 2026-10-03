# Technical report (living)

Written as decisions happen. Cap is 6 pages at submission; this file is the single source of truth.

**Schedule.** Increment 3 of ~6 (LiDAR multi-room drift, damage, fix loop, benchmark/head-to-head still ahead). Video is many photo reconstructions plus a median, not SLAM.

## Increment 1 — LiDAR single-room path

**Capture route.** Route 2, stock **Stray Scanner**. Sample Drive zips already match that layout (`odometry.csv`, 16-bit mm depth, 0/1/2 confidence). Building an iOS app is out of scope for 48 hours and would not change the reconstruction.

**Why custom RANSAC, not Open3D.** The repeatability gate and the reproduction bundle both require a seeded, inspectable sampler. Open3D is a painful clean-machine install and hides the residual test we have to defend.

**Why confidence is a field, not a post-pass.** Photo and video must emit the same `RoomGeometry` with wider intervals. If confidence is bolted on after JSON, those tiers will either crash or look over-confident. `ConfidenceInterval.reason` is what we point at when a floor-only scan has no ceiling returns.

**Scale.** LiDAR depth is millimeters. Backprojection converts to meters. `scale_recovery.identity_scale` is a no-op so the photo-tier door-height hook has a place to live later.

**Vertical second pass.** Unconstrained RANSAC eats floor, ceiling, and tabletops first; walls lose. After classifying those, if fewer than three walls remain, a seeded vertical-constrained pass (`recover_vertical_walls`) peels near-vertical planes. Indoor rooms are then closed with a Manhattan oriented box of those planes — parallel walls make a raw intersection cycle drop corners.

**Output schema is ours.** The brief says “JSON to the published schema.” The six-page PDF has the output *contract* (rooms, openings, adjacency, damage, confidence intervals) but no JSON Schema file. The Drive folder is only the three sample zips. Nothing else published turned up. [`src/floorplan/schema/property_plan.json`](../src/floorplan/schema/property_plan.json) is an internal schema we wrote to match that contract. If a real published schema appears later, we adapt the models to it rather than claiming this file was provided.

**Gitignore / Deliverable #8.** Vendor Drive samples (`single_room`, `floor_only`, `with_ceiling`, `data/raw/vendor/`, `*.zip`) stay ignored — not ours to redistribute. Our own captures and `data/ground_truth/` are tracked. A blanket `data/raw/*` would swallow the reproduction bundle; do not add it. Convention is in [`data/README.md`](../data/README.md).

**Known limitation, increment 1.** Opening detection is 1D occupancy along each wall. `single_room` does not look at the ceiling; height is a wide prior.

## Increment 2 — Photo tier

**Why not COLMAP.** The spec is 2–8 stills per room. Sparse SfM fails more often than it works, and COLMAP is a bad clean-machine dependency. We recover a Manhattan frame from vanishing points (LSD, Hough fallback) on the strongest view, then set metric scale from a detected door leaf at **2.032 m** (`configs/default.yaml` → `photos.door_height_m`). If no door, a vertical span is assumed to be a 2.4 m ceiling (`ceiling_prior_no_door`) and the interval widens to 18%. If VPs fail entirely we emit a prior box at 30% — wide, not a crash.

**Calibrated intervals.** The photo gate is ±8% with calibrated intervals. Door-scaled lengths use `door_scale_frac: 0.08`. That is the calibration: we do not report 2 cm on a phone still.

**Opening gate — spec is ambiguous; this is our reading.** The metric table requires opening widths ≤ 2 cm on ≥ 85% of openings, and scores missed/phantom openings. Walls are explicitly loosened for photos (±8%) and video (±3%). The opening row has **no** photo/video exception. Two readings: (a) 2 cm applies at every tier, or (b) openings follow the same “calibrated intervals widen as sensors thin” rule as walls. We are shipping (b): photo opening *position* is a placeholder (typical 0.9 m leaf on the longest wall, not imaged), and we do not claim the 2 cm detection gate on the photo path. If a grader applies (a), photo openings will fail that row. This is a documented judgment call, not a silent gap. If we have a channel to Siva, ask which reading they want — do not spend increment time building real jamb localization.

**Per-room folders → one plan.** Each subfolder becomes a `RoomGeometry`. `stitch_rooms` matches door widths (±20%) for adjacency and translates rooms so AABBs do not overlap. Unmatched rooms pack in a row with `photo_stitch_unmatched_doors`. This is not a pose graph; photo folders have no shared poses. Drift ablation stays a LiDAR-tier job.

**Disclosure.** No pretrained network. Line detection is OpenCV LSD or Canny+Hough. Door height is a published interior standard, not measured on the day unless we later tape the actual leaf.

**Proxy frames vs protocol stills.** Stills ripped from the vendor `rgb.mp4` fail VP sanity (handheld walk, motion blur, no composed door) and correctly emit a 4×5 m prior at 30% (`fallback_prior`). That is the fail-loud path. The graded photo path is 2–8 composed JPEGs with a door leaf, as in the README protocol.

## Increment 3 — Video tier

**Why not SLAM / COLMAP.** Same clean-machine and time-box reasons as photos, plus a handheld clip does not give us metric depth. Video’s advantage is *many* stills of the same room. We sample keyframes, run increment-2 VP + door-scale on each, and only claim ±3% when enough sane frames agree.

**Sampling.** Default 16 keyframes, skip first/last 10%. Indices are Beta(2.2, 2.2) toward mid-clip (`video.midpoint_bias`), not uniform in time. A walkthrough often starts on a doorway or one wall; the walker is more often centered later. If `_sane_room` rarely fires on a real clip, change sampling — do not retune VP.

**Consensus is the failure point, and the guards are explicit.** A naive index-wise median is silent garbage when winding flips or wall counts differ. We never median mismatched polygons:

- ≥ `min_sane_frames` (3) **and** every sane frame has the same wall count → median AABB width/depth, reason `video_keyframe_consensus`, fraction `0.03`.
- Otherwise if any sane frames exist → best-score frame, `video_thin_consensus`, fraction `0.08`. If wall counts disagreed at ≥3 frames, also warn `video_wall_count_mismatch`.
- Zero sane → same 4×5 m `fallback_prior` at 30%. Never invent a tight 3%.

Scale is still the door (2.032 m) or the 2.4 m ceiling prior. Stitch reuses photo `stitch_rooms`. Opening 2 cm judgment call is unchanged.

**Own clips are not shot yet.** The only real video on disk is vendor `rgb.mp4`. First real-data run (8 mid-biased keyframes, clip treated as a video-only folder): 7 frames failed VP/sanity (one lacked two vanishing points — a close-up / coverage miss, not a consensus-math bug), 1 frame barely passed `_sane_room` (~2.87 m²). Landed in `video_thin_consensus` at ±8% with warning `video_thin_consensus`. Did **not** claim ±3%. That is the coverage risk we flagged: a walkthrough keyframe is not a posed still. Fix, when we have our own clip, is sampling — not VP.
