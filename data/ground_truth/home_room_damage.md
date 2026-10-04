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

Detector is **draft**: conservative gates, more false negatives, warning `damage_detector_draft:precision_not_benchmarked`.
