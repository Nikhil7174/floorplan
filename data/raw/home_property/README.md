# Multi-room photo capture (3 rooms + connector)

**Tracked. Do not gitignore this tree.** Place stills when shot:

```
home_property/
  bedroom/     # 2–8 JPEGs, door leaf in at least one
  second/      # another room
  connector/   # hallway / landing, door to bedroom visible
```

Tape CSV: `data/ground_truth/home_property.csv` (create when measured).

```bash
uv run floorplan process data/raw/home_property --out runs/home_property
```
