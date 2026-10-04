# Floorplan

One command turns a capture folder into a dimensioned room plan (`plan.json` + `plan.png`). **LiDAR**, **photos**, and **video** run today.

**Python:** `requires-python = ">=3.11"` ([`pyproject.toml`](pyproject.toml)). Deps pinned in committed [`uv.lock`](uv.lock).

**First photo/video run** downloads **Depth-Anything-V2-Small (~100 MB)** from Hugging Face (network once, then cached). Disclosed on purpose — case study allows “weights fetched by script.”

**Your room photos/video in this repo are cloned with the repo** (Deliverable #8). Graders get `data/raw/home_*` and `data/ground_truth/`. Vendor Drive zips are **not** in the clone.

---

## 1. Clear steps to run (grader / clean machine)

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

Timed clean-clone dry run (4 Oct): **~4 min** total (`uv sync` ~61 s + process ~180 s incl. HF weights). Under the 15-minute bar.

### Other useful commands

```bash
# Bedroom-only stills (larger dump; includes weak stills — prefer home_property for scored smoke)
uv run floorplan process data/raw/home_room_photos --out runs/home_room_photos

# Kitchen video
uv run floorplan process data/raw/home_property_video --out runs/home_property_video

# Bedroom walk video (often thin/fallback — documented)
uv run floorplan process data/raw/home_room_video --out runs/home_room_video

# Unit tests (LiDAR tests need optional Drive symlinks; photo/damage/benchmark tests do not)
uv run pytest

# Optional LiDAR smoke — Drive sample NOT in repo; symlink yourself:
mkdir -p data/raw
ln -sfn /path/to/vendor/c00a170fe1 data/raw/single_room
uv run floorplan process data/raw/single_room --out runs/single_room
```

---

## 2. How others test (no app)

| Scenario | What they do |
|---|---|
| **Reproduce your numbers** | Clone → `uv sync` → process `data/raw/home_property` → `benchmark.py` |
| **Walk-in (cold room)** | They shoot → AirDrop/USB into a folder → `uv run floorplan process <folder> --out runs/walkin` |

They **manually** put photos/video into folders (see protocol below). That hand-off is expected and scored for clarity — not something we wrap in a GUI.

---

## 3. Capture protocol (non-engineer hand-off)

### Photos

1. Stock Camera, **JPEG** (Most Compatible). Landscape.
2. **2–8 stills per room**; full **door leaf** in ≥1 frame (scale = 2.032 m).
3. **Transfer:** AirDrop *or* USB → Finder. **Not WhatsApp** (compresses).
4. On the Mac, create folders by hand:

```text
<property>/                 ← CLI argument
  bedroom/*.jpg             ← any room names
  kitchen/*.jpg
```

Flat folder of stills = one room. Nested folders = multi-room; matching door widths (±20%) = adjacency (“connector”). No hallway folder required.

5. `uv run floorplan process <property> --out runs/<name>` → done when `plan.json` + `plan.png` exist.

### Video

One **H.264** clip per room (20–40 s), door in frame → `<property>/<room>/walk.mp4` → same command.

### LiDAR (Stray Scanner, iPhone 12 Pro+)

Export folder with `odometry.csv` + `depth/` → same command.

| Hardware | Photos | Video | LiDAR |
|---|---|---|---|
| iPhone 15 / 16 (no Pro) | yes | yes | no |
| iPhone 12 Pro+ | yes | yes | yes |

---

## 4. What’s done vs left (honest)

**Done**

- LiDAR / photo / video one-command pipeline
- Photo: Depth Anything V2 + two-anchor scale; VP fallback; multi-still median
- Fix-loop documented ([`fix_loop/diff.md`](fix_loop/diff.md))
- Benchmark script + tape CSV for bedroom
- Damage **draft** (stain + crack OpenCV); stain stills committed
- Repeatability **unit** test (same input + seed 42)
- Clean-clone smoke path + HF disclosure
- Assumptions listed (opening 2 cm LiDAR-only; our JSON schema; no incumbent export; no LiDAR phone)

**Left / partial (documented, not hidden)**

| Item | Status |
|---|---|
| Multi-room stitch (spec: 3+ rooms + connector) | **partial** — 2 rooms + door adjacency implemented/scored; 3rd room/connector not captured (code already supports another folder) |
| Crack-class staged stills | **not shot** — stain only so far ([`home_room_damage.md`](data/ground_truth/home_room_damage.md)) |
| Second bedroom shoot (repeatability pair) | folder empty: `data/raw/home_room_photos_repeat/` |
| Kitchen tape / GT CSV | not measured — kitchen walls not scored ±8% |
| Video consensus ±3% on own clip | bedroom walk = thin/fallback; kitchen video = thin |
| Head-to-head vs consumer app | **assumption** — no export provided |
| LiDAR multi-room drift | out of scope (no LiDAR phone) |
| Damage precision | **draft** — FN-leaning, not benchmarked |

Full matrix: [`reports/compliance_matrix.md`](reports/compliance_matrix.md). Living decisions: [`reports/technical_report.md`](reports/technical_report.md).

---

## 5. Output + layout

Every metric: `{value, lo, hi, unit, reason}`. Photo ±8% door-scaled; video ±3% only on `video_keyframe_consensus`. Schema: [`src/floorplan/schema/property_plan.json`](src/floorplan/schema/property_plan.json) (**ours**). Config: [`configs/default.yaml`](configs/default.yaml).

Committed vs ignored data: [`data/README.md`](data/README.md). **Do not** gitignore all of `data/raw/`.
