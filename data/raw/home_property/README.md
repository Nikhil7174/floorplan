# Multi-room photo capture (2 rooms; door = connector)

**Tracked. Do not gitignore this tree.**

```
home_property/
  bedroom/   # 00=201935, 01=014706 only
  kitchen/   # 20261004_143159 / 143212 / 143229
```

No separate hallway folder. **Adjacency via the shared door** is the connector
between bedroom and kitchen (`infer_adjacencies` door-width match).

### Bedroom still choice (explicit)

Known-weak oblique-door still **`214550` excluded** from multi-room consensus
to avoid re-introducing a characterized failure mode (corner-door Z overestimate,
~27 m²). Keep only the two tape-passing stills (`201935`, `014706`).

Kitchen video (separate tier): `data/raw/home_property_video/kitchen/walk.mp4`.

```bash
uv run floorplan process data/raw/home_property --out runs/home_property
uv run python scripts/benchmark.py runs/home_property/plan.json data/ground_truth/home_room.csv
```

Note: `benchmark.py` scores room[0] only — bedroom is first alphabetically.
