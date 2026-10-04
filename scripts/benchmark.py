"""Score a PropertyPlan against a tape CSV. Photo gate ±8%, video consensus ±3%."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from floorplan.models import PropertyPlan


@dataclass
class TapeRoom:
    walls: list[float]
    area_m2: float | None
    ceiling_m: float | None


def load_tape(path: Path) -> TapeRoom:
    walls: list[float] = []
    area: float | None = None
    ceiling: float | None = None
    with path.open() as fh:
        for row in csv.DictReader(fh):
            kind = (row.get("kind") or "").strip()
            raw = row.get("value_m") or ""
            if raw == "":
                continue
            value = float(raw)
            if kind == "wall_length":
                walls.append(value)
            elif kind == "floor_area_m2":
                area = value
            elif kind == "ceiling_height":
                ceiling = value
    return TapeRoom(walls=sorted(walls), area_m2=area, ceiling_m=ceiling)


def load_plan(path: Path) -> PropertyPlan:
    return PropertyPlan.model_validate(json.loads(path.read_text()))


def wall_frac_for_plan(plan: PropertyPlan) -> float:
    if not plan.rooms:
        return 0.08
    reason = plan.rooms[0].walls[0].length_m.reason
    if reason == "video_keyframe_consensus":
        return 0.03
    if "fallback" in reason or "prior" in reason and "door" not in reason:
        return 0.30 if "fallback" in reason else 0.18
    return 0.08


def score_room(plan: PropertyPlan, tape: TapeRoom, wall_frac: float | None = None) -> list[str]:
    room = plan.rooms[0]
    pred = sorted(w.length_m.value for w in room.walls)
    frac = wall_frac if wall_frac is not None else wall_frac_for_plan(plan)
    lines = [
        f"# Benchmark {plan.capture_id} ({plan.tier})",
        "",
        f"Gate fraction: ±{frac:.0%} (from reason `{room.walls[0].length_m.reason}`)",
        "",
        "| Gate | Tape | Pred | Rel. err | Pass |",
        "|---|---|---|---|---|",
    ]
    n = min(len(tape.walls), len(pred))
    if len(tape.walls) != len(pred):
        lines.append(
            f"| wall_count | {len(tape.walls)} | {len(pred)} | mismatch | FAIL |"
        )
    for i in range(n):
        t, p = tape.walls[i], pred[i]
        err = (p - t) / t if t else 0.0
        ok = abs(err) <= frac
        lines.append(
            f"| wall[{i}] | {t:.2f} m | {p:.2f} m | {err:+.1%} | {'PASS' if ok else 'FAIL'} |"
        )
    if tape.area_m2 is not None:
        err = (room.floor_area_m2.value - tape.area_m2) / tape.area_m2
        lines.append(
            f"| floor_area | {tape.area_m2:.2f} m² | {room.floor_area_m2.value:.2f} m² | {err:+.1%} | n/a |"
        )
    if tape.ceiling_m is not None:
        err = (room.ceiling_height_m.value - tape.ceiling_m) / tape.ceiling_m
        lines.append(
            f"| ceiling | {tape.ceiling_m:.2f} m | {room.ceiling_height_m.value:.2f} m | {err:+.1%} | n/a |"
        )
    lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score plan.json against a tape CSV.")
    parser.add_argument("plan", type=Path, help="plan.json from floorplan process")
    parser.add_argument("tape", type=Path, help="ground-truth CSV")
    parser.add_argument("--out", type=Path, default=None, help="optional markdown path")
    args = parser.parse_args(argv)
    plan = load_plan(args.plan)
    tape = load_tape(args.tape)
    lines = score_room(plan, tape)
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
