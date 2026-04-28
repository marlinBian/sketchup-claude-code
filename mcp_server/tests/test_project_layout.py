"""Tests for project layout validation."""

import json

import pytest

from mcp_server.project_init import init_project
from mcp_server.project_layout import validate_project_layout


def failed_checks(result, name):
    return [
        check
        for check in result["checks"]
        if check["name"] == name and not check.get("valid", False)
    ]


def test_validate_project_layout_accepts_initialized_bathroom(tmp_path):
    init_project(tmp_path, template="bathroom")

    result = validate_project_layout(tmp_path)

    assert result["ok"] is True
    assert result["failed_count"] == 0


@pytest.mark.asyncio
async def test_validate_project_layout_detects_component_overlap(tmp_path):
    from mcp_server.server import add_component_instance_semantic, set_project_space

    init_project(tmp_path, template="empty")
    await set_project_space(
        project_path=str(tmp_path),
        space_id="bathroom_001",
        space_type="bathroom",
        width=4000,
        depth=3000,
        height=2400,
    )
    for instance_id in ("vanity_001", "vanity_duplicate"):
        response = await add_component_instance_semantic(
            project_path=str(tmp_path),
            component_id="vanity_wall_600",
            space_id="bathroom_001",
            relation="against_wall",
            wall_side="north",
            instance_id=instance_id,
        )
        assert json.loads(response.text)["instance_id"] == instance_id

    result = validate_project_layout(tmp_path)

    assert result["ok"] is False
    overlaps = failed_checks(result, "component_overlap")
    assert overlaps
    assert overlaps[0]["instances"] == ["vanity_001", "vanity_duplicate"]


@pytest.mark.asyncio
async def test_validate_project_layout_detects_front_clearance_failure(tmp_path):
    from mcp_server.server import add_component_instance_semantic, set_project_space

    init_project(tmp_path, template="empty")
    await set_project_space(
        project_path=str(tmp_path),
        space_id="bathroom_001",
        space_type="bathroom",
        width=4000,
        depth=1000,
        height=2400,
    )
    await add_component_instance_semantic(
        project_path=str(tmp_path),
        component_id="vanity_wall_600",
        space_id="bathroom_001",
        relation="against_wall",
        wall_side="north",
    )

    result = validate_project_layout(tmp_path)

    assert result["ok"] is False
    clearances = failed_checks(result, "front_clearance")
    assert clearances
    assert clearances[0]["available"] == 540.0
    assert clearances[0]["required"] == 700.0


@pytest.mark.asyncio
async def test_validate_project_layout_mcp_tool_returns_json(tmp_path):
    from mcp_server.server import validate_project_layout as validate_tool

    init_project(tmp_path, template="bathroom")

    response = await validate_tool(project_path=str(tmp_path))
    result = json.loads(response.text)

    assert result["ok"] is True
    assert result["project_path"] == str(tmp_path.resolve())
