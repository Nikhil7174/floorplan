from floorplan.pipeline import process_capture
from floorplan.schema.validate import validate_plan


def test_cli_output_validates(single_room, fast_config) -> None:
    plan = process_capture(single_room, fast_config)
    payload = validate_plan(plan)
    assert payload["schema_version"] == "1.0.0"
    assert payload["rooms"][0]["walls"]
    height = payload["rooms"][0]["ceiling_height_m"]
    assert height["lo"] <= height["value"] <= height["hi"]
