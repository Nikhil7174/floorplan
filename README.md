# Floorplan

One command turns a capture folder into a dimensioned room plan (`plan.json` + `plan.png`). Supports **LiDAR**, **photos**, and **video**.

**Python:** 3.11+ ([`pyproject.toml`](pyproject.toml)). Dependencies are pinned in [`uv.lock`](uv.lock).

**First photo/video run** downloads **Depth-Anything-V2-Small (~100 MB)** from Hugging Face (once, then cached). This is intentional — weights are fetched by script, not vendored in git.

**Included in this clone:** room photos/video under `data/raw/home_*` and tape notes under `data/ground_truth/`. Vendor Drive LiDAR zips are **not** included.

---

## 1. Run (clean machine)

```bash
# 0) once: install uv — https://docs.astral.sh/uv/
curl -LsSf https://astral.sh/uv/install.sh | sh

# 1) clone + install (~1 min on a good network; torch is large)
git clone <this-repo> floorplan && cd floorplan
uv sync

# 2) smoke — committed 2-room capture (no Drive symlink)
uv run floorplan process data/raw/home_property --out runs/home_property
# Expect: runs/home_property/plan.json and plan.png

# 3) score bedroom vs tape (benchmark scores room[0] = bedroom)
uv run python scripts/benchmark.py \
  runs/home_property/plan.json data/ground_truth/home_room.csv
# Expect: four walls PASS ±8%; area ~13.36 m²
```

Timed clean-clone dry run (4 Oct): **~4 min** total (`uv sync` ~61 s + process ~180 s including HF weights). Under the 15-minute bar.

### More commands

```bash
# Bedroom-only stills (larger dump; includes weak stills — prefer home_property above)
uv run floorplan process data/raw/home_room_photos --out runs/home_room_photos

# Kitchen video
uv run floorplan process data/raw/home_property_video --out runs/home_property_video

# Bedroom walk video (often thin/fallback — see reports)
uv run floorplan process data/raw/home_room_video --out runs/home_room_video

# Unit tests (LiDAR tests need optional Drive symlinks; photo/damage/benchmark tests do not)
uv run pytest

# Optional LiDAR smoke — Drive sample is not in this repo; symlink a local export:
mkdir -p data/raw
ln -sfn /path/to/vendor/c00a170fe1 data/raw/single_room
uv run floorplan process data/raw/single_room --out runs/single_room
```

---

## 2. How to test

| Goal | Steps |
|---|---|
| **Reproduce the reported bedroom score** | Use the stills already in the repo (§1). No phone needed. |
| **Try a new room (walk-in)** | Shoot → copy files onto this Mac → put them in a folder → run the CLI on that folder |

There is **no web upload, no app, no drag-and-drop UI**. “Upload” here means: get the photos off the phone onto the machine that has this repo, then pass that folder path to `floorplan process`.

### Walk-in: where the photos go

1. **On the phone** — shoot 2–8 JPEGs (see §3).
2. **Onto the Mac** — AirDrop the album to this computer, *or* plug in USB and copy from Finder / Image Capture. Do **not** send via WhatsApp (compresses).
3. **Into a folder next to the repo** (any path is fine). Example:

```text
~/Desktop/walkin_room/          ← you create this
  01.jpg
  02.jpg
  03.jpg
```

Or multi-room:

```text
~/Desktop/walkin_property/
  bedroom/01.jpg 02.jpg …
  kitchen/01.jpg 02.jpg …
```

4. **Run** (from the cloned repo):

```bash
cd floorplan   # the clone
uv run floorplan process ~/Desktop/walkin_room --out runs/walkin
# → runs/walkin/plan.json and runs/walkin/plan.png
```

The input folder can live anywhere on disk. Outputs go under `runs/` (or any `--out` path you choose). Committed examples already live at `data/raw/home_property/` if you only want to reproduce scores.

---

## 3. Capture protocol

### Photos

1. Stock Camera, **JPEG** (Most Compatible). Landscape.
2. **2–8 stills per room**; full **door leaf** in at least one frame (scale = 2.032 m).
3. **Transfer:** AirDrop or USB → Finder. **Not WhatsApp**.
4. Arrange files as in §2 (flat folder = one room; nested folders = multi-room). Matching door widths (±20%) become adjacency (“connector”). No hallway folder required.
5. `uv run floorplan process <that-folder> --out runs/<name>` — done when `plan.json` and `plan.png` exist.

### Video

One **H.264** clip per room (20–40 s), door in frame. Same transfer. Layout:

```text
~/Desktop/walkin_property/kitchen/walk.mp4
```

Then: `uv run floorplan process ~/Desktop/walkin_property --out runs/walkin`.

### LiDAR (Stray Scanner, iPhone 12 Pro+)

Export a folder with `odometry.csv` + `depth/` → AirDrop/USB that folder → same `floorplan process` command.

| Hardware | Photos | Video | LiDAR |
|---|---|---|---|
| iPhone 15 / 16 (no Pro) | yes | yes | no |
| iPhone 12 Pro+ | yes | yes | yes |

---

## 4. Status and known gaps

**Shipped**

- One-command LiDAR / photo / video pipeline
- Photo path: Depth Anything V2 + two-anchor scale; VP fallback; multi-still median
- Fix-loop write-up: [`fix_loop/diff.md`](fix_loop/diff.md)
- Bedroom tape benchmark: [`scripts/benchmark.py`](scripts/benchmark.py) + [`data/ground_truth/home_room.csv`](data/ground_truth/home_room.csv)
- Damage detector (draft: stain + crack OpenCV); stain stills in-repo
- Repeatability unit test (same input + seed 42)
- Assumptions documented below and in the technical report

**Known gaps / partial**

| Item | Status |
|---|---|
| Multi-room stitch (spec: 3+ rooms + connector) | **partial** — 2 rooms + door adjacency implemented and scored; a 3rd room/connector folder is supported by code but was not captured |
| Crack-class staged stills | **not shot** — stain only ([`home_room_damage.md`](data/ground_truth/home_room_damage.md)) |
| Second bedroom shoot (repeatability pair) | folder empty: `data/raw/home_room_photos_repeat/` |
| Kitchen tape / GT CSV | not measured — kitchen walls not scored ±8% |
| Video consensus ±3% on in-repo clips | bedroom walk = thin/fallback; kitchen video = thin |
| Head-to-head vs consumer app | **assumption** — no export was provided |
| LiDAR multi-room drift | out of scope (no LiDAR phone for this capture) |
| Damage precision | **draft** — FN-leaning, not benchmarked |

**Assumptions (listed for scoring):** opening 2 cm gate is LiDAR-only; JSON schema is ours (none published in the brief); no incumbent/consumer-app export to compare; no LiDAR phone for own scored captures.

Full matrix: [`reports/compliance_matrix.md`](reports/compliance_matrix.md). Decisions: [`reports/technical_report.md`](reports/technical_report.md).

---

## 5. Output

Every metric is `{value, lo, hi, unit, reason}`. Photo walls use ±8% door-scaled intervals; video claims ±3% only on `video_keyframe_consensus`. Schema: [`src/floorplan/schema/property_plan.json`](src/floorplan/schema/property_plan.json) (**ours**). Config: [`configs/default.yaml`](configs/default.yaml).

What ships in git vs what is ignored: [`data/README.md`](data/README.md). Do not ignore all of `data/raw/`.
