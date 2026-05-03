"""Tests for autonomous-first floor-plan import into project truth."""

import json

from mcp_server.project_init import init_project
from mcp_server.project_state import read_project_state
from mcp_server.resources.design_model_schema import load_design_model
from mcp_server.smoke import validate_project
from mcp_server.tools.import_pipeline import (
    get_import_summary,
    import_floorplan_to_model,
    normalize_imported_wall_alignment,
    register_import_source,
    repair_imported_boundary_coverage,
    repair_imported_corner_notch,
    repair_imported_shell_overreach,
    repair_imported_region,
    rescale_imported_model,
    review_imported_boundary_coverage,
    review_imported_wall_space_consistency,
    review_model_against_import_source,
)
from mcp_server.tools.project_executor import build_project_execution_plan


def make_source(tmp_path, name="floorplan.pdf"):
    """Create a small source file fixture."""
    source = tmp_path / name
    source.write_bytes(b"%PDF-1.4\n% floorplan fixture\n")
    return source


def make_area_guard_interpretation(tmp_path):
    """Create an interpretation fixture with one rejected overwide balcony candidate."""
    interpretation = {
        "version": "1.0",
        "scale": {
            "units": "mm",
            "source": "visible_dimension_annotations",
            "confidence": 0.74,
            "width": 7095,
            "depth": 7880,
        },
        "dimension_chains": [
            {
                "id": "bottom_width_chain",
                "axis": "x",
                "segments": [
                    {"id": "outside_left", "length": 1335},
                    {"id": "kitchen", "length": 3130},
                    {"id": "balcony_b", "length": 1315},
                    {"id": "outside_right", "length": 1180},
                ],
            }
        ],
        "negative_regions": [
            {
                "id": "lower_right_outside_plan",
                "kind": "outside_plan",
                "footprint": [
                    [5780, 1785, 0],
                    [7095, 1785, 0],
                    [7095, 0, 0],
                    [5780, 0, 0],
                ],
            }
        ],
        "space_candidates": [
            {
                "id": "balcony_b_overwide_candidate",
                "space_id": "balcony_b_001",
                "type": "balcony",
                "name": "Balcony B",
                "label_area_m2": 2.3,
                "confidence": 0.91,
                "dimension_constraints": [
                    {"axis": "x", "length": 1315, "tolerance": 80, "source": "bottom_width_chain"}
                ],
                "footprint": [
                    [4465, 1785, 0],
                    [7095, 1785, 0],
                    [7095, 0, 0],
                    [4465, 0, 0],
                ],
            },
            {
                "id": "balcony_b_area_matched_candidate",
                "space_id": "balcony_b_001",
                "type": "balcony",
                "name": "Balcony B",
                "label_area_m2": 2.3,
                "confidence": 0.78,
                "dimension_constraints": [
                    {"axis": "x", "length": 1315, "tolerance": 80, "source": "bottom_width_chain"}
                ],
                "footprint": [
                    [4465, 1785, 0],
                    [5780, 1785, 0],
                    [5780, 0, 0],
                    [4465, 0, 0],
                ],
            },
            {
                "id": "kitchen_candidate",
                "space_id": "kitchen_001",
                "type": "kitchen",
                "name": "Kitchen",
                "label_area_m2": 5.6,
                "confidence": 0.82,
                "footprint": [
                    [1335, 1785, 0],
                    [4465, 1785, 0],
                    [4465, 0, 0],
                    [1335, 0, 0],
                ],
            },
        ],
        "walls": [
            {
                "wall_id": "w_ext_bottom",
                "path": [[1335, 0, 0], [7095, 0, 0]],
                "confidence": 0.66,
            },
            {
                "wall_id": "w_balcony_b_west",
                "path": [[4465, 0, 0], [4465, 1785, 0]],
                "confidence": 0.7,
            },
            {
                "wall_id": "w_balcony_b_east",
                "path": [[5780, 0, 0], [5780, 1785, 0]],
                "confidence": 0.7,
            },
        ],
        "openings": [],
    }
    path = tmp_path / "source_interpretation.json"
    path.write_text(json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def make_ambiguous_balcony_interpretation(tmp_path):
    """Create a fixture where label-area evidence should beat a wrong blank region."""
    interpretation = {
        "version": "1.0",
        "scale": {
            "units": "mm",
            "source": "visible_dimension_annotations",
            "confidence": 0.74,
            "width": 7095,
            "depth": 7880,
        },
        "negative_regions": [
            {
                "id": "ambiguous_lower_middle_blank",
                "kind": "outside_plan_blank",
                "footprint": [
                    [4465, 1785, 0],
                    [5915, 1785, 0],
                    [5915, 0, 0],
                    [4465, 0, 0],
                ],
            }
        ],
        "space_candidates": [
            {
                "id": "balcony_b_right_strip_candidate",
                "space_id": "balcony_b_001",
                "type": "balcony",
                "name": "Balcony B",
                "label_area_m2": 2.3,
                "confidence": 0.9,
                "dimension_constraints": [
                    {"axis": "x", "length": 1180, "tolerance": 80, "source": "bottom_width_chain"},
                    {"axis": "y", "length": 1785, "tolerance": 80, "source": "right_depth_chain"},
                ],
                "footprint": [
                    [5915, 1785, 0],
                    [7095, 1785, 0],
                    [7095, 0, 0],
                    [5915, 0, 0],
                ],
            },
            {
                "id": "balcony_b_area_and_dimension_candidate",
                "space_id": "balcony_b_001",
                "type": "balcony",
                "name": "Balcony B",
                "label_area_m2": 2.3,
                "confidence": 0.72,
                "dimension_constraints": [
                    {"axis": "x", "length": 1315, "tolerance": 80, "source": "area_backsolve"},
                    {"axis": "y", "length": 1785, "tolerance": 80, "source": "right_depth_chain"},
                ],
                "footprint": [
                    [4465, 1785, 0],
                    [5780, 1785, 0],
                    [5780, 0, 0],
                    [4465, 0, 0],
                ],
            },
        ],
        "walls": [
            {
                "wall_id": "w_ext_bottom",
                "path": [[1335, 0, 0], [7095, 0, 0]],
                "confidence": 0.66,
            },
            {
                "wall_id": "w_balcony_b_east",
                "path": [[5780, 0, 0], [5780, 1785, 0]],
                "space_refs": ["balcony_b_001"],
                "confidence": 0.7,
            },
        ],
        "openings": [],
    }
    path = tmp_path / "ambiguous_source_interpretation.json"
    path.write_text(json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def create_offset_right_boundary(project):
    """Create a near-boundary imported wall offset like a mixed dimension chain."""
    design_model_path = project / "design_model.json"
    design_model = json.loads(design_model_path.read_text(encoding="utf-8"))
    walls = design_model["walls"]
    east_wall = walls["import_001_wall_east"]
    east_wall["path"] = [[6000.0, 4000.0, 0], [6000.0, 2200.0, 0]]
    walls["import_001_wall_east_step"] = {
        **east_wall,
        "path": [[6000.0, 2200.0, 0], [5880.0, 2200.0, 0]],
    }
    walls["import_001_wall_east_lower"] = {
        **east_wall,
        "path": [[5880.0, 2200.0, 0], [5880.0, 0.0, 0]],
    }

    space = design_model["spaces"]["import_001_space_001"]
    space["footprint"] = [
        [0, 0, 0],
        [5880.0, 0, 0],
        [5880.0, 2200.0, 0],
        [6000.0, 2200.0, 0],
        [6000.0, 4000.0, 0],
        [0, 4000.0, 0],
    ]

    generated = design_model["import_sessions"]["import_001"]["generated_model"]
    generated["wall_ids"] = [
        wall_id
        for wall_id in generated["wall_ids"]
        if wall_id != "import_001_wall_east"
    ]
    generated["wall_ids"].extend(
        [
            "import_001_wall_east",
            "import_001_wall_east_step",
            "import_001_wall_east_lower",
        ]
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
    walls = design_model["walls"]
    walls["import_001_wall_south"]["path"] = [
        [min_x, min_y, 0.0],
        [overreach_x, min_y, 0.0],
    ]
    walls["import_001_wall_east"]["path"] = [
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


def create_semantic_false_opening_gap(project):
    """Create a short living-balcony boundary gap that should be auto-filled."""
    design_model_path = project / "design_model.json"
    design_model = json.loads(design_model_path.read_text(encoding="utf-8"))
    source = {
        "kind": "import_floorplan",
        "import_id": "import_001",
        "confidence": 0.7,
        "assumptions": ["Semantic false-opening fixture."],
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
    assert plan["operation_count"] == 5
    assert [op["operation_type"] for op in plan["bridge_operations"]].count(
        "create_wall"
    ) == 2
    assert [op["operation_type"] for op in plan["bridge_operations"]].count(
        "create_wall_with_openings"
    ) == 2
    assert [op["operation_type"] for op in plan["bridge_operations"]].count("create_box") == 0
    assert validation["ok"] is True


def test_interpreted_import_rejects_overwide_space_and_trims_shell(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_area_guard_interpretation(tmp_path)

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation,
        wall_thickness=180,
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    extracted = json.loads(
        (
            project
            / "imports"
            / "import_001"
            / "extracted"
            / "interpretation.json"
        ).read_text(encoding="utf-8")
    )
    validation = validate_project(project)

    assert result["source_interpretation_used"] is True
    assert result["summary"]["rejected_candidate_count"] == 1
    assert "source_space_candidate_rejected" in result["quality_flags"]
    assert "source_shell_overreach_trimmed_during_generation" in result["quality_flags"]
    assert design_model["spaces"]["balcony_b_001"]["footprint"] == [
        [4465.0, 1785.0, 0.0],
        [5780.0, 1785.0, 0.0],
        [5780.0, 0.0, 0.0],
        [4465.0, 0.0, 0.0],
    ]
    assert design_model["walls"]["w_ext_bottom"]["path"] == [
        [1335.0, 0.0, 0.0],
        [5780.0, 0.0, 0.0],
    ]
    rejected = [
        review
        for review in extracted["candidate_reviews"]
        if review["candidate_id"] == "balcony_b_overwide_candidate"
    ][0]
    assert rejected["status"] == "rejected"
    assert {issue["code"] for issue in rejected["issues"]} == {
        "room_label_area_mismatch",
        "dimension_constraint_mismatch",
        "negative_space_overlap",
    }
    assert extracted["shell_trim"]["trimmed_walls"] == ["w_ext_bottom"]
    assert validation["ok"] is True


def test_interpreted_import_prefers_label_area_over_ambiguous_blank_region(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_ambiguous_balcony_interpretation(tmp_path)

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation,
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    extracted = json.loads(
        (
            project
            / "imports"
            / "import_001"
            / "extracted"
            / "interpretation.json"
        ).read_text(encoding="utf-8")
    )

    assert result["source_interpretation_used"] is True
    assert "source_negative_region_conflict_overridden" in result["quality_flags"]
    assert design_model["spaces"]["balcony_b_001"]["source"]["candidate_id"] == (
        "balcony_b_area_and_dimension_candidate"
    )
    assert design_model["spaces"]["balcony_b_001"]["footprint"] == [
        [4465.0, 1785.0, 0.0],
        [5780.0, 1785.0, 0.0],
        [5780.0, 0.0, 0.0],
        [4465.0, 0.0, 0.0],
    ]
    reviews = {
        review["candidate_id"]: review
        for review in extracted["candidate_reviews"]
    }
    assert reviews["balcony_b_right_strip_candidate"]["status"] == "accepted"
    assert reviews["balcony_b_area_and_dimension_candidate"]["status"] == "accepted"
    assert (
        reviews["balcony_b_area_and_dimension_candidate"]["selection_score"]
        < reviews["balcony_b_right_strip_candidate"]["selection_score"]
    )
    assert {
        issue["code"]
        for issue in reviews["balcony_b_area_and_dimension_candidate"]["issues"]
    } == {"negative_space_conflict_overridden"}
    assert validate_project(project)["ok"] is True


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


def test_normalize_imported_wall_alignment_snaps_boundary_offsets(tmp_path):
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
    create_offset_right_boundary(project)

    result = normalize_imported_wall_alignment(
        project,
        "import_001",
        tolerance=160,
        coordinate_match_tolerance=1,
        notes="Straightened an exterior right wall offset.",
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (project / "imports" / "import_001" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert result["status"] == "normalized"
    assert result["snap_maps"]["x"]["5880.0"] == 6000.0
    assert "import_001_wall_east_step" in result["removed_walls"]
    assert design_model["walls"]["import_001_wall_east_lower"]["path"] == [
        [6000.0, 2200.0, 0.0],
        [6000.0, 0.0, 0.0],
    ]
    assert "import_001_wall_east_step" not in design_model["walls"]
    assert "import_001_wall_east_step" not in (
        design_model["import_sessions"]["import_001"]["generated_model"]["wall_ids"]
    )
    assert "import_001_wall_east_step" not in (
        design_model["import_sessions"]["import_001"]["generated_model"][
            "changed_model_ids"
        ]
    )
    assert design_model["spaces"]["import_001_space_001"]["footprint"][1] == [
        6000.0,
        0.0,
        0.0,
    ]
    assert "exterior_wall_alignment_normalized" in (
        design_model["import_sessions"]["import_001"]["quality_flags"]
    )
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"
    assert manifest["status"] == "repaired"
    assert manifest["repair_history"][-1]["action"] == "normalize_imported_wall_alignment"


def test_repair_imported_corner_notch_restores_missing_step(tmp_path):
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
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    design_model["openings"]["import_001_door_001"]["host_wall"] = "import_001_wall_west"
    design_model["openings"]["import_001_door_001"]["offset"] = 2500
    (project / "design_model.json").write_text(
        json.dumps(design_model, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = repair_imported_corner_notch(
        project,
        "import_001",
        corner="top_left",
        horizontal_offset=500,
        vertical_offset=600,
        target_space_id="import_001_space_001",
        notes="Restore top-left exterior notch from source review.",
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (project / "imports" / "import_001" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    plan = build_project_execution_plan(project)

    assert result["status"] == "repaired"
    assert result["added_walls"] == [
        "import_001_top_left_notch_vertical",
        "import_001_top_left_notch_horizontal",
    ]
    assert design_model["walls"]["import_001_wall_north"]["path"] == [
        [6000, 4000, 0],
        [500.0, 4000.0, 0.0],
    ]
    assert design_model["walls"]["import_001_wall_west"]["path"] == [
        [0.0, 3400.0, 0.0],
        [0, 0, 0],
    ]
    assert design_model["spaces"]["import_001_space_001"]["footprint"] == [
        [500.0, 4000.0, 0.0],
        [6000.0, 4000.0, 0.0],
        [6000.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
        [0.0, 3400.0, 0.0],
        [500.0, 3400.0, 0.0],
    ]
    assert design_model["openings"]["import_001_door_001"]["offset"] == 1900.0
    assert "exterior_corner_notch_repaired" in (
        design_model["import_sessions"]["import_001"]["quality_flags"]
    )
    assert "import_001_top_left_notch_vertical" in (
        design_model["import_sessions"]["import_001"]["generated_model"]["wall_ids"]
    )
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"
    assert manifest["repair_history"][-1]["action"] == "repair_imported_corner_notch"
    assert plan["skipped_count"] == 0


def test_boundary_coverage_review_and_repair_adds_missing_wall(tmp_path):
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
    create_missing_boundary_wall_gap(project)

    review = review_imported_boundary_coverage(project, "import_001")
    repair = repair_imported_boundary_coverage(
        project,
        "import_001",
        notes="Fill a high-confidence footprint boundary gap.",
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (project / "imports" / "import_001" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    plan = build_project_execution_plan(project)
    added_wall_id = repair["added_walls"][0]

    assert review["status"] == "gaps_found"
    assert review["recommended_repair_count"] == 1
    assert review["gaps"][0]["start_point"] == [0.0, 0.0, 0.0]
    assert review["gaps"][0]["end_point"] == [1500.0, 0.0, 0.0]
    assert repair["status"] == "repaired"
    assert repair["remaining_gap_count"] == 0
    assert added_wall_id.startswith("import_001_boundary_gap_")
    assert design_model["walls"][added_wall_id]["path"] == [
        [0.0, 0.0, 0.0],
        [1500.0, 0.0, 0.0],
    ]
    assert added_wall_id in (
        design_model["import_sessions"]["import_001"]["generated_model"]["wall_ids"]
    )
    assert "import_boundary_coverage_repaired" in (
        design_model["import_sessions"]["import_001"]["quality_flags"]
    )
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"
    assert manifest["repair_history"][-1]["action"] == (
        "repair_imported_boundary_coverage"
    )
    assert plan["skipped_count"] == 0


def test_boundary_coverage_auto_fills_semantic_false_opening(tmp_path):
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
    create_semantic_false_opening_gap(project)

    review = review_imported_boundary_coverage(project, "import_001")
    repair = repair_imported_boundary_coverage(
        project,
        "import_001",
        notes="Auto-fill a semantic false opening on a living-balcony boundary.",
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    added_wall_id = repair["added_walls"][0]
    semantic_gap = next(
        gap
        for gap in review["gaps"]
        if gap["classification"] == "candidate_false_opening_or_missing_wall"
    )

    assert review["recommended_repair_count"] == 1
    assert semantic_gap["interval"] == [3400.0, 3900.0]
    assert semantic_gap["semantic_repair"]["repair_recommended"] is True
    assert semantic_gap["semantic_repair"]["adjacent_space_types"] == [
        "balcony",
        "living_room",
    ]
    assert repair["status"] == "repaired"
    assert repair["repaired_gaps"][0]["classification"] == (
        "candidate_false_opening_or_missing_wall"
    )
    assert design_model["walls"][added_wall_id]["path"] == [
        [3400.0, 0.0, 0.0],
        [3900.0, 0.0, 0.0],
    ]
    assert "import_false_opening_repaired" in (
        design_model["import_sessions"]["import_001"]["quality_flags"]
    )


def test_shell_overreach_review_and_repair_trim_phantom_pocket(tmp_path):
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
    create_shell_overreach(project)

    review = review_imported_wall_space_consistency(project, "import_001")
    repair = repair_imported_shell_overreach(
        project,
        "import_001",
        notes="Trim shell area outside the imported footprint.",
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (project / "imports" / "import_001" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    plan = build_project_execution_plan(project)
    added_wall_id = repair["added_walls"][0]

    assert review["status"] == "overreach_found"
    assert review["recommended_repair_count"] == 2
    assert {
        segment["wall_id"] for segment in review["overreach_segments"]
    } == {"import_001_wall_south", "import_001_wall_east"}
    assert repair["status"] == "repaired"
    assert repair["remaining_overreach_count"] == 0
    assert repair["remaining_boundary_gap_count"] == 0
    assert "import_001_wall_south" in repair["trimmed_walls"]
    assert "import_001_wall_east" in repair["removed_walls"]
    assert added_wall_id.startswith("import_001_boundary_gap_")
    assert design_model["walls"]["import_001_wall_south"]["path"] == [
        [0.0, 0.0, 0.0],
        [6000.0, 0.0, 0.0],
    ]
    assert "import_001_wall_east" not in design_model["walls"]
    assert design_model["walls"][added_wall_id]["path"] == [
        [6000.0, 0.0, 0.0],
        [6000.0, 4000.0, 0.0],
    ]
    assert added_wall_id in (
        design_model["import_sessions"]["import_001"]["generated_model"]["wall_ids"]
    )
    assert "import_001_wall_east" not in (
        design_model["import_sessions"]["import_001"]["generated_model"]["wall_ids"]
    )
    assert "import_shell_overreach_repaired" in (
        design_model["import_sessions"]["import_001"]["quality_flags"]
    )
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"
    assert manifest["repair_history"][-1]["action"] == "repair_imported_shell_overreach"
    assert plan["skipped_count"] == 0


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
