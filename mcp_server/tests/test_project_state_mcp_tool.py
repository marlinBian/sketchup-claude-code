"""Tests for project state MCP tools."""

import json

import pytest

from mcp_server.project_init import init_project


@pytest.mark.asyncio
async def test_get_project_state_reads_design_model(tmp_path):
    from mcp_server.server import get_project_state

    init_project(tmp_path, project_name="State Test", template="bathroom")

    response = await get_project_state(str(tmp_path))
    data = json.loads(response.text)

    assert data["project_path"] == str(tmp_path.resolve())
    assert data["design_model_path"].endswith("design_model.json")
    assert data["design_model"]["project_name"] == "State Test"
    assert "toilet_001" in data["design_model"]["components"]


@pytest.mark.asyncio
async def test_get_project_state_reports_missing_model(tmp_path):
    from mcp_server.server import get_project_state

    response = await get_project_state(str(tmp_path))

    assert response.text.startswith("Project state failed:")
    assert "File not found" in response.text


@pytest.mark.asyncio
async def test_list_project_components_includes_lighting_by_default(tmp_path):
    from mcp_server.server import list_project_components

    init_project(tmp_path, template="bathroom")

    response = await list_project_components(str(tmp_path))
    data = json.loads(response.text)

    ids = {component["id"] for component in data["components"]}
    kinds = {component["kind"] for component in data["components"]}

    assert data["count"] == 5
    assert "toilet_001" in ids
    assert "ceiling_light_001" in ids
    assert kinds == {"component", "lighting"}


@pytest.mark.asyncio
async def test_list_project_components_can_exclude_lighting(tmp_path):
    from mcp_server.server import list_project_components

    init_project(tmp_path, template="bathroom")

    response = await list_project_components(str(tmp_path), include_lighting=False)
    data = json.loads(response.text)

    ids = {component["id"] for component in data["components"]}

    assert data["count"] == 4
    assert "ceiling_light_001" not in ids


@pytest.mark.asyncio
async def test_validate_design_project_uses_cli_validation(tmp_path):
    from mcp_server.server import validate_design_project

    init_project(tmp_path, template="bathroom")

    response = await validate_design_project(str(tmp_path))
    data = json.loads(response.text)

    assert data["ok"] is True
    assert {check["name"] for check in data["checks"]} >= {
        "design_model",
        "design_rules",
        "assets_lock",
        "asset_refs_locked",
    }
