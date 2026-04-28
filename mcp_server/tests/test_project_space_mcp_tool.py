"""Tests for project-backed space editing MCP tools."""

import json

import pytest

from mcp_server.project_init import init_project
from mcp_server.resources.design_model_schema import save_design_model
from mcp_server.tools.project_executor import build_project_execution_plan


@pytest.mark.asyncio
async def test_set_project_space_writes_rectangular_space_truth(tmp_path):
    from mcp_server.server import get_project_state, set_project_space

    init_project(tmp_path, template="empty")

    response = await set_project_space(
        project_path=str(tmp_path),
        space_id="studio_001",
        space_type="office",
        width=4000,
        depth=5000,
        height=2800,
    )
    data = json.loads(response.text)
    design_model = json.loads((tmp_path / "design_model.json").read_text())
    state_response = await get_project_state(str(tmp_path))
    state = json.loads(state_response.text)
    plan = build_project_execution_plan(tmp_path)

    assert data["space_id"] == "studio_001"
    assert data["space"]["bounds"]["max"] == [4000.0, 5000.0, 2800.0]
    assert design_model["spaces"]["studio_001"]["center"] == [2000.0, 2500.0, 1400.0]
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"
    assert state["execution"]["sync_status"] == "dirty"
    assert plan["skipped_count"] == 0
    assert [operation["operation_type"] for operation in plan["bridge_operations"][:4]] == [
        "create_wall",
        "create_wall",
        "create_wall",
        "create_wall",
    ]
    assert plan["bridge_operations"][0]["payload"]["space_id"] == "studio_001"


@pytest.mark.asyncio
async def test_set_project_space_clears_stale_wall_execution_feedback(tmp_path):
    from mcp_server.server import set_project_space

    init_project(tmp_path, template="empty")
    design_model_path = tmp_path / "design_model.json"
    design_model = json.loads(design_model_path.read_text())
    design_model["spaces"]["studio_001"] = {
        "type": "office",
        "bounds": {"min": [0, 0, 0], "max": [3000, 3000, 2400]},
        "center": [1500, 1500, 1200],
        "execution": {
            "walls": {
                "south": {
                    "operation_id": "wall_studio_001_south",
                    "entity_ids": ["stale-wall"],
                }
            }
        },
    }
    saved, errors = save_design_model(str(design_model_path), design_model)
    assert saved, errors

    response = await set_project_space(
        project_path=str(tmp_path),
        space_id="studio_001",
        space_type="office",
        width=4200,
        depth=3000,
        height=2600,
    )
    data = json.loads(response.text)
    design_model = json.loads(design_model_path.read_text())

    assert data["previous_execution_cleared"] is True
    assert "execution" not in design_model["spaces"]["studio_001"]
    assert design_model["spaces"]["studio_001"]["bounds"]["max"] == [
        4200.0,
        3000.0,
        2600.0,
    ]


@pytest.mark.asyncio
async def test_set_project_space_rejects_invalid_space_type(tmp_path):
    from mcp_server.server import set_project_space

    init_project(tmp_path, template="empty")

    response = await set_project_space(
        project_path=str(tmp_path),
        space_id="studio_001",
        space_type="unsupported",
        width=4000,
        depth=5000,
    )

    assert response.text.startswith("Project space failed: space_type must be one of:")
