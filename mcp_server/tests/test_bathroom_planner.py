"""Tests for the headless bathroom vertical slice."""

import json

import pytest

from mcp_server.resources.design_model_schema import validate_design_model
from mcp_server.resources.design_rules_schema import (
    create_default_design_rules,
    validate_design_rules,
)
from mcp_server.tools.bathroom_planner import (
    plan_bathroom_project,
    save_bathroom_plan,
)


def test_plan_bathroom_project_generates_valid_contracts():
    result = plan_bathroom_project(
        project_name="bathroom_mvp",
        width=2000,
        depth=1800,
        ceiling_height=2400,
    )

    is_valid_model, model_errors = validate_design_model(result["design_model"])
    is_valid_rules, rule_errors = validate_design_rules(result["design_rules"])

    assert is_valid_model is True
    assert model_errors == []
    assert is_valid_rules is True
    assert rule_errors == []
    assert result["validation_report"]["valid"] is True
    assert result["design_model"]["components"]["toilet_001"]["component_ref"] == (
        "toilet_floor_mounted_basic"
    )


def test_plan_bathroom_project_returns_bridge_operation_trace():
    result = plan_bathroom_project()
    operations = result["bridge_operations"]

    operation_types = [operation["operation_type"] for operation in operations]
    component_ids = [
        operation["payload"].get("component_id")
        for operation in operations
        if operation["operation_type"] == "place_component"
    ]

    assert operation_types[:4] == ["create_wall"] * 4
    assert "toilet_floor_mounted_basic" in component_ids
    assert "vanity_wall_600" in component_ids
    assert "bathroom_door_700" in component_ids
    assert operation_types[-1] == "get_scene_info"
    assert all("payload" in operation for operation in operations)


def test_plan_bathroom_project_reports_invalid_small_room():
    result = plan_bathroom_project(width=1400, depth=1300)

    assert result["validation_report"]["valid"] is False
    failed = [
        check["name"]
        for check in result["validation_report"]["checks"]
        if not check["valid"]
    ]
    assert "room_width" in failed
    assert "room_depth" in failed


def test_plan_bathroom_project_uses_fixture_dimension_rules():
    rules = create_default_design_rules()
    rules["rule_sets"]["bathroom"]["fixture_dimensions"]["vanity_wall_600"] = {
        "width": 500,
        "depth": 420,
        "height": 850,
    }

    result = plan_bathroom_project(rules=rules)
    vanity = result["design_model"]["components"]["vanity_001"]

    assert vanity["dimensions"] == {
        "width": 500.0,
        "depth": 420.0,
        "height": 850.0,
    }
    assert vanity["position"][0] == 1750.0
    assert vanity["bounds"]["min"] == [1500.0, 0, 0]


def test_plan_bathroom_project_rejects_non_positive_dimensions():
    with pytest.raises(ValueError, match="positive"):
        plan_bathroom_project(width=0)


def test_save_bathroom_plan_writes_project_files(tmp_path):
    result = plan_bathroom_project(project_name="saved_bathroom")
    written = save_bathroom_plan(tmp_path, result)

    design_model = json.loads((tmp_path / "design_model.json").read_text())
    design_rules = json.loads((tmp_path / "design_rules.json").read_text())
    assets_lock = json.loads((tmp_path / "assets.lock.json").read_text())
    snapshot_manifest = json.loads(
        (tmp_path / "snapshots" / "manifest.json").read_text()
    )
    locked_ids = {asset["component_id"] for asset in assets_lock["assets"]}

    assert written["design_model_path"].endswith("design_model.json")
    assert written["design_rules_path"].endswith("design_rules.json")
    assert written["assets_lock_path"].endswith("assets.lock.json")
    assert written["snapshot_manifest_path"].endswith("snapshots/manifest.json")
    assert design_model["project_name"] == "saved_bathroom"
    assert design_rules["rule_sets"]["bathroom"]["clearances"][
        "toilet_front_clearance"
    ] == 600
    assert "toilet_floor_mounted_basic" in locked_ids
    assert (tmp_path / "assets" / "components").is_dir()
    assert snapshot_manifest["snapshots"] == []
    assert snapshot_manifest["reviews"] == []
