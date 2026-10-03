"""Single graded entrypoint. One command per capture folder."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from floorplan.config import load_config
from floorplan.exceptions import FloorplanError
from floorplan.pipeline import process_capture
from floorplan.render.plan import render_plan

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Floor plan reconstruction CLI.")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def process(
    capture: Path = typer.Argument(..., exists=True, file_okay=False, help="Capture folder."),
    out: Path = typer.Option(..., "--out", help="Directory for plan.json and plan.png."),
    config: Path | None = typer.Option(None, "--config", help="YAML config; default configs/default.yaml."),
) -> None:
    """Run the pipeline on one capture. Auto-detects the tier from folder contents."""

    _configure_logging()
    logger = logging.getLogger("floorplan.cli")
    cfg = load_config(config)
    try:
        plan = process_capture(capture, cfg)
    except FloorplanError as exc:
        logger.error("%s", exc)
        raise typer.Exit(code=1) from exc
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "plan.json"
    json_path.write_text(json.dumps(plan.model_dump(), indent=2) + "\n")
    png_path = render_plan(plan, out / "plan.png")
    logger.info("Wrote %s and %s", json_path, png_path)


@app.callback()
def _root() -> None:
    """Dimensioned floor plans from a capture folder."""


def main() -> None:
    app()
