"""Tests for semantic component instance MCP tools."""

import json

import pytest

from mcp_server.project_init import init_project


@pytest.mark.asyncio
async def test_add_component_instance_writes_design_model_and_asset_lock(tmp_path):
    from mcp_server.server import add_component_instance

    init_project(tmp_path, template="empty")

    response = await add_component_instance(
        project_path=str(tmp_path),
        component_id="toilet_floor_mounted_basic",
        position_x=500,
        position_y=700,
        position_z=0,
    )
    data = json.loads(response.text)
    design_model = json.loads((tmp_path / "design_model.json").read_text())
    asset_lock = json.loads((tmp_path / "assets.lock.json").read_text())

    assert data["instance_id"] == "toilet_001"
    assert design_model["components"]["toilet_001"]["component_ref"] == (
        "toilet_floor_mounted_basic"
    )
    assert design_model["components"]["toilet_001"]["bounds"]["min"] == [310.0, 700.0, 0.0]
    assert asset_lock["assets"][0]["component_id"] == "toilet_floor_mounted_basic"
    assert asset_lock["assets"][0]["used_by"] == ["toilet_001"]


@pytest.mark.asyncio
async def test_add_component_instance_uses_project_fixture_dimension_rules(tmp_path):
    from mcp_server.server import add_component_instance, set_fixture_dimension

    init_project(tmp_path, template="empty")
    await set_fixture_dimension(
        project_path=str(tmp_path),
        rule_set="bathroom",
        fixture_name="vanity_wall_600",
        width=500,
        depth=420,
        height=850,
    )

    response = await add_component_instance(
        project_path=str(tmp_path),
        component_id="vanity_wall_600",
        position_x=1000,
        position_y=0,
        position_z=0,
    )
    data = json.loads(response.text)

    assert data["instance"]["dimensions"] == {
        "width": 500.0,
        "depth": 420.0,
        "height": 850.0,
    }


@pytest.mark.asyncio
async def test_add_component_instance_rejects_duplicate_instance_id(tmp_path):
    from mcp_server.server import add_component_instance

    init_project(tmp_path, template="empty")

    await add_component_instance(
        project_path=str(tmp_path),
        component_id="mirror_wall_500",
        position_x=500,
        position_y=0,
        instance_id="mirror_custom",
    )
    response = await add_component_instance(
        project_path=str(tmp_path),
        component_id="mirror_wall_500",
        position_x=800,
        position_y=0,
        instance_id="mirror_custom",
    )

    assert response.text == (
        "Component instance failed: instance already exists: mirror_custom"
    )


@pytest.mark.asyncio
async def test_add_component_instance_rejects_unknown_component(tmp_path):
    from mcp_server.server import add_component_instance

    init_project(tmp_path, template="empty")

    response = await add_component_instance(
        project_path=str(tmp_path),
        component_id="missing_component",
        position_x=0,
        position_y=0,
    )

    assert response.text == (
        "Component instance failed: component not found: missing_component"
    )
