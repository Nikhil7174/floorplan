# home_room — tape notes

One bedroom. No LiDAR capture (no hardware). Siva (3 Oct): Drive samples have no GT; we tape our own 1–2 rooms.

**Current scored path** (graders): `data/raw/home_property/bedroom/` stills `201935` + `014706` → all walls **PASS ±8%**. See [`reports/benchmark_report.md`](../../reports/benchmark_report.md).

**Historical fix-loop** used weak still `214550` (VP / early DA). That story lives in [`fix_loop/diff.md`](../../fix_loop/diff.md) — do not treat those failing numbers as the submission score.

| Item | Tape | Meters |
|---|---|---|
| Door height × width | 204.5 × 81.5 cm | 2.045 × 0.815 |
| Ceiling / room height | 276 cm | 2.76 |
| Wall 1 | 331 cm | 3.31 |
| Wall 2 | 401 cm | 4.01 |
| Wall 3 | 338 cm | 3.38 |
| Wall 4 | 394 cm | 3.94 |
| Floor / ceiling area | derived | **13.2964 m²** |

Opposite walls are the pairs (1, 3) and (2, 4). Area uses those means, not a perfect rectangle.

Door height here is 2.045 m. Pipeline default scale is still 2.032 m (80") until we point a capture-specific config at this tape.

Machine-readable: [`home_room.csv`](home_room.csv).

### Video on this room

Original `20261003_210004.mp4` → `data/raw/home_room_video/walk.mp4`. Sixteen mid-biased keyframes: **0 sane** → **`fallback_prior`**. Consensus never fired. ±3% **unproven** on this clip.
