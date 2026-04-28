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
