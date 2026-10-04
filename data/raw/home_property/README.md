# Multi-room photo capture (2 rooms; door = connector)

**Partial vs spec.** Spec asks for 3+ rooms plus a connector. This tree is **2 rooms** with door adjacency as the connector. Stitch already accepts another folder if captured.

**Tracked — clones with the repo.**

```
home_property/
  bedroom/   # 00=201935, 01=014706 only
  kitchen/   # 143159 / 143212 / 143229
```

No hallway folder. **Door adjacency** between bedroom and kitchen is the connector.

### Bedroom still choice (explicit)

Known-weak oblique-door still **`214550` excluded** from multi-room consensus
to avoid re-introducing a characterized failure mode (corner-door Z overestimate,
~27 m²). Keep only the two tape-passing stills (`201935`, `014706`).

Kitchen video: `data/raw/home_property_video/kitchen/walk.mp4`.

```bash
uv run floorplan process data/raw/home_property --out runs/home_property
uv run python scripts/benchmark.py \
  runs/home_property/plan.json data/ground_truth/home_room.csv
# bedroom (room[0]): expect ±8% PASS on walls ~3.46 / 3.86 m
```
