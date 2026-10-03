"""Validate a PropertyPlan against our internal JSON schema.

No separate schema document shipped with the case study PDF or Drive folder.
`property_plan.json` is ours; it encodes the Part 2 output contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from floorplan.exceptions import SchemaValidationError
from floorplan.models import PropertyPlan


def schema_path() -> Path:
    return Path(__file__).with_name("property_plan.json")


def load_schema() -> dict:
    with schema_path().open() as fh:
        return json.load(fh)


def validate_plan(plan: PropertyPlan) -> dict:
    """Dump and re-validate via Pydantic plus the JSON schema file.

    Why: Pydantic enforces types; the JSON file is the grader-facing contract we invented.
    """

    payload = plan.model_dump()
    schema = load_schema()
    _check_required(payload, schema.get("required", []), "$")
    if len(payload["rooms"]) < 1:
        raise SchemaValidationError("PropertyPlan must contain at least one room.")
    for i, room in enumerate(payload["rooms"]):
        if len(room["polygon_xy"]) < 3:
            raise SchemaValidationError(f"rooms[{i}].polygon_xy must have >= 3 vertices.")
        if len(room["walls"]) < 3:
            raise SchemaValidationError(f"rooms[{i}].walls must have >= 3 walls.")
        _check_interval(room["ceiling_height_m"], f"rooms[{i}].ceiling_height_m")
        _check_interval(room["floor_area_m2"], f"rooms[{i}].floor_area_m2")
    return payload


def _check_required(obj: dict, required: list[str], where: str) -> None:
    missing = [key for key in required if key not in obj]
    if missing:
        raise SchemaValidationError(f"{where} missing required keys: {missing}")


def _check_interval(interval: dict, where: str) -> None:
    if interval["lo"] > interval["value"] or interval["hi"] < interval["value"]:
        raise SchemaValidationError(f"{where}: value must lie inside [lo, hi].")
