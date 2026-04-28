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
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"
    assert design_model["metadata"]["execution_sync"]["reason"] == "component_instance_added"
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


@pytest.mark.asyncio
async def test_add_component_instance_uses_project_component_library(tmp_path):
    from mcp_server.server import add_component_instance, register_project_component

    init_project(tmp_path, template="empty")
    await register_project_component(
        project_path=str(tmp_path),
        component_id="project_display_plinth",
        name="Project display plinth",
        category="furniture",
        subcategory="display_plinth",
        width=900,
        depth=450,
        height=750,
        procedural_fallback="box_component",
    )
    asset_file = tmp_path / "assets" / "components" / "project_display_plinth.skp"
    asset_file.parent.mkdir(parents=True, exist_ok=True)
    asset_file.write_text("skp placeholder", encoding="utf-8")

    response = await add_component_instance(
        project_path=str(tmp_path),
        component_id="project_display_plinth",
        position_x=1000,
        position_y=500,
        position_z=0,
    )
    data = json.loads(response.text)
    design_model = json.loads((tmp_path / "design_model.json").read_text())
    asset_lock = json.loads((tmp_path / "assets.lock.json").read_text())

    assert data["instance_id"] == "display_plinth_001"
    assert design_model["components"]["display_plinth_001"]["component_ref"] == (
        "project_display_plinth"
    )
    assert asset_lock["assets"][0]["component_id"] == "project_display_plinth"
    assert asset_lock["assets"][0]["cache"]["status"] == "cached"


@pytest.mark.asyncio
async def test_add_component_instance_semantic_centers_component_in_space(tmp_path):
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

    response = await add_component_instance_semantic(
        project_path=str(tmp_path),
        component_id="vanity_wall_600",
        space_id="bathroom_001",
        relation="centered_in_space",
    )
    data = json.loads(response.text)
    design_model = json.loads((tmp_path / "design_model.json").read_text())
    vanity = design_model["components"]["vanity_001"]

    assert data["instance_id"] == "vanity_001"
    assert vanity["position"] == [2000.0, 1270.0, 0.0]
    assert vanity["bounds"]["min"] == [1700.0, 1270.0, 0.0]
    assert vanity["bounds"]["max"] == [2300.0, 1730.0, 850.0]
    assert vanity["semantic_anchor"] == "center"
    assert vanity["relative_to"] == "bathroom_001"
    assert vanity["source"]["semantic_placement"]["relation"] == "centered_in_space"
    assert data["semantic_placement"]["relation"] == "centered_in_space"


@pytest.mark.asyncio
async def test_add_component_instance_semantic_places_against_north_wall(tmp_path):
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

    response = await add_component_instance_semantic(
        project_path=str(tmp_path),
        component_id="vanity_wall_600",
        space_id="bathroom_001",
        relation="against_wall",
        wall_side="north",
    )
    data = json.loads(response.text)
    vanity = data["instance"]

    assert vanity["position"] == [2000.0, 2540.0, 0.0]
    assert vanity["bounds"]["max"][1] == 3000.0
    assert vanity["rotation"] == 180.0
    assert vanity["semantic_anchor"] == "back"
    assert vanity["source"]["semantic_placement"]["wall_side"] == "north"


@pytest.mark.asyncio
async def test_add_component_instance_semantic_rejects_out_of_bounds_offset(tmp_path):
    from mcp_server.server import add_component_instance_semantic, set_project_space

    init_project(tmp_path, template="empty")
    await set_project_space(
        project_path=str(tmp_path),
        space_id="bathroom_001",
        space_type="bathroom",
        width=1000,
        depth=1000,
        height=2400,
    )

    response = await add_component_instance_semantic(
        project_path=str(tmp_path),
        component_id="vanity_wall_600",
        space_id="bathroom_001",
        relation="against_wall",
        wall_side="north",
        offset_along_wall=700,
    )
    design_model = json.loads((tmp_path / "design_model.json").read_text())

    assert response.text.startswith(
        "Semantic component placement failed: component bounds exceed space bounds:"
    )
    assert design_model["components"] == {}


@pytest.mark.asyncio
async def test_execute_component_instance_sends_bridge_operation_and_saves_entity_id(
    monkeypatch,
    tmp_path,
):
    from mcp_server import server

    init_project(tmp_path, template="empty")
    await server.add_component_instance(
        project_path=str(tmp_path),
        component_id="mirror_wall_500",
        position_x=500,
        position_y=0,
        instance_id="mirror_custom",
    )

    captured = {}

    def fake_execute(operations, stop_on_error=True):
        captured["operations"] = operations
        captured["stop_on_error"] = stop_on_error
        return {
            "status": "success",
            "executed_count": 1,
            "requested_count": 1,
            "results": [
                {
                    "operation_id": operations[0]["operation_id"],
                    "operation_type": "place_component",
                    "response": {"result": {"entity_ids": ["42"]}},
                    "ok": True,
                }
            ],
        }

    monkeypatch.setattr(server, "execute_bridge_operations", fake_execute)

    response = await server.execute_component_instance(
        project_path=str(tmp_path),
        instance_id="mirror_custom",
    )
    data = json.loads(response.text)
    design_model = json.loads((tmp_path / "design_model.json").read_text())

    assert data["entity_id"] == "42"
    assert captured["operations"][0]["operation_type"] == "place_component"
    assert captured["operations"][0]["payload"]["instance_id"] == "mirror_custom"
    assert design_model["components"]["mirror_custom"]["entity_id"] == "42"


@pytest.mark.asyncio
async def test_execute_component_instance_reports_missing_instance(tmp_path):
    from mcp_server.server import execute_component_instance

    init_project(tmp_path, template="empty")

    response = await execute_component_instance(
        project_path=str(tmp_path),
        instance_id="missing",
    )

    assert response.text == "Component execution failed: instance not found: missing"
