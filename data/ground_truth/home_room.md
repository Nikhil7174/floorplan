# home_room — tape notes

One room. No LiDAR capture (no hardware). Siva (3 Oct): Drive samples have no GT; we tape our own 1–2 rooms.

Photos: originals in `data/raw/home_room_photos/` (4624×3468). Scored still is `00.jpg` (`20261003_214550`).

| | Tape | Pred (`door_height_2.032m`) |
|---|---|---|
| Walls (sorted) | 3.31, 3.38, 3.94, 4.01 m | 5.11, 6.16, 10.25, 11.31 m |
| Area | 13.30 m² | 11.58 m² (−12.9%) |
| Ceiling | 2.76 m | 2.40 m prior |

Wall ±8% **fails**. Area is the honest near-hit. See [`fix_loop/diff.md`](../../fix_loop/diff.md).

Video: original `20261003_210004.mp4` (1920×1080, 61 s, 78 MB) as `data/raw/home_room_video/walk.mp4`. Sixteen mid-biased keyframes: **0 sane**. Mix of too-few lines and `DegenerateIntersectionError` (0–7°). Result **`fallback_prior`** 4×5 m / 20 m² / 2.4 m. Consensus never fired. Same tape: walls +18–27% vs the prior box (not a reconstruction).

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
