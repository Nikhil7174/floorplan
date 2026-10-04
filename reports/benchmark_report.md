# Benchmark report

Command:

```bash
uv run python scripts/benchmark.py runs/home_room_photos/plan.json data/ground_truth/home_room.csv
```

Tape: [`data/ground_truth/home_room.csv`](../data/ground_truth/home_room.csv) — walls 3.31 / 3.38 / 3.94 / 4.01 m, area 13.30 m², ceiling 2.76 m. Photo gate ±8%.

## Last scored stills (depth two-anchor, 4 Oct)

Not a `plan.json` of the whole `home_room_photos` folder (that folder still mixes failing stills). Per-still vs tape, sorted unique sides:

| Still | Pred walls | Area | ±8% walls |
|---|---|---|---|
| `201935` | 3.48 / 3.83 | 13.34 | PASS |
| `014706` | 3.46 / 3.86 | 13.36 | PASS |
| `214550` | 4.24 / 6.46 | 27.39 | FAIL (corner door) |

Re-run the command after `floorplan process` on a clean still folder to refresh a mechanical table.

Damage detector is **draft** (not in this table). Head-to-head vs a consumer app is listed as an assumption until an export arrives.
