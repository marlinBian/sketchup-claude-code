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


def create_offset_right_boundary(project):
    """Create a near-boundary imported wall offset fixture."""
    design_model_path = project / "design_model.json"
    design_model = json.loads(design_model_path.read_text(encoding="utf-8"))
    east_wall = design_model["walls"]["import_001_wall_east"]
    east_wall["path"] = [[6000.0, 4000.0, 0], [6000.0, 2200.0, 0]]
    design_model["walls"]["import_001_wall_east_step"] = {
        **east_wall,
        "path": [[6000.0, 2200.0, 0], [5880.0, 2200.0, 0]],
    }
    design_model["walls"]["import_001_wall_east_lower"] = {
        **east_wall,
        "path": [[5880.0, 2200.0, 0], [5880.0, 0.0, 0]],
    }
    generated = design_model["import_sessions"]["import_001"]["generated_model"]
    generated["wall_ids"].extend(
        ["import_001_wall_east_step", "import_001_wall_east_lower"]
    )
    generated["changed_model_ids"].extend(
        ["import_001_wall_east_step", "import_001_wall_east_lower"]
    )
    design_model_path.write_text(
        json.dumps(design_model, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_missing_boundary_wall_gap(project):
    """Create a long uncovered imported footprint edge segment."""
    design_model_path = project / "design_model.json"
    design_model = json.loads(design_model_path.read_text(encoding="utf-8"))
    design_model["walls"]["import_001_wall_south"]["path"] = [
        [1500.0, 0.0, 0.0],
        [6000.0, 0.0, 0.0],
    ]
    design_model_path.write_text(
        json.dumps(design_model, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_shell_overreach(project):
    """Create imported wall geometry that encloses area outside the footprint."""
    design_model_path = project / "design_model.json"
    design_model = json.loads(design_model_path.read_text(encoding="utf-8"))
    footprint = design_model["spaces"]["import_001_space_001"]["footprint"]
    min_x = min(float(point[0]) for point in footprint)
    max_x = max(float(point[0]) for point in footprint)
    min_y = min(float(point[1]) for point in footprint)
    max_y = max(float(point[1]) for point in footprint)
    overreach_x = max_x + 1200.0
    design_model["walls"]["import_001_wall_south"]["path"] = [
        [min_x, min_y, 0.0],
        [overreach_x, min_y, 0.0],
    ]
    design_model["walls"]["import_001_wall_east"]["path"] = [
        [overreach_x, min_y, 0.0],
        [overreach_x, max_y, 0.0],
    ]
    generated = design_model["import_sessions"]["import_001"]["generated_model"]
    for wall_id in ("import_001_wall_south", "import_001_wall_east"):
        if wall_id not in generated["changed_model_ids"]:
            generated["changed_model_ids"].append(wall_id)
    design_model_path.write_text(
        json.dumps(design_model, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_source_evidence_short_boundary_gap(project):
    """Create a short boundary gap without source wall evidence."""
    design_model_path = project / "design_model.json"
    design_model = json.loads(design_model_path.read_text(encoding="utf-8"))
    source = {
        "kind": "import_floorplan",
        "import_id": "import_001",
        "confidence": 0.7,
        "assumptions": ["Short gap fixture without source wall evidence."],
    }
    living = design_model["spaces"]["import_001_space_001"]
    living["type"] = "living_room"
    living["source"] = source
    design_model["spaces"]["import_001_balcony_001"] = {
        "type": "balcony",
        "bounds": {"min": [3000.0, -1000.0, 0.0], "max": [4200.0, 0.0, 2800.0]},
        "center": [3600.0, -500.0, 1400.0],
        "footprint": [
            [3000.0, 0.0, 0.0],
            [4200.0, 0.0, 0.0],
            [4200.0, -1000.0, 0.0],
            [3000.0, -1000.0, 0.0],
        ],
        "source": source,
    }
    reference_wall = design_model["walls"]["import_001_wall_south"]
    reference_wall["path"] = [[0.0, 0.0, 0.0], [3400.0, 0.0, 0.0]]
    design_model["walls"]["import_001_wall_south_right"] = {
        **reference_wall,
        "path": [[3900.0, 0.0, 0.0], [6000.0, 0.0, 0.0]],
    }
    generated = design_model["import_sessions"]["import_001"]["generated_model"]
    if "import_001_balcony_001" not in generated["space_ids"]:
        generated["space_ids"].append("import_001_balcony_001")
    if "import_001_wall_south_right" not in generated["wall_ids"]:
        generated["wall_ids"].append("import_001_wall_south_right")
    generated["changed_model_ids"].extend(
        ["import_001_balcony_001", "import_001_wall_south_right"]
    )
    design_model_path.write_text(
        json.dumps(design_model, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
    constraints_path = project / "imports" / "import_001" / "constraints.json"
    constraints_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "import_id": "import_001",
                "provenance": {"origin": "vision_extracted"},
                "opening_constraints": [
                    {
                        "id": "import_001_door_001",
                        "host_wall": "import_001_wall_south",
                        "host_wall_axis": "horizontal",
                        "interval": [2050, 2950],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    constraint_response = await server.validate_import_source_constraints(
        project_path=str(project),
        import_id="import_001",
        require_extracted_evidence=True,
    )
    state_response = await server.get_import_summary(str(project), "import_001")
    list_response = await server.list_import_sessions(str(project))
    constraint_data = json.loads(constraint_response.text)
    state = json.loads(state_response.text)
    listed = json.loads(list_response.text)

    assert data["status"] == "imported"
    assert data["summary"]["wall_count"] == 4
    assert constraint_data["status"] == "passed"
    assert state["model_import_sessions"]["import_001"]["scale"]["width"] == 5000.0
    assert state["model_import_sessions"]["import_001"]["source_fidelity"]["status"] == "passed"
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


@pytest.mark.asyncio
async def test_normalize_imported_wall_alignment_tool_repairs_offset(tmp_path):
    from mcp_server import server

    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    await server.import_floorplan_to_model(
        project_path=str(project),
        source_path=str(source),
        import_id="import_001",
        width=6000,
        depth=4000,
    )
    create_offset_right_boundary(project)

    response = await server.normalize_imported_wall_alignment(
        project_path=str(project),
        import_id="import_001",
        tolerance=160,
    )
    data = json.loads(response.text)

    assert data["status"] == "normalized"
    assert data["snap_maps"]["x"]["5880.0"] == 6000.0
    assert "import_001_wall_east_step" in data["removed_walls"]


@pytest.mark.asyncio
async def test_repair_imported_corner_notch_tool_restores_step(tmp_path):
    from mcp_server import server

    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    await server.import_floorplan_to_model(
        project_path=str(project),
        source_path=str(source),
        import_id="import_001",
        width=6000,
        depth=4000,
    )

    response = await server.repair_imported_corner_notch(
        project_path=str(project),
        import_id="import_001",
        corner="top_left",
        horizontal_offset=500,
        vertical_offset=600,
        target_space_id="import_001_space_001",
    )
    data = json.loads(response.text)

    assert data["status"] == "repaired"
    assert data["added_walls"] == [
        "import_001_top_left_notch_vertical",
        "import_001_top_left_notch_horizontal",
    ]
    assert "import_001_space_001" in data["changed_spaces"]


@pytest.mark.asyncio
async def test_boundary_coverage_tools_review_and_repair_missing_wall(tmp_path):
    from mcp_server import server

    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    await server.import_floorplan_to_model(
        project_path=str(project),
        source_path=str(source),
        import_id="import_001",
        width=6000,
        depth=4000,
    )
    create_missing_boundary_wall_gap(project)

    review_response = await server.review_imported_boundary_coverage(
        project_path=str(project),
        import_id="import_001",
    )
    repair_response = await server.repair_imported_boundary_coverage(
        project_path=str(project),
        import_id="import_001",
    )
    review = json.loads(review_response.text)
    repair = json.loads(repair_response.text)

    assert review["recommended_repair_count"] == 1
    assert review["gaps"][0]["classification"] == "candidate_missing_wall"
    assert repair["status"] == "repaired"
    assert repair["added_walls"][0].startswith("import_001_boundary_gap_")


@pytest.mark.asyncio
async def test_boundary_coverage_tool_does_not_auto_repair_source_evidence_short_gap(tmp_path):
    from mcp_server import server

    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    await server.import_floorplan_to_model(
        project_path=str(project),
        source_path=str(source),
        import_id="import_001",
        width=6000,
        depth=4000,
    )
    create_source_evidence_short_boundary_gap(project)

    review_response = await server.review_imported_boundary_coverage(
        project_path=str(project),
        import_id="import_001",
    )
    repair_response = await server.repair_imported_boundary_coverage(
        project_path=str(project),
        import_id="import_001",
    )
    review = json.loads(review_response.text)
    repair = json.loads(repair_response.text)

    assert review["recommended_repair_count"] == 0
    assert review["gaps"][0]["classification"] == "candidate_opening_or_intentional_gap"
    assert review["gaps"][0]["source_evidence_repair"]["repair_recommended"] is False
    assert repair["status"] == "unchanged"
    assert repair["added_walls"] == []


@pytest.mark.asyncio
async def test_shell_overreach_tools_review_and_repair_phantom_space(tmp_path):
    from mcp_server import server

    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    await server.import_floorplan_to_model(
        project_path=str(project),
        source_path=str(source),
        import_id="import_001",
        width=6000,
        depth=4000,
    )
    create_shell_overreach(project)

    review_response = await server.review_imported_wall_space_consistency(
        project_path=str(project),
        import_id="import_001",
    )
    repair_response = await server.repair_imported_shell_overreach(
        project_path=str(project),
        import_id="import_001",
    )
    review = json.loads(review_response.text)
    repair = json.loads(repair_response.text)

    assert review["status"] == "overreach_found"
    assert review["recommended_repair_count"] == 2
    assert repair["status"] == "repaired"
    assert repair["remaining_overreach_count"] == 0
    assert "import_001_wall_south" in repair["trimmed_walls"]
    assert "import_001_wall_east" in repair["removed_walls"]
    assert repair["added_walls"][0].startswith("import_001_boundary_gap_")


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
    constraints_path = project / "imports" / "import_001" / "constraints.json"
    constraints_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "import_id": "import_001",
                "opening_constraints": [
                    {
                        "id": "import_001_door_001",
                        "host_wall": "import_001_wall_south",
                        "host_wall_axis": "horizontal",
                        "interval": [2550, 3450],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    source_constraint_code = main(
        ["validate-import-constraints", str(project), "import_001", "--strict"]
    )
    source_constraint_output = json.loads(capsys.readouterr().out)
    create_offset_right_boundary(project)
    normalize_code = main(
        [
            "normalize-import-alignment",
            str(project),
            "import_001",
            "--tolerance",
            "160",
        ]
    )
    normalize_output = json.loads(capsys.readouterr().out)
    corner_notch_code = main(
        [
            "repair-import-corner-notch",
            str(project),
            "import_001",
            "--corner",
            "top_left",
            "--horizontal-offset",
            "500",
            "--vertical-offset",
            "600",
            "--target-space-id",
            "import_001_space_001",
        ]
    )
    corner_notch_output = json.loads(capsys.readouterr().out)
    create_missing_boundary_wall_gap(project)
    boundary_review_code = main(
        [
            "review-import-boundary-coverage",
            str(project),
            "import_001",
        ]
    )
    boundary_review_output = json.loads(capsys.readouterr().out)
    boundary_repair_code = main(
        [
            "repair-import-boundary-coverage",
            str(project),
            "import_001",
        ]
    )
    boundary_repair_output = json.loads(capsys.readouterr().out)
    create_shell_overreach(project)
    wall_space_review_code = main(
        [
            "review-import-wall-space",
            str(project),
            "import_001",
        ]
    )
    wall_space_review_output = json.loads(capsys.readouterr().out)
    shell_overreach_code = main(
        [
            "repair-import-shell-overreach",
            str(project),
            "import_001",
        ]
    )
    shell_overreach_output = json.loads(capsys.readouterr().out)
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
    assert source_constraint_code == 0
    assert normalize_code == 0
    assert corner_notch_code == 0
    assert boundary_review_code == 0
    assert boundary_repair_code == 0
    assert wall_space_review_code == 0
    assert shell_overreach_code == 0
    assert summary_code == 0
    assert list_code == 0
    assert rescale_code == 0
    assert import_output["status"] == "imported"
    assert source_constraint_output["status"] == "passed"
    assert normalize_output["status"] == "normalized"
    assert corner_notch_output["status"] == "repaired"
    assert boundary_review_output["recommended_repair_count"] == 1
    assert boundary_repair_output["status"] == "repaired"
    assert wall_space_review_output["recommended_repair_count"] == 2
    assert shell_overreach_output["status"] == "repaired"
    assert summary_output["count"] == 1
    assert list_output["imports"][0]["import_id"] == "import_001"
    assert rescale_output["scale_x"] == 1.5
