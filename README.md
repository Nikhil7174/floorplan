# Floorplan

One command turns a capture folder into a dimensioned room plan (`plan.json` + `plan.png`). **LiDAR**, **photos**, and **video** run today. Video claims ±3% only when enough keyframes agree on wall count; otherwise it widens.

**Python:** `requires-python = ">=3.11"` in [`pyproject.toml`](pyproject.toml). Dependencies are pinned in committed [`uv.lock`](uv.lock).

**First photo/video run** downloads **Depth-Anything-V2-Small (~100 MB)** from Hugging Face; needs network once, then cached under the Hugging Face cache. Allowed by the case-study “weights fetched by script” rule — disclosed here, not silent.

---

## Quick start (what a grader does first)

Clean machine, under ~15 minutes to a green smoke:

```bash
# install uv once: https://docs.astral.sh/uv/
git clone <this-repo> floorplan && cd floorplan
uv sync

# Smoke on committed capture (no Drive symlink needed):
uv run floorplan process data/raw/home_property --out runs/home_property
# Expect: runs/home_property/plan.json and plan.png

# Reproduce scored bedroom numbers vs tape:
uv run python scripts/benchmark.py runs/home_property/plan.json data/ground_truth/home_room.csv
```

`benchmark.py` scores **room[0]** (bedroom is first alphabetically). Tape walls for that room should land near **3.46 / 3.86 m**, area **~13.36 m²**, ±8% PASS.

LiDAR smoke (optional; Drive samples are **not** in the repo):

```bash
mkdir -p data/raw
ln -sfn /path/to/vendor/c00a170fe1 data/raw/single_room
uv run floorplan process data/raw/single_room --out runs/single_room
```

---

## How others test this (no app, no UI)

There is no packaged app. A stranger with a terminal, this README, and one CLI command is the bar.

### 1. Reproduction bundle (your reported numbers)

Clone → `uv sync` → process a **committed** folder under `data/raw/` → optional `scripts/benchmark.py` against `data/ground_truth/`. That regenerates the scored table from raw inputs (Deliverable #8).

### 2. Walk-in test (cold capture, highest weight)

They shoot a room you have never seen, put files in a folder shaped as below, then:

```bash
uv run floorplan process <their_capture_folder> --out runs/walkin
```

Someone must copy photos/video off the phone into that folder. That hand-off is expected — document it clearly; do not hide it behind a GUI.

---

## Capture protocol (hand to a non-engineer)

### Photos (any iPhone 15+, no LiDAR required)

1. Stock **Camera** app. Prefer **JPEG** (Settings → Camera → Formats → Most Compatible).
2. **2–8 stills per room**, landscape. Include every wall. Put a **full door leaf** in at least one frame (meter stick = 2.032 m / 80").
3. Do not zoom. Avoid only-mirror / only-glass shots.
4. **Transfer (pick one):** AirDrop the album to the Mac, *or* USB → Finder / Image Capture. Do not send via WhatsApp (it compresses).
5. **Folder shape on the Mac** (they create this by hand):

```text
<property_name>/          ← this path is the CLI argument
  bedroom/01.jpg …        ← any room name; 2–8 JPEGs
  kitchen/01.jpg …
```

A flat folder of stills (no subfolders) is one room. Nested room folders → one `RoomGeometry` each; doors that match ±20% width become adjacencies (the “connector”). No separate hallway folder required.

6. Run:

```bash
uv run floorplan process <property_name> --out runs/<property_name>
```

Done when `plan.json` and `plan.png` exist in `--out`.

### Video (any iPhone 15+)

1. Stock Camera, landscape, **Most Compatible** (H.264). HEVC often fails to decode on the walk-in Mac — the CLI logs that instead of crashing.
2. **One clip per room**, 20–40 s. Include a full door leaf.
3. AirDrop / USB into:

```text
<property_name>/
  kitchen/walk.mp4
```

Or a single top-level `.mp4` / `.mov` = one room. Then the same `floorplan process` command.

### LiDAR (Route 2 — Stray Scanner)

1. iPhone 12 Pro+, App Store **Stray Scanner**.
2. Landscape, chest height; perimeter then figure-eight; optional ceiling look.
3. Export the scan folder (must contain `odometry.csv` and `depth/`). AirDrop / USB to the Mac.
4. `uv run floorplan process <that_folder> --out runs/<name>`.

Device matrix:

| Hardware | Photos | Video | LiDAR |
|---|---|---|---|
| iPhone 15 / 16 (no Pro) | this path | this path | no |
| iPhone 12 Pro or newer | this path | this path | this path |

---

## Output

Every measurement carries `{value, lo, hi, unit, reason}`. Photo walls use ±8% when door-scaled; video ±3% only on `video_keyframe_consensus`. Damage regions are optional and draft (`damage_detector_draft:precision_not_benchmarked`).

`plan.json` follows [`src/floorplan/schema/property_plan.json`](src/floorplan/schema/property_plan.json) — **ours**; the case study PDF/Drive did not ship a schema file.

Thresholds: [`configs/default.yaml`](configs/default.yaml). Tests: `uv run pytest` (LiDAR tests need the optional Drive symlinks).

See [`data/README.md`](data/README.md) for what is committed vs gitignored. Do **not** add `data/raw/*` to `.gitignore`.
