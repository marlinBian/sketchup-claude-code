"""Tests for component registry MCP tools."""

import json

import pytest


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
