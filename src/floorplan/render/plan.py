"""Top-down dimensioned plan. Why: the walk-in test wants a rendered artifact, not just JSON."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from floorplan.models import PropertyPlan


def render_plan(plan: PropertyPlan, dest: Path) -> Path:
    """Draw each room polygon with wall lengths and opening ticks."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    for room in plan.rooms:
        poly = np.array(room.polygon_xy, dtype=np.float64)
        closed = np.vstack([poly, poly[0]])
        ax.plot(closed[:, 0], closed[:, 1], color="black", linewidth=2.0)
        ax.fill(poly[:, 0], poly[:, 1], color="#e8eef5", alpha=0.7)
        for i, wall in enumerate(room.walls):
            a = poly[i]
            b = poly[(i + 1) % len(poly)]
            mid = 0.5 * (a + b)
            ax.annotate(
                f"{wall.length_m.value:.2f}m",
                (mid[0], mid[1]),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=8,
            )
            for opening in wall.openings:
                direction = b - a
                length = np.linalg.norm(direction)
                if length < 1e-6:
                    continue
                u = direction / length
                p0 = a + u * opening.t0_m
                p1 = a + u * opening.t1_m
                ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="#c0392b", linewidth=4.0)
        ax.text(
            poly[:, 0].mean(),
            poly[:, 1].mean(),
            f"{room.room_id}\n{room.floor_area_m2.value:.1f} m²\n"
            f"h={room.ceiling_height_m.value:.2f}m",
            ha="center",
            va="center",
            fontsize=9,
        )
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(f"{plan.capture_id} ({plan.tier})")
    ax.set_xlabel("m")
    ax.set_ylabel("m")
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(dest, dpi=140)
    plt.close(fig)
    return dest
