# Benchmark report

## Command graders run

```bash
uv run floorplan process data/raw/home_property --out runs/home_property
uv run python scripts/benchmark.py \
  runs/home_property/plan.json data/ground_truth/home_room.csv
```

Tape: [`data/ground_truth/home_room.csv`](../data/ground_truth/home_room.csv) — walls 3.31 / 3.38 / 3.94 / 4.01 m, area 13.30 m², ceiling 2.76 m. Photo gate ±8%.

`benchmark.py` scores **room[0]** only. With `home_property`, that is **bedroom**.

## Scored result (4 Oct — bedroom without `214550`)

| Gate | Tape | Pred | Rel. err | Pass |
|---|---|---|---|---|
| wall[0] | 3.31 m | 3.46 m | +4.5% | **PASS** |
| wall[1] | 3.38 m | 3.46 m | +2.3% | **PASS** |
| wall[2] | 3.94 m | 3.86 m | −2.0% | **PASS** |
| wall[3] | 4.01 m | 3.86 m | −3.7% | **PASS** |
| floor_area | 13.30 m² | 13.36 m² | +0.5% | n/a |
| ceiling | 2.76 m | 2.63 m | −4.5% | n/a |

Stills used: `201935`, `014706`. **`214550` excluded** (known-weak oblique door). See [`data/raw/home_property/README.md`](../data/raw/home_property/README.md).

## Kitchen (not taped)

Thin consensus from one sane still ≈ **6.5×10.2 m, 66 m²** — not scored. No `home_property.csv` yet.

## Damage

Draft detector; stain stills in `data/raw/home_room_damage/`. Crack class **not staged**. Warning always includes `damage_detector_draft:precision_not_benchmarked`.

## Head-to-head

No consumer-app export provided — listed as assumption in the technical report.
