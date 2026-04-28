"""Tests for the bathroom planning MCP tool wrapper."""

import json

import pytest

from mcp_server.resources.design_rules_schema import create_default_design_rules


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
    assert (tmp_path / "assets.lock.json").exists()
    assert (tmp_path / "assets" / "components").is_dir()
    assert (tmp_path / "snapshots" / "manifest.json").exists()
    assert data["written_files"]["design_model_path"].endswith("design_model.json")
    assert data["written_files"]["assets_lock_path"].endswith("assets.lock.json")


@pytest.mark.asyncio
async def test_plan_bathroom_tool_uses_project_design_rules(tmp_path):
    from mcp_server.server import plan_bathroom

    rules = create_default_design_rules()
    rules["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = 1200
    (tmp_path / "design_rules.json").write_text(
        json.dumps(rules, indent=2) + "\n",
        encoding="utf-8",
    )

    response = await plan_bathroom(project_path=str(tmp_path), depth=1800)
    data = json.loads(response.text)
    toilet_front = next(
        check
        for check in data["validation_report"]["checks"]
        if check["name"] == "toilet_front_clearance"
    )

    assert data["validation_report"]["valid"] is False
    assert toilet_front["required"] == 1200


@pytest.mark.asyncio
async def test_execute_bathroom_plan_tool_uses_trace_executor(monkeypatch):
    from mcp_server import server

    def fake_execute(operations, stop_on_error=True):
        return {
            "status": "success",
            "executed_count": len(operations),
            "requested_count": len(operations),
            "results": [],
        }

    monkeypatch.setattr(server, "execute_bridge_operations", fake_execute)

    response = await server.execute_bathroom_plan(project_name="execute_fixture")
    data = json.loads(response.text)

    assert data["design_model"]["project_name"] == "execute_fixture"
    assert data["execution_report"]["status"] == "success"
    assert data["execution_report"]["executed_count"] == 10


@pytest.mark.asyncio
async def test_execute_bathroom_plan_tool_uses_project_design_rules(
    monkeypatch,
    tmp_path,
):
    from mcp_server import server

    def fake_execute(operations, stop_on_error=True):
        return {
            "status": "success",
            "executed_count": len(operations),
            "requested_count": len(operations),
            "results": [],
        }

    rules = create_default_design_rules()
    rules["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = 1200
    (tmp_path / "design_rules.json").write_text(
        json.dumps(rules, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "execute_bridge_operations", fake_execute)

    response = await server.execute_bathroom_plan(project_path=str(tmp_path))
    data = json.loads(response.text)
    toilet_front = next(
        check
        for check in data["validation_report"]["checks"]
        if check["name"] == "toilet_front_clearance"
    )

    assert data["validation_report"]["valid"] is False
    assert toilet_front["required"] == 1200
