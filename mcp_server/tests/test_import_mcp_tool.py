"""Tests for import MCP tools and CLI commands."""

import json

import pytest

from mcp_server.cli import main
from mcp_server.project_init import init_project


def make_source(tmp_path, name="floorplan.pdf"):
    """Create a source file fixture."""
    source = tmp_path / name
    source.write_bytes(b"source fixture\n")
    return source


@pytest.mark.asyncio
async def test_import_floorplan_to_model_tool_writes_project_truth(tmp_path):
    from mcp_server import server

    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)

    response = await server.import_floorplan_to_model(
        project_path=str(project),
        source_path=str(source),
        import_id="import_001",
        width=5000,
        depth=3600,
    )
    data = json.loads(response.text)
    state_response = await server.get_import_summary(str(project), "import_001")
    list_response = await server.list_import_sessions(str(project))
    state = json.loads(state_response.text)
    listed = json.loads(list_response.text)

    assert data["status"] == "imported"
    assert data["summary"]["wall_count"] == 4
    assert state["model_import_sessions"]["import_001"]["scale"]["width"] == 5000.0
    assert listed["count"] == 1
    assert listed["imports"][0]["import_id"] == "import_001"


@pytest.mark.asyncio
async def test_rescale_and_repair_tools_patch_imported_truth(tmp_path):
    from mcp_server import server

    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    await server.import_floorplan_to_model(
        project_path=str(project),
        source_path=str(source),
        import_id="import_001",
    )

    rescale_response = await server.rescale_imported_model(
        project_path=str(project),
        import_id="import_001",
        target_width=8000,
    )
    repair_response = await server.repair_imported_region(
        project_path=str(project),
        import_id="import_001",
        wall_thickness=150,
        notes="Corrected shell thickness.",
    )
    review_response = await server.review_model_against_import_source(
        project_path=str(project),
        import_id="import_001",
        target_id="import_001_wall_north",
    )

    assert json.loads(rescale_response.text)["status"] == "rescaled"
    assert json.loads(repair_response.text)["status"] == "repaired"
    assert "import_001_wall_north" in json.loads(review_response.text)[
        "matched_model_entities"
    ]["walls"]


def test_cli_import_floorplan_summary_and_rescale(tmp_path, capsys):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)

    exit_code = main(
        [
            "import-floorplan",
            str(project),
            str(source),
            "--import-id",
            "import_001",
            "--width",
            "6000",
            "--depth",
            "4200",
            "--force",
        ]
    )
    import_output = json.loads(capsys.readouterr().out)
    summary_code = main(["import-summary", str(project), "--import-id", "import_001"])
    summary_output = json.loads(capsys.readouterr().out)
    list_code = main(["list-imports", str(project)])
    list_output = json.loads(capsys.readouterr().out)
    rescale_code = main(
        [
            "rescale-import",
            str(project),
            "import_001",
            "--target-width",
            "9000",
        ]
    )
    rescale_output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary_code == 0
    assert list_code == 0
    assert rescale_code == 0
    assert import_output["status"] == "imported"
    assert summary_output["count"] == 1
    assert list_output["imports"][0]["import_id"] == "import_001"
    assert rescale_output["scale_x"] == 1.5
