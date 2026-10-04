# Ground truth

**Not gitignored.** Ships in the clone.

| File | Role |
|---|---|
| [`home_room.csv`](home_room.csv) | Bedroom tape (scored) |
| [`home_room.md`](home_room.md) | How walls/door/ceiling were measured |
| [`home_room_damage.md`](home_room_damage.md) | Stain notes; **crack still TBD** |

Kitchen tape / `home_property.csv` — **not created** (kitchen unscored).

```bash
uv run python scripts/benchmark.py \
  runs/home_property/plan.json data/ground_truth/home_room.csv
```
