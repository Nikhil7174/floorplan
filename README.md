# Floorplan

One command turns a capture folder into a dimensioned room plan (`plan.json` + `plan.png`). **LiDAR**, **photos**, and **video** run today. Video claims ±3% only when enough keyframes agree on wall count; otherwise it widens.

## Clean-machine setup (< 15 minutes)

1. Install [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone this repo and sync:

```bash
cd LiDAR
uv sync
```

3. Vendor Drive samples (gitignored — not ours to redistribute). Symlink locally; do not commit:

```bash
mkdir -p data/raw
ln -sfn /Users/nikhilkumarsingh/Downloads/c00a170fe1 data/raw/single_room
ln -sfn /Users/nikhilkumarsingh/Downloads/1a8384c3f6 data/raw/floor_only
ln -sfn /Users/nikhilkumarsingh/Downloads/c7d28f72c6 data/raw/with_ceiling
```

Our own benchmark captures and tape/laser notes go under `data/raw/<name>/` and `data/ground_truth/` and **are committed** (Deliverable #8). See [`data/README.md`](data/README.md). Do not gitignore all of `data/raw/`.

4. Run one capture:

```bash
uv run floorplan process data/raw/single_room --out runs/single_room
uv run floorplan process data/raw/photos_property --out runs/photos_property
uv run floorplan process data/raw/videos_property --out runs/videos_property
```

Expected files: `plan.json` and `plan.png` in the `--out` directory.

Photo capture layout (one folder per room, 2–8 JPEGs each):

```
photos_property/
  living/01.jpg … 06.jpg
  kitchen/01.jpg … 04.jpg
```

A flat folder of stills is treated as a single room.

Video capture layout (one clip per room):

```
videos_property/
  living/walk.mp4
  kitchen/walk.mp4
```

A single top-level `.mp4` / `.mov` is one room. A LiDAR folder with `rgb.mp4` stays LiDAR.

5. Tests (need the `single_room` and `floor_only` links):

```bash
uv run pytest
```

Thresholds live in [`configs/default.yaml`](configs/default.yaml). Do not scatter magic numbers.

## Capture protocol (Route 2 — Stray Scanner)

Walk-in testers follow this page literally.

1. On an iPhone 12 Pro or newer (LiDAR), install **Stray Scanner** from the App Store.
2. Open the app, grant camera / motion permissions, start a new scan.
3. Hold the phone in landscape, chest height, screen facing you.
4. Walk the room perimeter slowly, then a figure-eight through the center. Point at the **ceiling** if you want a ceiling height (skip that only for a floor-only ablation).
5. Avoid standing still for long; avoid pointing only at glass or mirrors.
6. Stop after 30–90 seconds for a single room. Export / share the scan folder via the Files app (AirDrop or USB).
7. Hand the unzipped folder to the pipeline. It must contain `odometry.csv` and `depth/`.

### Photos (any iPhone 15 or newer, no LiDAR required)

1. Use the stock Camera app. Prefer **JPEG** (Settings → Camera → Formats → Most Compatible). HEIC is accepted if Pillow can read it.
2. One folder per room. Take **2 to 8** stills per room.
3. Stand near two opposite corners. Include every wall. Put a **full door leaf** in at least one frame — that door is the meter stick (2.032 m / 80").
4. Hold the phone landscape, keep the floor and a door header in frame when you can.
5. Do not zoom. Avoid only-mirror or only-glass shots.
6. AirDrop / Files the folders to the machine. The parent folder is the capture argument.

### Video (any iPhone 15 or newer, no LiDAR required)

1. Stock Camera app, landscape. Prefer **Most Compatible** (H.264). HEVC often fails to decode on the walk-in Mac — the CLI logs that line instead of crashing.
2. **One clip per room**, 20–40 seconds. A property-length walk needs room cuts we will not invent.
3. Walk slowly through the center. Include a **full door leaf** — scale is still 2.032 m, same as photos.
4. Do not zoom. Start/end at a doorway is fine: sampling skips the first and last 10% and biases toward mid-clip, where the walker is more often centered.
5. AirDrop / Files the folders. Nested `living/walk.mp4` or a single top-level clip both work.

Device matrix (honest):

| Hardware | Photos | Video | LiDAR |
|---|---|---|---|
| iPhone 15 / 16 (no Pro) | **this path** | **this path** | no |
| iPhone 12 Pro or newer (LiDAR) | **this path** | **this path** | **this path** |

## Output

Every measurement carries `{value, lo, hi, unit, reason}`. A floor-only LiDAR scan writes a wide ceiling interval with `reason=no_ceiling_returns`. Photo walls use a calibrated ±8% interval when a door set the scale (`door_height_2.032m`), wider if we had to use a ceiling prior. Video walls use ±3% only on `video_keyframe_consensus` (≥3 sane keyframes, same wall count); otherwise `video_thin_consensus` (±8%) or `fallback_prior` (±30%).

`plan.json` follows [`src/floorplan/schema/property_plan.json`](src/floorplan/schema/property_plan.json). That file is **ours**: the case study asks for “the published schema,” but the PDF and Drive folder do not include one. The schema encodes the Part 2 contract until an official file appears.

## Layout

See `src/floorplan/` for ingestion, reconstruction, confidence, schema, and the CLI. Reports live in `reports/`.
