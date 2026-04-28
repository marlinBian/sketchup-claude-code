"""Tests for component registry MCP tools."""

import json

import pytest

from mcp_server.project_init import init_project


@pytest.mark.asyncio
async def test_search_components_returns_machine_readable_manifest_data():
    from mcp_server.server import search_components

    response = await search_components(query="toilet", category="fixture", limit=2)
    data = json.loads(response.text)

    assert data["query"] == "toilet"
    assert data["category"] == "fixture"
    assert data["count"] >= 1
    assert data["components"][0]["id"] == "toilet_floor_mounted_basic"
    assert data["components"][0]["dimensions"]["width"] == 380
    assert data["components"][0]["anchors"]["back"] == "wall"
    assert "_match_score" in data["components"][0]


@pytest.mark.asyncio
async def test_search_components_supports_chinese_aliases():
    from mcp_server.server import search_components

    response = await search_components(query="马桶", category="fixture", limit=5)
    data = json.loads(response.text)

    assert data["components"][0]["id"] == "toilet_floor_mounted_basic"


@pytest.mark.asyncio
async def test_get_component_manifest_returns_one_component_by_id():
    from mcp_server.server import get_component_manifest

    response = await get_component_manifest("vanity_wall_600")
    data = json.loads(response.text)

    assert data["component_id"] == "vanity_wall_600"
    assert data["component"]["category"] == "fixture"
    assert data["component"]["dimensions"]["width"] == 600
    assert data["component"]["clearance"]["front"] == 700


@pytest.mark.asyncio
async def test_get_component_manifest_reports_missing_component():
    from mcp_server.server import get_component_manifest

    response = await get_component_manifest("missing_component")

    assert response.text == "Component not found: missing_component"


@pytest.mark.asyncio
async def test_register_project_component_adds_searchable_project_manifest(tmp_path):
    from mcp_server.server import (
        get_component_manifest,
        list_local_library_categories,
        register_project_component,
        search_components,
    )

    init_project(tmp_path, template="empty")

    response = await register_project_component(
        project_path=str(tmp_path),
        component_id="project_display_plinth",
        name="Project display plinth",
        category="furniture",
        subcategory="display_plinth",
        width=900,
        depth=450,
        height=750,
        aliases_en=["display stand"],
        aliases_zh_cn=["展示台"],
        tags=["project-local", "display"],
        procedural_fallback="box_component",
    )
    data = json.loads(response.text)
    project_library = json.loads((tmp_path / "component_library.json").read_text())
    search_response = await search_components(
        query="展示台",
        project_path=str(tmp_path),
    )
    search_data = json.loads(search_response.text)
    manifest_response = await get_component_manifest(
        "project_display_plinth",
        project_path=str(tmp_path),
    )
    manifest_data = json.loads(manifest_response.text)
    categories_response = await list_local_library_categories(project_path=str(tmp_path))

    assert data["component_id"] == "project_display_plinth"
    assert project_library["components"][0]["id"] == "project_display_plinth"
    assert search_data["components"][0]["id"] == "project_display_plinth"
    assert manifest_data["component"]["dimensions"]["width"] == 900
    assert "furniture" in categories_response.text


@pytest.mark.asyncio
async def test_register_project_component_rejects_packaged_component_id(tmp_path):
    from mcp_server.server import register_project_component

    init_project(tmp_path, template="empty")

    response = await register_project_component(
        project_path=str(tmp_path),
        component_id="toilet_floor_mounted_basic",
        name="Duplicate toilet",
        category="fixture",
        width=380,
        depth=700,
        height=760,
    )

    assert response.text == (
        "Project component failed: component ID already exists in packaged registry: "
        "toilet_floor_mounted_basic"
    )


@pytest.mark.asyncio
async def test_register_selected_component_infers_manifest_from_selection(
    monkeypatch,
    tmp_path,
):
    import mcp_server.server as server

    init_project(tmp_path, template="empty")

    monkeypatch.setattr(
        server,
        "selection_info_from_bridge",
        lambda limit=100: {
            "selected_count": 1,
            "entities": [
                {
                    "entityID": "42",
                    "type": "group",
                    "layer": "Furniture",
                    "name": "SketchUp console",
                    "definition_name": "Console table",
                    "bounding_box": {
                        "min": [100, 200, 0],
                        "max": [900, 500, 850],
                    },
                }
            ],
        },
    )

    response = await server.register_selected_component(
        project_path=str(tmp_path),
        component_id="selected_console_table",
        category="furnitures",
        subcategory="console_table",
        anchor_back="wall",
        clearance_front=700,
    )
    data = json.loads(response.text)
    project_library = json.loads((tmp_path / "component_library.json").read_text())

    assert data["component_id"] == "selected_console_table"
    assert data["source_selection"]["entity_id"] == "42"
    assert data["source_selection"]["definition_name"] == "Console table"
    assert data["selection_count"] == 1
    assert data["component"]["name"] == "Console table"
    assert data["component"]["category"] == "furniture"
    assert data["component"]["dimensions"] == {
        "width": 800.0,
        "depth": 300.0,
        "height": 850.0,
    }
    assert data["component"]["anchors"]["back"] == "wall"
    assert data["component"]["clearance"]["front"] == 700
    assert data["component"]["license"]["source"] == "sketchup_selection"
    assert "sketchup-selection" in data["component"]["tags"]
    assert project_library["components"][0]["id"] == "selected_console_table"


@pytest.mark.asyncio
async def test_register_selected_component_reports_empty_selection(monkeypatch, tmp_path):
    import mcp_server.server as server

    init_project(tmp_path, template="empty")

    monkeypatch.setattr(
        server,
        "selection_info_from_bridge",
        lambda limit=100: {"selected_count": 0, "entities": []},
    )

    response = await server.register_selected_component(
        project_path=str(tmp_path),
        component_id="selected_empty",
    )

    assert response.text == (
        "Project component from selection failed: no SketchUp entities selected."
    )


@pytest.mark.asyncio
async def test_register_selected_component_rejects_degenerate_bounds(
    monkeypatch,
    tmp_path,
):
    import mcp_server.server as server

    init_project(tmp_path, template="empty")

    monkeypatch.setattr(
        server,
        "selection_info_from_bridge",
        lambda limit=100: {
            "selected_count": 1,
            "entities": [
                {
                    "entityID": "7",
                    "type": "face",
                    "layer": "Layer0",
                    "name": "Flat face",
                    "bounding_box": {
                        "min": [0, 0, 0],
                        "max": [1000, 500, 0],
                    },
                }
            ],
        },
    )

    response = await server.register_selected_component(
        project_path=str(tmp_path),
        component_id="selected_flat_face",
    )

    assert response.text == (
        "Project component from selection failed: selected entity bounds are "
        "degenerate; select a 3D group or component, or register dimensions "
        "explicitly."
    )
