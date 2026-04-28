"""Tests for project asset lock maintenance."""

import json

import pytest

from mcp_server.cli import main
from mcp_server.project_assets import refresh_project_asset_lock
from mcp_server.project_init import init_project


@pytest.mark.asyncio
async def test_refresh_project_asset_lock_marks_cached_assets(tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="empty")
    await server.register_project_component(
        project_path=str(tmp_path),
        component_id="project_display_plinth",
        name="Project display plinth",
        category="furniture",
        width=900,
        depth=450,
        height=750,
        procedural_fallback="box_component",
    )
    await server.add_component_instance(
        project_path=str(tmp_path),
        component_id="project_display_plinth",
        position_x=1000,
        position_y=500,
    )
    asset_file = tmp_path / "assets" / "components" / "project_display_plinth.skp"
    asset_file.parent.mkdir(parents=True, exist_ok=True)
    asset_file.write_text("skp placeholder", encoding="utf-8")

    result = refresh_project_asset_lock(tmp_path)
    lock = json.loads((tmp_path / "assets.lock.json").read_text(encoding="utf-8"))

    assert result["asset_count"] == 1
    assert result["cached_asset_count"] == 1
    assert lock["assets"][0]["cache"]["status"] == "cached"


@pytest.mark.asyncio
async def test_refresh_project_asset_lock_mcp_tool(tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="bathroom")

    response = await server.refresh_project_asset_lock(str(tmp_path))
    data = json.loads(response.text)

    assert data["asset_count"] == 5
    assert data["referenced_asset_count"] == 5
    assert data["missing_asset_count"] == 0


def test_cli_refresh_assets_outputs_json(tmp_path, capsys):
    init_project(tmp_path, template="bathroom")

    exit_code = main(["refresh-assets", str(tmp_path)])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["asset_count"] == 5
    assert data["assets_lock_path"].endswith("assets.lock.json")
