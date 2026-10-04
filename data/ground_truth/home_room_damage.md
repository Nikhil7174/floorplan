# Staged damage notes — home_room

**This file is Deliverable #8 ground truth. Do not gitignore it.**
Stills go in `data/raw/home_room_damage/` (also tracked, not vendor).

## Protocol (when you shoot)

Two classes only:

1. **stain** — paper or cloth discoloration on a wall, not the whole wall.
2. **crack** — painter’s tape or a drawn thin dark run, longer than ~20 cm.

Take 4 landscape stills of the same wall as the marks. Do not AI-edit. Note wall side (from door, left/right).

| Class | How staged | Wall | Approx size | Still names |
|---|---|---|---|---|
| stain | Real water / drip discoloration on painted surface (ceiling/wall close-ups) | bedroom ceiling/wall, close-up | tide rings ~10–30 cm; small brown flecks mm-scale | `00.jpg`←`20261004_142455`, `01.jpg`←`142452`, `02.jpg`←`142433`, `03.jpg`←`142440` |
| crack | _not shot yet_ | | | |

Captured 4 Oct 2026 ~14:29 from Downloads. Camera originals, not WhatsApp.

### What else is needed for these stain stills

Stain class is covered. Remaining for a complete 2-class damage row:

1. **Crack class** — one more shoot: painter’s tape or a thin dark run ≥ ~20 cm on a wall, 2–4 stills. Without that we only defend `stain`.
2. Optional: which wall (from the bedroom door, left/right) and approx size in the table above — fill blanks when you recall.
3. No more stain photos required unless you want a wider-context shot that includes the stain *and* a door (so damage can ride on a full room plan). Close-ups alone are enough for the detector unit path.

Detector is **draft**: conservative gates, more false negatives, warning `damage_detector_draft:precision_not_benchmarked`.
Draft run on these four: stain hits on `00`/`01` (tide rings); `02`/`03` flecks missed (expected FN).
