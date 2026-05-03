"""Tests for autonomous-first floor-plan import into project truth."""

import json

from mcp_server.project_init import init_project
from mcp_server.project_state import read_project_state
from mcp_server.resources.design_model_schema import load_design_model
from mcp_server.smoke import validate_project
from mcp_server.tools.import_pipeline import (
    get_import_summary,
    import_floorplan_to_model,
    register_import_source,
    repair_imported_region,
    rescale_imported_model,
    review_model_against_import_source,
)
from mcp_server.tools.project_executor import build_project_execution_plan


def make_source(tmp_path, name="floorplan.pdf"):
    """Create a small source file fixture."""
    source = tmp_path / name
    source.write_bytes(b"%PDF-1.4\n% floorplan fixture\n")
    return source


def test_register_import_source_creates_manifest_and_source_copy(tmp_path):
    init_project(tmp_path / "project", template="empty")
    source = make_source(tmp_path)

    result = register_import_source(
        tmp_path / "project",
        source,
        import_id="import_001",
        label="Existing plan",
    )

    manifest_path = tmp_path / "project" / "imports" / "import_001" / "manifest.json"
    copied_source = tmp_path / "project" / "imports" / "import_001" / "source" / source.name
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["status"] == "registered"
    assert copied_source.exists()
    assert manifest["source"]["source_type"] == "pdf"
    assert manifest["source"]["stored_path"] == "imports/import_001/source/floorplan.pdf"


def test_import_floorplan_to_model_writes_working_truth_and_trace(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        width=7200,
        depth=5100,
    )
    design_model, errors = load_design_model(str(project / "design_model.json"))
    plan = build_project_execution_plan(project)
    validation = validate_project(project)

    assert errors == []
    assert result["autonomous_first"] is True
    assert result["summary"]["wall_count"] == 4
    assert result["summary"]["opening_count"] == 2
    assert design_model["import_sessions"]["import_001"]["status"] == "imported"
    assert design_model["spaces"]["import_001_space_001"]["footprint"][2] == [
        7200.0,
        5100.0,
        0,
    ]
    assert sorted(design_model["walls"]) == [
        "import_001_wall_east",
        "import_001_wall_north",
        "import_001_wall_south",
        "import_001_wall_west",
    ]
    assert sorted(design_model["openings"]) == [
        "import_001_door_001",
        "import_001_window_001",
    ]
    assert plan["skipped_count"] == 0
    assert plan["operation_count"] == 7
    assert [op["operation_type"] for op in plan["bridge_operations"]].count(
        "create_wall"
    ) == 4
    assert [op["operation_type"] for op in plan["bridge_operations"]].count(
        "create_box"
    ) == 2
    assert validation["ok"] is True


def test_import_floorplan_requires_explicit_overwrite_for_existing_session(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
    )

    try:
        import_floorplan_to_model(
            project,
            source_path=source,
            import_id="import_001",
        )
    except FileExistsError as error:
        assert "Use overwrite=True" in str(error)
    else:
        raise AssertionError("Expected existing import session to require overwrite.")

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        overwrite=True,
    )

    assert result["status"] == "imported"


def test_validate_project_reports_invalid_imported_opening(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        width=3000,
        depth=2400,
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    design_model["openings"]["import_001_door_001"]["offset"] = 2900
    (project / "design_model.json").write_text(
        json.dumps(design_model, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    validation = validate_project(project)
    opening_check = next(
        check
        for check in validation["checks"]
        if check["name"] == "project_layout"
    )

    assert validation["ok"] is False
    assert "opening exceeds host wall length" in opening_check["errors"][0]


def test_import_floorplan_without_dimensions_sets_quality_flags(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "photo.png")

    import_floorplan_to_model(project, source_path=source, import_id="import_001")
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    session = design_model["import_sessions"]["import_001"]

    assert session["scale"]["source"] == "estimated"
    assert "scale_estimated" in session["quality_flags"]
    assert any(flag["code"] == "scale_estimated" for flag in design_model["quality_flags"])


def test_get_import_summary_reads_manifest_and_model_session(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    import_floorplan_to_model(project, source_path=source, import_id="import_001")

    summary = get_import_summary(project, import_id="import_001")

    assert summary["count"] == 1
    assert summary["imports"][0]["import_id"] == "import_001"
    assert summary["model_import_sessions"]["import_001"]["status"] == "imported"


def test_rescale_imported_model_updates_geometry_and_records_history(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        width=6000,
        depth=4000,
    )

    result = rescale_imported_model(project, "import_001", target_width=9000)
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))

    assert result["scale_x"] == 1.5
    assert result["scale_y"] == 1.5
    assert design_model["spaces"]["import_001_space_001"]["bounds"]["max"] == [
        9000.0,
        6000.0,
        2800.0,
    ]
    assert design_model["import_sessions"]["import_001"]["scale"]["source"] == (
        "target_dimensions"
    )
    assert design_model["import_sessions"]["import_001"]["scale"]["history"]


def test_review_and_repair_imported_region_update_source_backed_truth(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    import_floorplan_to_model(project, source_path=source, import_id="import_001")

    review = review_model_against_import_source(
        project,
        "import_001",
        target_id="import_001_wall_south",
    )
    repair = repair_imported_region(
        project,
        "import_001",
        wall_thickness=180,
        notes="Wall thickness corrected from source review.",
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))

    assert "import_001_wall_south" in review["matched_model_entities"]["walls"]
    assert repair["status"] == "repaired"
    assert design_model["walls"]["import_001_wall_south"]["thickness"] == 180.0
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"


def test_project_state_includes_import_summary(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path)
    import_floorplan_to_model(project, source_path=source, import_id="import_001")

    state = read_project_state(project)

    assert state["imports"]["count"] == 1
    assert state["imports"]["sessions"][0]["status"] == "imported"
