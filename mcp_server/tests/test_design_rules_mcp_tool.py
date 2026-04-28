"""Tests for design rule MCP tools."""

import json

import pytest

from mcp_server.project_init import init_project


@pytest.mark.asyncio
async def test_get_design_rules_tool_reads_project_rules(tmp_path):
    from mcp_server.server import get_design_rules

    init_project(tmp_path, template="bathroom")

    response = await get_design_rules(str(tmp_path))
    data = json.loads(response.text)

    assert data["units"] == "mm"
    assert "bathroom" in data["rule_sets"]


@pytest.mark.asyncio
async def test_set_design_clearance_updates_project_rules(tmp_path):
    from mcp_server.server import get_design_rules, set_design_clearance

    init_project(tmp_path, template="bathroom")

    response = await set_design_clearance(
        project_path=str(tmp_path),
        rule_set="bathroom",
        clearance_name="toilet_front_clearance",
        value=1200,
    )
    update = json.loads(response.text)
    rules_response = await get_design_rules(str(tmp_path))
    rules = json.loads(rules_response.text)

    assert update["value"] == 1200
    assert rules["source"] == "project_user_override"
    assert rules["rule_sets"]["bathroom"]["clearances"][
        "toilet_front_clearance"
    ] == 1200


@pytest.mark.asyncio
async def test_set_design_clearance_creates_missing_rules_file(tmp_path):
    from mcp_server.server import set_design_clearance

    response = await set_design_clearance(
        project_path=str(tmp_path),
        rule_set="bathroom",
        clearance_name="vanity_front_clearance",
        value=900,
    )
    data = json.loads(response.text)
    rules = json.loads((tmp_path / "design_rules.json").read_text())

    assert data["design_rules_path"].endswith("design_rules.json")
    assert rules["rule_sets"]["bathroom"]["clearances"][
        "vanity_front_clearance"
    ] == 900


@pytest.mark.asyncio
async def test_set_design_clearance_rejects_negative_value(tmp_path):
    from mcp_server.server import set_design_clearance

    init_project(tmp_path, template="bathroom")

    response = await set_design_clearance(
        project_path=str(tmp_path),
        rule_set="bathroom",
        clearance_name="toilet_front_clearance",
        value=-1,
    )

    assert "Design rules failed" in response.text


@pytest.mark.asyncio
async def test_set_fixture_dimension_updates_project_rules(tmp_path):
    from mcp_server.server import get_design_rules, set_fixture_dimension

    init_project(tmp_path, template="bathroom")

    response = await set_fixture_dimension(
        project_path=str(tmp_path),
        rule_set="bathroom",
        fixture_name="compact_vanity",
        width=500,
        depth=420,
        height=850,
    )
    update = json.loads(response.text)
    rules_response = await get_design_rules(str(tmp_path))
    rules = json.loads(rules_response.text)

    assert update["dimensions"]["width"] == 500
    assert rules["source"] == "project_user_override"
    assert rules["rule_sets"]["bathroom"]["fixture_dimensions"]["compact_vanity"] == {
        "width": 500,
        "depth": 420,
        "height": 850,
    }


@pytest.mark.asyncio
async def test_set_fixture_dimension_rejects_negative_dimensions(tmp_path):
    from mcp_server.server import set_fixture_dimension

    init_project(tmp_path, template="bathroom")

    response = await set_fixture_dimension(
        project_path=str(tmp_path),
        rule_set="bathroom",
        fixture_name="bad_fixture",
        width=-1,
        depth=420,
        height=850,
    )

    assert "Design rules failed" in response.text


@pytest.mark.asyncio
async def test_set_design_preference_updates_project_preferences(tmp_path):
    from mcp_server.server import get_design_rules, set_design_preference

    init_project(tmp_path, template="bathroom")

    response = await set_design_preference(
        project_path=str(tmp_path),
        preference_name="lighting_temperature",
        value="3000K",
    )
    update = json.loads(response.text)
    rules_response = await get_design_rules(str(tmp_path))
    rules = json.loads(rules_response.text)

    assert update["value"] == "3000K"
    assert rules["source"] == "project_user_override"
    assert rules["preferences"]["lighting_temperature"] == "3000K"


@pytest.mark.asyncio
async def test_designer_profile_tools_create_and_report_status(tmp_path):
    from mcp_server.server import get_designer_profile_status, init_designer_profile

    profile_path = tmp_path / "profile" / "design_rules.json"

    init_response = await init_designer_profile(profile_path=str(profile_path))
    init_data = json.loads(init_response.text)
    status_response = await get_designer_profile_status(profile_path=str(profile_path))
    status_data = json.loads(status_response.text)

    assert init_data["path"] == str(profile_path)
    assert profile_path.exists()
    assert status_data["exists"] is True
    assert status_data["valid"] is True
    assert status_data["source"] == "designer_profile"


@pytest.mark.asyncio
async def test_set_designer_profile_clearance_creates_profile(tmp_path):
    from mcp_server.server import set_designer_profile_clearance

    profile_path = tmp_path / "designer_profile.json"

    response = await set_designer_profile_clearance(
        rule_set="bathroom",
        clearance_name="toilet_front_clearance",
        value=720,
        profile_path=str(profile_path),
    )
    update = json.loads(response.text)
    rules = json.loads(profile_path.read_text(encoding="utf-8"))

    assert update["scope"] == "designer_profile"
    assert update["value"] == 720
    assert rules["source"] == "designer_profile"
    assert rules["rule_sets"]["bathroom"]["clearances"][
        "toilet_front_clearance"
    ] == 720


@pytest.mark.asyncio
async def test_set_designer_profile_fixture_and_preference(tmp_path):
    from mcp_server.server import (
        set_designer_profile_fixture_dimension,
        set_designer_profile_preference,
    )

    profile_path = tmp_path / "designer_profile.json"

    fixture_response = await set_designer_profile_fixture_dimension(
        rule_set="bathroom",
        fixture_name="compact_vanity",
        width=500,
        depth=420,
        height=850,
        profile_path=str(profile_path),
    )
    preference_response = await set_designer_profile_preference(
        preference_name="lighting_temperature",
        value="3000K",
        profile_path=str(profile_path),
    )
    fixture_update = json.loads(fixture_response.text)
    preference_update = json.loads(preference_response.text)
    rules = json.loads(profile_path.read_text(encoding="utf-8"))

    assert fixture_update["scope"] == "designer_profile"
    assert preference_update["scope"] == "designer_profile"
    assert rules["rule_sets"]["bathroom"]["fixture_dimensions"]["compact_vanity"] == {
        "width": 500,
        "depth": 420,
        "height": 850,
    }
    assert rules["preferences"]["lighting_temperature"] == "3000K"
