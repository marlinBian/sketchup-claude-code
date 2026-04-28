"""Tests for the bathroom planning MCP tool wrapper."""

import json

import pytest


@pytest.mark.asyncio
async def test_plan_bathroom_tool_returns_json_text():
    from mcp_server.server import plan_bathroom

    response = await plan_bathroom(
        project_name="tool_bathroom",
        width=2000,
        depth=1800,
        ceiling_height=2400,
    )
    data = json.loads(response.text)

    assert data["design_model"]["project_name"] == "tool_bathroom"
    assert data["validation_report"]["valid"] is True


@pytest.mark.asyncio
async def test_plan_bathroom_tool_writes_project_files(tmp_path):
    from mcp_server.server import plan_bathroom

    response = await plan_bathroom(project_path=str(tmp_path))
    data = json.loads(response.text)

    assert (tmp_path / "design_model.json").exists()
    assert (tmp_path / "design_rules.json").exists()
    assert data["written_files"]["design_model_path"].endswith("design_model.json")
