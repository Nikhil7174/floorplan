# Data that ships vs data that does not

Deliverable #8: raw captures + tape notes ship in the clone so graders can
regenerate reported numbers. **Cloning this repo downloads our room photos/video.**

## In the clone (tracked — others get these)

| Path | What |
|---|---|
| `data/raw/home_property/bedroom/` | `201935`, `014706` only (`214550` excluded — known weak) |
| `data/raw/home_property/kitchen/` | three kitchen stills |
| `data/raw/home_property_video/kitchen/walk.mp4` | kitchen clip |
| `data/raw/home_room_photos/` | full bedroom still dump (includes weak stills) |
| `data/raw/home_room_video/walk.mp4` | bedroom walk (~75 MB) |
| `data/raw/home_room_damage/` | four stain close-ups |
| `data/raw/home_room_photos_repeat/` | **empty stub** — second shoot not done |
| `data/ground_truth/home_room.csv` | bedroom tape |
| `data/ground_truth/home_room.md` | tape notes |
| `data/ground_truth/home_room_damage.md` | stain notes; crack TBD |

## Not in the clone (gitignored)

- Vendor Drive zips / `single_room`, `floor_only`, `with_ceiling` symlinks
- `single_room_photos/`, `downloads_sane/`, `runs/`

Do **not** add `data/raw/*` or `data/ground_truth/*` to `.gitignore`.

## Graders: start here

```bash
uv run floorplan process data/raw/home_property --out runs/home_property
uv run python scripts/benchmark.py runs/home_property/plan.json data/ground_truth/home_room.csv
```
