# Multi-room photo capture (3 rooms + connector)

**Tracked. Do not gitignore this tree.**

```
home_property/
  bedroom/     # taped room stills (201935, 014706, 214550, …)
  kitchen/     # 20261004_143159 / 143212 / 143229
  connector/   # hallway — empty until shot
```

Kitchen video (separate tier): `data/raw/home_property_video/kitchen/walk.mp4` ← `20261004_143239.mp4`.

```bash
uv run floorplan process data/raw/home_property --out runs/home_property
uv run floorplan process data/raw/home_property_video --out runs/home_property_video
```
