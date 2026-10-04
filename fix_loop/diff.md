# Fix loop — worst-performing gate (photo wall lengths)

**Current submission score** is not this file’s early FAIL table — use
[`reports/benchmark_report.md`](../reports/benchmark_report.md)
(`home_property` bedroom without `214550`). This file is the prediction → after trail.

**Still:** `20261003_214550` as `data/raw/home_room_photos/00.jpg`  
**Run:** `runs/home_room_photos/plan.json`  
**Reason:** `door_height_2.032m` (after the conditioned-intersection fix)  
**Tape:** `data/ground_truth/home_room.csv`

## Before / after the intersection guard

| | Before (unguarded A∩A) | After (A∩B + 8° guard) |
|---|---|---|
| `214550` | 85–116 m walls, area 107 m² (`max_edge`) | 5.11 / 6.16 / 10.25 / 11.31 m, area **11.58 m²** |
| `214538` | 11 km walls | rejected (`min_edge` ≈ 0) |
| Unit test | — | near-parallel lines raise `DegenerateIntersectionError` |

The infinity-box is gone. That is a correctness fix, not a threshold guess. We stop here on VP math.

## Score vs tape (sorted walls; correspondence unknown)

| Gate | Tape | Pred | Rel. err | ±8% |
|---|---|---|---|---|
| Wall (shortest) | 3.31 m | 5.11 m | **+54%** | FAIL |
| Wall | 3.38 m | 6.16 m | **+82%** | FAIL |
| Wall | 3.94 m | 10.25 m | **+160%** | FAIL |
| Wall (longest) | 4.01 m | 11.31 m | **+182%** | FAIL |
| Floor area | 13.30 m² | 11.58 m² | **−12.9%** | n/a (area not the ±8% row) |
| Ceiling | 2.76 m | 2.40 m prior | −13.0% | (door scale did not replace the 2.4 m prior) |

**Worst-performing gate:** photo wall lengths vs tape. Area is in the ballpark; walls are not.

## Hypothesis (do not “fix” tonight)

Single-still VP reconstruction recovers **overall scale** (door height 2.032 m) reasonably — area **−12.9%** vs tape — but **individual wall lengths** are sensitive to small errors in vanishing-point line angle. Those errors compound through the floor-quad intersection, so two sides blow out to 10–11 m while the product (area) stays near 12 m².

A **multi-view / multi-still median** should reduce that variance. That is exactly what the video-tier `video_keyframe_consensus` path is for. Photo-tier’s miss is the reason video-tier exists, not a reason to retune LSD tonight.

## Video on the same room (`20261003_210004.mp4`)

16 mid-biased keyframes, 0 sane → `fallback_prior`. Thumbs in `runs/home_room_video/keyframes/`.

| idx | t (s) | Fail | Notes |
|---|---|---|---|
| 354 | 11.8 | too few lines | |
| **476** | **15.9** | **degenerate 0.0°** | **Same corner as still `214550`** (door + jackets + bed + floor). Handheld, not a coverage miss. |
| 563 | 18.8 | too few lines | Too close; door only |
| 637 | 21.3 | too few lines | |
| 704 | 23.5 | too few lines | |
| 766 | 25.6 | sane_room min_edge | |
| 825 | 27.6 | degenerate 0.0° | Not the 214550 pose |
| 884 | 29.5 | too few lines | |
| 941 | 31.4 | degenerate 0.1° | |
| 1000 | 33.4 | degenerate 7.1° | |
| 1059 | 35.4 | too few lines | |
| 1121 | 37.4 | degenerate 0.2° | |
| 1188 | 39.7 | too few lines | Curtain rod / ceiling |
| 1262 | 42.1 | too few lines | |
| 1349 | 45.1 | degenerate 4.0° | |
| 1471 | 49.1 | need 2 VPs | |

**Two findings, not one.** Most of the 16 are structurally unable (blank wall, too close, mid-turn) — coverage. **Frame 476 at 15.9 s is the validated corner** and still dies: `DegenerateIntersectionError` 0.0°. The still of that pose passed after the A∩B guard; the handheld frame of it does not. Likely motion blur / a few degrees of angle, not “we never walked there.”

A pause on that corner (3–5 s) is still the right next shoot: several near-identical frames, less blur. Do not retune VP.

Consensus never claimed ±3%. The “median tightens walls” hypothesis is still untested — needs ≥3 sane keyframes.

## Depth Anything — scale bug, then two-anchor (4 Oct)

### Declaration (written as the ship decision)

**Worst gate:** photo wall lengths. VP: 1/19 stills sane, walls +54–182% on `214550`. First DA-V2: 12/19 sane, but 2–5× area (40–73 m² vs tape 13.30). Root cause: door **height + width** are one plane, so they pin `Z_door` and leave `(a, b)` free.

**Fix:** reject non-scene depth maps; fit `Z = a d + b` from **two depths** (door Z from 2.032 m leaf height, floor Z from 1.50 m camera-height). Not a new model.

**Predicted numbers (stated before the re-run):** well-anchored stills (frontal-ish door or a clear floor band) → area **12–16 m²** and paired walls **inside ±8%** of tape 3.31–4.01 m. Corner-door `214550` → still oversized, **~20–35 m²**, because a receding leaf is a bad fronto-parallel Z. Cards/screenshots → **reject**, not a 27 m² “room.”

### After (measured)

| | First DA-V2 (door H+W) | Two-anchor (door Z + floor camera-height) |
|---|---|---|
| `201935` | 24.7 m² / 4.8×5.2 | **13.34 m² / 3.48×3.83** (tape 13.30 / 3.31–4.01) |
| `014706` | 42.5 m² / 5.4×8.0 | **13.36 m² / 3.46×3.86** |
| `214550` | 66 m² / 7.7×8.6 | 27.4 m² / 4.24×6.46 (receding door, as predicted) |
| BIT card / signature / screenshot | “passed” | **rejected** (`sane_depth_map`) |

`201935` / `014706` landed on the predicted band. `214550` is still high (27.4 vs 20–35). Stop here — do not retune reconstruction tonight.

## Cleared limitation (Siva, 3 Oct 2026)

Drive samples have **no** tape/laser GT. We have no LiDAR phone. LiDAR vendor zips are a smoke test, not a scored ±X% table. Cite that email; do not treat it as an open gap.
