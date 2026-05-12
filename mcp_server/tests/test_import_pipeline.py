"""Tests for autonomous-first floor-plan import into project truth."""

import json

import pytest

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
    validate_import_source_constraints,
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


def make_blocked_passage_interpretation(tmp_path):
    """Create a fixture where one continuous wall incorrectly blocks a hallway."""
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "living_candidate",
                "space_id": "living_001",
                "type": "living_room",
                "name": "Living Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [4000, 0, 0], [4000, 3000, 0], [0, 3000, 0]],
            },
            {
                "id": "storage_candidate",
                "space_id": "storage_001",
                "type": "storage",
                "name": "Storage",
                "confidence": 0.7,
                "footprint": [
                    [0, 3000, 0],
                    [1200, 3000, 0],
                    [1200, 4200, 0],
                    [0, 4200, 0],
                ],
            },
            {
                "id": "passage_candidate",
                "space_id": "passage_001",
                "type": "hallway",
                "name": "Passage",
                "confidence": 0.7,
                "footprint": [
                    [1200, 3000, 0],
                    [2500, 3000, 0],
                    [2500, 4200, 0],
                    [1200, 4200, 0],
                ],
            },
        ],
        "walls": [
            {
                "wall_id": "w_service_south",
                "path": [[0, 3000, 0], [2500, 3000, 0]],
                "space_refs": ["living_001", "storage_001", "passage_001"],
                "confidence": 0.6,
            },
            {
                "wall_id": "w_storage_passage",
                "path": [[1200, 3000, 0], [1200, 4200, 0]],
                "space_refs": ["storage_001", "passage_001"],
                "confidence": 0.6,
            },
        ],
        "openings": [],
    }
    path = tmp_path / "blocked_passage_interpretation.json"
    path.write_text(json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def make_open_passage_boundary_gap_interpretation(tmp_path):
    """Create a fixture where a living room and hallway intentionally share an open edge."""
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "living_candidate",
                "space_id": "living_001",
                "type": "living_room",
                "name": "Living Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [4000, 0, 0], [4000, 3000, 0], [0, 3000, 0]],
            },
            {
                "id": "storage_candidate",
                "space_id": "storage_001",
                "type": "storage",
                "name": "Storage",
                "confidence": 0.7,
                "footprint": [
                    [0, 3000, 0],
                    [1200, 3000, 0],
                    [1200, 4200, 0],
                    [0, 4200, 0],
                ],
            },
            {
                "id": "passage_candidate",
                "space_id": "passage_001",
                "type": "hallway",
                "name": "Passage",
                "confidence": 0.7,
                "footprint": [
                    [1200, 3000, 0],
                    [2500, 3000, 0],
                    [2500, 4200, 0],
                    [1200, 4200, 0],
                ],
            },
        ],
        "walls": [
            {
                "wall_id": "w_storage_south",
                "path": [[0, 3000, 0], [1200, 3000, 0]],
                "space_refs": ["living_001", "storage_001"],
                "confidence": 0.68,
            },
            {
                "wall_id": "w_living_north_right",
                "path": [[2500, 3000, 0], [4000, 3000, 0]],
                "space_refs": ["living_001"],
                "confidence": 0.68,
            },
            {
                "wall_id": "w_storage_passage",
                "path": [[1200, 3000, 0], [1200, 4200, 0]],
                "space_refs": ["storage_001", "passage_001"],
                "confidence": 0.68,
            },
            {
                "wall_id": "w_passage_east",
                "path": [[2500, 3000, 0], [2500, 4200, 0]],
                "space_refs": ["passage_001"],
                "confidence": 0.68,
            },
            {
                "wall_id": "w_passage_north",
                "path": [[1200, 4200, 0], [2500, 4200, 0]],
                "space_refs": ["passage_001"],
                "confidence": 0.68,
            },
        ],
        "openings": [],
    }
    path = tmp_path / "open_passage_boundary_gap_interpretation.json"
    path.write_text(json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def make_wrong_bedroom_door_host_interpretation(tmp_path):
    """Create a fixture where a bedroom door is attached to the wrong wall."""
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "living_candidate",
                "space_id": "living_001",
                "type": "living_room",
                "name": "Living Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [6500, 0, 0], [6500, 3000, 0], [0, 3000, 0]],
            },
            {
                "id": "passage_candidate",
                "space_id": "passage_001",
                "type": "hallway",
                "name": "Passage",
                "confidence": 0.7,
                "footprint": [
                    [1200, 3000, 0],
                    [2500, 3000, 0],
                    [2500, 4200, 0],
                    [1200, 4200, 0],
                ],
            },
            {
                "id": "bedroom_candidate",
                "space_id": "bedroom_001",
                "type": "bedroom",
                "name": "Bedroom",
                "confidence": 0.8,
                "footprint": [
                    [2500, 3000, 0],
                    [6500, 3000, 0],
                    [6500, 6000, 0],
                    [2500, 6000, 0],
                ],
            },
        ],
        "walls": [
            {
                "wall_id": "w_bedroom_west",
                "path": [[2500, 3000, 0], [2500, 6000, 0]],
                "space_refs": ["bedroom_001", "passage_001"],
                "confidence": 0.68,
            },
            {
                "wall_id": "w_bedroom_south",
                "path": [[2500, 3000, 0], [6500, 3000, 0]],
                "space_refs": ["bedroom_001", "living_001"],
                "confidence": 0.68,
            },
        ],
        "openings": [
            {
                "id": "bedroom_door_001",
                "type": "door",
                "host_wall": "w_bedroom_south",
                "offset": 120,
                "width": 900,
                "height": 2100,
                "sill_height": 0,
                "swing_direction": "left",
            }
        ],
    }
    path = tmp_path / "wrong_bedroom_door_host_interpretation.json"
    path.write_text(json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def make_entry_door_boundary_interpretation(tmp_path):
    """Create a fixture where an entry door is already on an exterior wall."""
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "living_candidate",
                "space_id": "living_001",
                "type": "living_room",
                "name": "Living Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [4000, 0, 0], [4000, 3000, 0], [0, 3000, 0]],
            },
            {
                "id": "kitchen_candidate",
                "space_id": "kitchen_001",
                "type": "kitchen",
                "name": "Kitchen",
                "confidence": 0.7,
                "footprint": [[1000, 3000, 0], [3000, 3000, 0], [3000, 4500, 0], [1000, 4500, 0]],
            },
        ],
        "walls": [
            {
                "wall_id": "w_ext_living_west",
                "path": [[0, 0, 0], [0, 3000, 0]],
                "space_refs": ["living_001"],
                "confidence": 0.7,
            },
            {
                "wall_id": "w_living_kitchen",
                "path": [[1000, 3000, 0], [3000, 3000, 0]],
                "space_refs": ["living_001", "kitchen_001"],
                "confidence": 0.7,
            },
        ],
        "openings": [
            {
                "id": "entry_door_001",
                "type": "door",
                "host_wall": "w_ext_living_west",
                "offset": 900,
                "width": 900,
                "height": 2100,
                "sill_height": 0,
                "open_to_space": "living_001",
            }
        ],
    }
    path = tmp_path / "entry_door_boundary_interpretation.json"
    path.write_text(json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def make_balcony_access_wrong_exterior_host_interpretation(tmp_path):
    """Create a fixture where balcony access is incorrectly placed on exterior wall."""
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "kitchen_candidate",
                "space_id": "kitchen_001",
                "type": "kitchen",
                "name": "Kitchen",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [3000, 0, 0], [3000, 2400, 0], [0, 2400, 0]],
            },
            {
                "id": "balcony_candidate",
                "space_id": "balcony_001",
                "type": "balcony",
                "name": "Balcony",
                "confidence": 0.72,
                "footprint": [
                    [3000, 0, 0],
                    [4300, 0, 0],
                    [4300, 2400, 0],
                    [3000, 2400, 0],
                ],
            },
        ],
        "walls": [
            {
                "wall_id": "w_kitchen_balcony",
                "path": [[3000, 0, 0], [3000, 2400, 0]],
                "space_refs": ["kitchen_001", "balcony_001"],
                "confidence": 0.72,
            },
            {
                "wall_id": "w_balcony_exterior",
                "path": [[4300, 0, 0], [4300, 2400, 0]],
                "space_refs": ["balcony_001"],
                "confidence": 0.72,
            },
        ],
        "openings": [
            {
                "id": "balcony_access_001",
                "type": "door",
                "host_wall": "w_balcony_exterior",
                "offset": 999,
                "width": 100,
                "source_interval": [650, 1410],
                "height": 2100,
                "sill_height": 0,
                "open_to_space": "balcony_001",
                "access_from_space": "kitchen_001",
            }
        ],
    }
    path = tmp_path / "balcony_access_wrong_exterior_host_interpretation.json"
    path.write_text(json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def make_overlapping_hosted_openings_interpretation(tmp_path):
    """Create a fixture where two source openings overlap on one host wall."""
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [3000, 0, 0], [3000, 2500, 0], [0, 2500, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_room_east",
                "path": [[3000, 0, 0], [3000, 2500, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.7,
            }
        ],
        "openings": [
            {
                "id": "room_glazing_001",
                "type": "window",
                "host_wall": "w_room_east",
                "offset": 200,
                "width": 1300,
                "height": 1200,
                "sill_height": 800,
                "confidence": 0.68,
            },
            {
                "id": "room_door_001",
                "type": "door",
                "host_wall": "w_room_east",
                "offset": 600,
                "width": 700,
                "height": 2100,
                "sill_height": 0,
                "confidence": 0.62,
            },
        ],
    }
    path = tmp_path / "overlapping_hosted_openings_interpretation.json"
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


def test_interpreted_image_import_requires_real_source_file(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    surrogate_source = tmp_path / "uploaded_floorplan_source_note.txt"
    surrogate_source.write_text(
        "The user attached a floor-plan image in chat.",
        encoding="utf-8",
    )
    interpretation_path = tmp_path / "source_interpretation.json"
    interpretation_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "scale": {"units": "mm", "source": "vision", "confidence": 0.6},
                "source": {"provenance": {"origin": "vision_extracted"}},
                "space_candidates": [
                    {
                        "id": "room_candidate",
                        "space_id": "room_001",
                        "type": "other",
                        "confidence": 0.7,
                        "footprint": [
                            [0, 0, 0],
                            [1000, 0, 0],
                            [1000, 1000, 0],
                            [0, 1000, 0],
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="recognized source type"):
        import_floorplan_to_model(
            project,
            source_path=surrogate_source,
            import_id="import_001",
            source_interpretation_path=interpretation_path,
        )


def test_interpreted_image_import_normalizes_y_down_coordinates(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, name="floorplan.png")
    interpretation_path = tmp_path / "source_interpretation.json"
    interpretation_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "scale": {
                    "units": "mm",
                    "source": "visible_dimensions",
                    "confidence": 0.72,
                    "width": 2000,
                    "depth": 3000,
                    "coordinate_system": (
                        "x east, y south, origin at north-west source corner"
                    ),
                },
                "source": {"provenance": {"origin": "vision_extracted"}},
                "negative_regions": [
                    {
                        "id": "outside_blank",
                        "kind": "outside_plan",
                        "footprint": [
                            [0, 2000, 0],
                            [500, 2000, 0],
                            [500, 2500, 0],
                            [0, 2500, 0],
                        ],
                    }
                ],
                "boundary_closure_constraints": [
                    {
                        "id": "room_top_boundary_closure",
                        "path": [[0, 0, 0], [2000, 0, 0]],
                        "space_refs": ["room_001"],
                    }
                ],
                "space_candidates": [
                    {
                        "id": "room_candidate",
                        "space_id": "room_001",
                        "type": "bedroom",
                        "name": "Room",
                        "confidence": 0.76,
                        "label_anchor": [1000, 500, 0],
                        "footprint": [
                            [0, 0, 0],
                            [2000, 0, 0],
                            [2000, 1000, 0],
                            [0, 1000, 0],
                        ],
                    }
                ],
                "walls": [
                    {
                        "wall_id": "w_room_top",
                        "path": [[0, 0, 0], [2000, 0, 0]],
                        "space_refs": ["room_001"],
                    },
                    {
                        "wall_id": "w_room_right",
                        "path": [[2000, 0, 0], [2000, 1000, 0]],
                        "space_refs": ["room_001"],
                    }
                ],
                "openings": [
                    {
                        "id": "window_001",
                        "type": "window",
                        "host_wall": "w_room_top",
                        "source_interval": [500, 1300],
                        "source_anchor": [900, 0, 0],
                        "height": 1200,
                        "sill_height": 900,
                    },
                    {
                        "id": "window_right",
                        "type": "window",
                        "host_wall": "w_room_right",
                        "source_interval": [250, 750],
                        "source_anchor": [2000, 500, 0],
                        "height": 1200,
                        "sill_height": 900,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )

    design_model = json.loads((project / "design_model.json").read_text())
    assert result["summary"]["coordinate_transform"]["type"] == (
        "image_y_down_to_model_y_up"
    )
    assert "source_y_down_coordinates_transformed" in result["quality_flags"]
    assert (
        "source_constraints_derived_from_interpretation"
        in result["quality_flags"]
    )
    assert design_model["spaces"]["room_001"]["footprint"] == [
        [0.0, 3000.0, 0.0],
        [2000.0, 3000.0, 0.0],
        [2000.0, 2000.0, 0.0],
        [0.0, 2000.0, 0.0],
    ]
    assert design_model["walls"]["w_room_top"]["path"] == [
        [0.0, 3000.0, 0.0],
        [2000.0, 3000.0, 0.0],
    ]
    assert design_model["walls"]["w_room_right"]["path"] == [
        [2000.0, 3000.0, 0.0],
        [2000.0, 2000.0, 0.0],
    ]
    assert design_model["openings"]["window_001"]["source"]["opening_evidence"][
        "source_anchor"
    ] == [900.0, 3000.0, 0.0]
    assert design_model["openings"]["window_right"]["offset"] == 250.0
    assert design_model["openings"]["window_right"]["width"] == 500.0
    assert design_model["openings"]["window_right"]["source"]["opening_evidence"][
        "source_interval"
    ] == [2250.0, 2750.0]
    assert design_model["openings"]["window_right"]["source"]["opening_evidence"][
        "source_interval_coordinate_system"
    ] == "model_y_up"
    constraints_path = (
        project
        / design_model["import_sessions"]["import_001"]["source_constraints_path"]
    )
    constraints = json.loads(constraints_path.read_text(encoding="utf-8"))
    dynamic_skill = (
        project
        / ".agents"
        / "skills"
        / "import-source-import-001"
        / "SKILL.md"
    )
    dynamic_skill_text = dynamic_skill.read_text(encoding="utf-8")
    assert dynamic_skill.exists()
    assert result["dynamic_runtime_skill"]["skill_name"] == "import-source-import-001"
    assert "source_file_backed: true" in dynamic_skill_text
    assert "source_interpretation_path: imports/import_001/extracted/source_interpretation.json" in dynamic_skill_text
    assert "source_constraints_path: imports/import_001/constraints.json" in dynamic_skill_text
    assert (project / ".claude" / "skills" / "import-source-import-001" / "SKILL.md").exists()
    assert constraints["derived_from_source_interpretation"] is True
    assert constraints["negative_region_constraints"][0]["footprint"] == [
        [0.0, 1000.0, 0.0],
        [500.0, 1000.0, 0.0],
        [500.0, 500.0, 0.0],
        [0.0, 500.0, 0.0],
    ]
    assert constraints["boundary_closure_constraints"][0]["path"] == [
        [0.0, 3000.0, 0.0],
        [2000.0, 3000.0, 0.0],
    ]
    assert constraints["boundary_closure_constraints"][0]["provenance"] == {
        "origin": "vision_extracted"
    }
    assert constraints["opening_constraints"][0]["source_anchor"] == [
        900.0,
        3000.0,
        0.0,
    ]
    assert constraints["opening_constraints"][1]["source_interval"] == [
        2250.0,
        2750.0,
    ]
    assert constraints["opening_constraints"][1]["source_interval_mode"] == (
        "wall_coordinate"
    )


def test_chat_attachment_source_reference_import_creates_draft_dynamic_skill(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    interpretation_path = tmp_path / "chat_source_interpretation.json"
    interpretation_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "scale": {
                    "units": "mm",
                    "source": "vision_attachment",
                    "confidence": 0.52,
                    "width": 2400,
                    "depth": 1800,
                },
                "source": {"provenance": {"origin": "vision_extracted"}},
                "space_candidates": [
                    {
                        "id": "room_candidate",
                        "space_id": "room_001",
                        "type": "other",
                        "confidence": 0.62,
                        "footprint": [
                            [0, 0, 0],
                            [2400, 0, 0],
                            [2400, 1800, 0],
                            [0, 1800, 0],
                        ],
                    }
                ],
                "walls": [
                    {
                        "wall_id": "w_room_south",
                        "path": [[0, 0, 0], [2400, 0, 0]],
                        "space_refs": ["room_001"],
                        "confidence": 0.58,
                    }
                ],
                "openings": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_reference="chat attachment Image #1",
        import_id="chat_floorplan_001",
        source_interpretation_path=interpretation_path,
    )

    manifest = json.loads(
        (
            project
            / "imports"
            / "chat_floorplan_001"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    dynamic_skill = (
        project
        / ".agents"
        / "skills"
        / "import-source-chat-floorplan-001"
        / "SKILL.md"
    )
    dynamic_skill_text = dynamic_skill.read_text(encoding="utf-8")

    assert result["source_file_backed"] is False
    assert result["dynamic_runtime_skill"]["skill_name"] == (
        "import-source-chat-floorplan-001"
    )
    assert manifest["source"]["source_type"] == "chat_image_attachment"
    assert manifest["source"]["file_backed"] is False
    assert manifest["source"]["original_path"] == "chat attachment Image #1"
    assert (
        project / "imports" / "chat_floorplan_001" / "evidence" / "source_reference.md"
    ).exists()
    assert "chat_attachment_no_local_source_file" in result["quality_flags"]
    assert "source_file_backed_import_pending" in result["quality_flags"]
    assert dynamic_skill.exists()
    assert "source_file_backed: false" in dynamic_skill_text
    assert "stored_source_record: imports/chat_floorplan_001/evidence/source_reference.md" in dynamic_skill_text
    assert (
        "source_interpretation_path: imports/chat_floorplan_001/extracted/source_interpretation.json"
        in dynamic_skill_text
    )
    assert (
        design_model["import_sessions"]["chat_floorplan_001"]["dynamic_runtime_skill"][
            "paths"
        ][0]
        == ".agents/skills/import-source-chat-floorplan-001/SKILL.md"
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
    manifest = json.loads(
        (project / "imports" / "import_001" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert errors == []
    assert result["autonomous_first"] is True
    assert result["summary"]["wall_count"] == 4
    assert result["summary"]["opening_count"] == 2
    assert result["timing"]["trace_type"] == "import_floorplan"
    assert result["timing"]["budget"]["total_within_budget"] is True
    assert manifest["timing"]["total_ms"] == result["timing"]["total_ms"]
    assert "project_state_read" in {
        phase["name"] for phase in result["timing"]["phases"]
    }
    assert "source_preprocessing_or_extraction" in {
        phase["name"] for phase in result["timing"]["phases"]
    }
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


def test_interpreted_import_infers_doorless_circulation_opening(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_blocked_passage_interpretation(tmp_path)

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
    plan = build_project_execution_plan(project)

    opening = design_model["openings"]["w_service_south_circulation_opening_01"]
    service_operation = next(
        operation
        for operation in plan["bridge_operations"]
        if operation["payload"].get("wall_id") == "w_service_south"
    )

    assert (
        "source_circulation_openings_inferred_during_generation"
        in result["quality_flags"]
    )
    assert extracted["circulation_openings"]["status"] == "inferred"
    assert opening["type"] == "opening"
    assert opening["host_wall"] == "w_service_south"
    assert opening["offset"] == 1200.0
    assert opening["width"] == 1300.0
    assert opening["height"] == 2800.0
    assert opening["layer"] == "Other"
    assert service_operation["operation_type"] == "create_wall_with_openings"
    assert service_operation["payload"]["openings"][0]["type"] == "opening"


def test_interpreted_import_repairs_private_room_door_host_wall(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_wrong_bedroom_door_host_interpretation(tmp_path)
    stale_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    stale_model["execution"] = {
        "bridge_operations": {
            "wall_w_bedroom_south_with_openings": {
                "operation_type": "create_wall_with_openings",
                "entity_ids": ["old-wall-entity"],
                "opening_results": [
                    {
                        "opening_id": "bedroom_door_001",
                        "entity_ids": ["old-door-entity"],
                        "status": "success",
                    }
                ],
                "status": "success",
            }
        }
    }
    (project / "design_model.json").write_text(
        json.dumps(stale_model, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

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
    plan = build_project_execution_plan(project)

    door = design_model["openings"]["bedroom_door_001"]
    west_wall_operation = next(
        operation
        for operation in plan["bridge_operations"]
        if operation["payload"].get("wall_id") == "w_bedroom_west"
    )

    assert "source_door_host_repaired_during_generation" in result["quality_flags"]
    assert extracted["door_host_repair"]["status"] == "repaired"
    assert door["host_wall"] == "w_bedroom_west"
    assert door["offset"] == 120.0
    assert door["open_to_space"] == "bedroom_001"
    assert door["open_side"] == "opposite"
    assert door["source"]["repairs"][0]["from_host_wall"] == "w_bedroom_south"
    assert west_wall_operation["operation_type"] == "create_wall_with_openings"
    assert west_wall_operation["payload"]["openings"][0]["open_side"] == "opposite"
    assert west_wall_operation["payload"]["openings"][0]["open_to_space"] == "bedroom_001"
    assert design_model["execution"]["bridge_operations"] == {}
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"
    assert design_model["metadata"]["execution_sync"]["details"][
        "stale_execution_feedback"
    ]["removed_bridge_operations"] == ["wall_w_bedroom_south_with_openings"]


def test_interpreted_import_keeps_entry_door_on_exterior_boundary(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_entry_door_boundary_interpretation(tmp_path)

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
    plan = build_project_execution_plan(project)

    door = design_model["openings"]["entry_door_001"]
    west_wall_operation = next(
        operation
        for operation in plan["bridge_operations"]
        if operation["payload"].get("wall_id") == "w_ext_living_west"
    )

    assert "source_door_host_repaired_during_generation" not in result["quality_flags"]
    assert extracted["door_host_repair"]["status"] == "unchanged"
    assert door["host_wall"] == "w_ext_living_west"
    assert door["offset"] == 900.0
    assert door["open_to_space"] == "living_001"
    assert west_wall_operation["operation_type"] == "create_wall_with_openings"


def test_interpreted_import_prefers_shared_boundary_for_balcony_access(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_balcony_access_wrong_exterior_host_interpretation(tmp_path)

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
    plan = build_project_execution_plan(project)

    door = design_model["openings"]["balcony_access_001"]
    shared_wall_operation = next(
        operation
        for operation in plan["bridge_operations"]
        if operation["payload"].get("wall_id") == "w_kitchen_balcony"
    )

    assert "source_door_host_repaired_during_generation" in result["quality_flags"]
    assert extracted["door_host_repair"]["status"] == "repaired"
    assert door["host_wall"] == "w_kitchen_balcony"
    assert door["offset"] == 650.0
    assert door["width"] == 760.0
    assert door["access_from_space"] == "kitchen_001"
    assert door["open_to_space"] == "balcony_001"
    assert door["source"]["repairs"][0]["from_host_wall"] == "w_balcony_exterior"
    assert shared_wall_operation["operation_type"] == "create_wall_with_openings"
    assert shared_wall_operation["payload"]["openings"][0]["open_to_space"] == "balcony_001"


def test_validate_import_source_constraints_passes_opening_and_wall_constraints(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_balcony_access_wrong_exterior_host_interpretation(tmp_path)

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation,
    )
    constraints_path = project / "imports" / "import_001" / "constraints.json"
    constraints_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "import_id": "import_001",
                "opening_constraints": [
                    {
                        "id": "balcony_access_001",
                        "type": "door",
                        "host_wall": "w_kitchen_balcony",
                        "open_to_space": "balcony_001",
                        "access_from_space": "kitchen_001",
                        "interval": [650, 1410],
                        "interval_tolerance": 1,
                    }
                ],
                "wall_constraints": [
                    {
                        "id": "w_kitchen_balcony",
                        "path": [[3000, 0, 0], [3000, 2400, 0]],
                        "path_tolerance": 1,
                        "space_refs": ["kitchen_001", "balcony_001"],
                    }
                ],
                "negative_region_constraints": [
                    {
                        "id": "outside_right",
                        "bounds": {
                            "min": [4400, 0, 0],
                            "max": [5200, 2400, 0],
                        },
                        "max_wall_overlap_length": 0,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = validate_import_source_constraints(project, "import_001")
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (project / "imports" / "import_001" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert result["status"] == "passed"
    assert result["checked_count"] == 3
    assert result["failure_count"] == 0
    assert design_model["import_sessions"]["import_001"]["source_fidelity"]["status"] == "passed"
    assert manifest["source_fidelity"]["status"] == "passed"


def test_validate_import_source_constraints_reports_opening_mismatch(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_balcony_access_wrong_exterior_host_interpretation(tmp_path)

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation,
    )
    constraints_path = project / "imports" / "import_001" / "constraints.json"
    constraints_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "import_id": "import_001",
                "opening_constraints": [
                    {
                        "id": "balcony_access_001",
                        "host_wall": "w_balcony_exterior",
                        "interval": [0, 500],
                        "interval_tolerance": 1,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = validate_import_source_constraints(project, "import_001")
    codes = {failure["code"] for failure in result["failures"]}

    assert result["status"] == "failed"
    assert "opening_host_wall_mismatch" in codes
    assert "opening_interval_mismatch" in codes


def test_validate_import_source_constraints_checks_opening_anchor_and_host_refs(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_balcony_access_wrong_exterior_host_interpretation(tmp_path)

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation,
    )
    constraints_path = project / "imports" / "import_001" / "constraints.json"
    constraints_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "import_id": "import_001",
                "opening_constraints": [
                    {
                        "id": "balcony_access_001",
                        "host_wall": "w_kitchen_balcony",
                        "open_to_space": "balcony_001",
                        "access_from_space": "kitchen_001",
                        "require_host_space_refs": True,
                        "source_anchor": {"point": [3000, 1030, 0], "mode": "center"},
                        "anchor_tolerance": 1,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = validate_import_source_constraints(project, "import_001")

    assert result["status"] == "passed"
    assert result["checked_count"] == 1


def test_validate_import_source_constraints_reports_opening_host_axis_mismatch(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "host-axis-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "bedroom",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [3000, 0, 0], [3000, 2400, 0], [0, 2400, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_room_south",
                "path": [[0, 0, 0], [3000, 0, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.72,
            }
        ],
        "openings": [
            {
                "id": "door_001",
                "type": "door",
                "host_wall": "w_room_south",
                "source_interval": [400, 1200],
                "height": 2100,
                "sill_height": 0,
                "open_to_space": "room_001",
            }
        ],
        "constraints": {
            "opening_constraints": [
                {
                    "id": "door_001",
                    "source_wall_orientation": "vertical",
                }
            ]
        },
    }
    interpretation_path = tmp_path / "host_axis_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "opening_host_axis_mismatch" in codes


def test_validate_import_source_constraints_reports_edge_alignment_mismatch(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "stacked-edge-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "upper_candidate",
                "space_id": "upper_001",
                "type": "balcony",
                "name": "Upper",
                "confidence": 0.76,
                "footprint": [[0, 1200, 0], [1200, 1200, 0], [1200, 2400, 0], [0, 2400, 0]],
            },
            {
                "id": "lower_candidate",
                "space_id": "lower_001",
                "type": "balcony",
                "name": "Lower",
                "confidence": 0.76,
                "footprint": [[160, 0, 0], [1360, 0, 0], [1360, 1200, 0], [160, 1200, 0]],
            },
        ],
        "walls": [],
        "openings": [],
        "constraints": {
            "alignment_constraints": [
                {
                    "id": "stacked_left_edges",
                    "space_ids": ["upper_001", "lower_001"],
                    "axis": "x",
                    "edge": "min",
                    "alignment_tolerance": 20,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "edge_alignment_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "edge_alignment_mismatch" in codes


def test_validate_import_source_constraints_reports_exterior_outline_gap(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "outline-gap-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [3000, 0, 0], [3000, 2400, 0], [0, 2400, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_room_south",
                "path": [[0, 0, 0], [3000, 0, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.72,
            }
        ],
        "openings": [],
        "constraints": {
            "exterior_outline_constraints": [
                {
                    "id": "source_exterior_outline",
                    "segments": [
                        {"path": [[0, 0, 0], [3000, 0, 0]]},
                        {"path": [[3000, 0, 0], [3000, 2400, 0]]},
                    ],
                    "path_tolerance": 1,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "outline_gap_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "exterior_outline_segment_missing" in codes


def test_validate_import_source_constraints_accepts_split_outline_coverage(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "split-outline-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [2000, 0, 0], [2000, 1200, 0], [0, 1200, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_south_left",
                "path": [[0, 0, 0], [1000, 0, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.72,
            },
            {
                "wall_id": "w_south_right",
                "path": [[1000, 0, 0], [2000, 0, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.72,
            },
        ],
        "openings": [],
        "constraints": {
            "exterior_outline_constraints": [
                {
                    "id": "source_split_outline",
                    "path": [[0, 0, 0], [2000, 0, 0]],
                    "path_tolerance": 1,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "split_outline_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )

    assert result["source_fidelity"]["status"] == "passed"


def test_interpreted_import_preserves_source_constrained_shell_segment(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "constrained-shell-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "bathroom",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [1000, 0, 0], [1000, 1000, 0], [0, 1000, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_source_notch_riser",
                "path": [[-200, 1000, 0], [-200, 1320, 0]],
                "confidence": 0.72,
            }
        ],
        "openings": [],
        "constraints": {
            "wall_constraints": [
                {
                    "id": "w_source_notch_riser",
                    "path": [[-200, 1000, 0], [-200, 1320, 0]],
                    "path_tolerance": 1,
                }
            ],
            "exterior_outline_constraints": [
                {
                    "id": "source_notch_outline",
                    "path": [[-200, 1000, 0], [-200, 1320, 0]],
                    "path_tolerance": 1,
                }
            ],
        },
    }
    interpretation_path = tmp_path / "constrained_shell_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
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

    assert "w_source_notch_riser" in design_model["walls"]
    assert result["source_fidelity"]["status"] == "passed"
    assert extracted["shell_trim"]["status"] == "unchanged"
    assert [
        segment["wall_id"]
        for segment in extracted["shell_trim"]["preserved_source_constrained_segments"]
    ] == ["w_source_notch_riser"]


def test_interpreted_import_uses_footprint_overlap_for_negative_notch(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "negative-notch-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "negative_regions": [
            {
                "id": "top_left_notch",
                "kind": "outside_plan_notch",
                "footprint": [[0, 1000, 0], [200, 1000, 0], [200, 1300, 0], [0, 1300, 0]],
            }
        ],
        "space_candidates": [
            {
                "id": "notched_room_candidate",
                "space_id": "notched_room_001",
                "type": "bathroom",
                "confidence": 0.76,
                "footprint": [
                    [0, 0, 0],
                    [1000, 0, 0],
                    [1000, 1300, 0],
                    [200, 1300, 0],
                    [200, 1000, 0],
                    [0, 1000, 0],
                ],
            }
        ],
        "walls": [],
        "openings": [],
        "constraints": {
            "negative_region_constraints": [
                {
                    "id": "top_left_notch",
                    "bounds": {"min": [0, 1000, 0], "max": [200, 1300, 0]},
                    "max_space_overlap_m2": 0.001,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "negative_notch_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )

    assert result["source_fidelity"]["status"] == "passed"
    assert result["summary"]["accepted_candidate_count"] == 1
    assert result["summary"]["rejected_candidate_count"] == 0


def test_interpreted_import_removes_redundant_wall_fully_covered_by_segments(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "redundant-wall-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [2000, 0, 0], [2000, 1200, 0], [0, 1200, 0]],
            }
        ],
        "walls": [
            {"wall_id": "w_broad", "path": [[0, 0, 0], [2000, 0, 0]], "confidence": 0.62},
            {"wall_id": "w_left", "path": [[0, 0, 0], [900, 0, 0]], "confidence": 0.7},
            {"wall_id": "w_right", "path": [[900, 0, 0], [2000, 0, 0]], "confidence": 0.7},
        ],
        "openings": [],
    }
    interpretation_path = tmp_path / "redundant_wall_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
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

    assert "source_redundant_walls_removed_during_generation" in result["quality_flags"]
    assert "w_broad" not in design_model["walls"]
    assert {"w_left", "w_right"}.issubset(design_model["walls"])
    assert extracted["redundant_walls"]["removed_walls"] == [
        {"wall_id": "w_broad", "covered_by": ["w_left", "w_right"]}
    ]


def test_interpreted_import_rejects_candidate_when_label_anchor_is_outside(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "label-anchor-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
                {
                    "id": "wrong_strip",
                    "space_id": "balcony_001",
                    "type": "balcony",
                    "label_area_m2": 1.44,
                "label_anchor": [500, 600, 0],
                "confidence": 0.9,
                "footprint": [[1200, 0, 0], [2400, 0, 0], [2400, 1200, 0], [1200, 1200, 0]],
            },
                {
                    "id": "label_containing_strip",
                    "space_id": "balcony_001",
                    "type": "balcony",
                    "label_area_m2": 1.44,
                "label_anchor": [500, 600, 0],
                "confidence": 0.7,
                "footprint": [[0, 0, 0], [1200, 0, 0], [1200, 1200, 0], [0, 1200, 0]],
            },
        ],
        "walls": [],
        "openings": [],
        "constraints": {
            "space_constraints": [
                {
                    "id": "balcony_001",
                    "label_anchor": [500, 600, 0],
                }
            ]
        },
    }
    interpretation_path = tmp_path / "label_anchor_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
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

    assert result["source_fidelity"]["status"] == "passed"
    assert design_model["spaces"]["balcony_001"]["source"]["candidate_id"] == "label_containing_strip"
    rejected = [
        review
        for review in extracted["candidate_reviews"]
        if review["candidate_id"] == "wrong_strip"
    ][0]
    assert rejected["status"] == "rejected"
    assert {issue["code"] for issue in rejected["issues"]} == {
        "label_anchor_outside_footprint",
    }


def test_validate_import_source_constraints_reports_space_label_anchor_outside(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "label-anchor-mismatch-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [1000, 0, 0], [1000, 1000, 0], [0, 1000, 0]],
            }
        ],
        "walls": [],
        "openings": [],
        "constraints": {
            "space_constraints": [
                {
                    "id": "room_001",
                    "label_anchor": [1500, 500, 0],
                }
            ]
        },
    }
    interpretation_path = tmp_path / "label_anchor_mismatch_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "space_label_anchor_outside_footprint" in codes


def test_validate_import_source_constraints_reports_negative_region_space_overlap(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "negative-space-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [2000, 0, 0], [2000, 2000, 0], [0, 2000, 0]],
            }
        ],
        "walls": [],
        "openings": [],
        "constraints": {
            "negative_region_constraints": [
                {
                    "id": "source_outside_region",
                    "bounds": {"min": [1000, 0, 0], "max": [3000, 2000, 0]},
                    "forbid_spaces": True,
                    "coordinate_tolerance": 1,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "negative_space_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "negative_region_space_overlap" in codes


def test_validate_import_source_constraints_reports_boundary_opening_type_missing(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "boundary-window-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "bedroom",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [3000, 0, 0], [3000, 2400, 0], [0, 2400, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_room_east",
                "path": [[3000, 0, 0], [3000, 2400, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.72,
            }
        ],
        "openings": [],
        "constraints": {
            "boundary_closure_constraints": [
                {
                    "id": "room_east_window_run",
                    "path": [[3000, 400, 0], [3000, 1800, 0]],
                    "required_opening_type": "window",
                    "path_tolerance": 1,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "boundary_window_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "boundary_opening_type_missing" in codes


def test_validate_import_source_constraints_reports_boundary_closure_missing(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "boundary-gap-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "balcony_candidate",
                "space_id": "balcony_001",
                "type": "balcony",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [2000, 0, 0], [2000, 1200, 0], [0, 1200, 0]],
            }
        ],
        "walls": [],
        "openings": [],
        "constraints": {
            "boundary_closure_constraints": [
                {
                    "id": "balcony_source_bottom_edge",
                    "path": [[0, 0, 0], [2000, 0, 0]],
                    "path_tolerance": 1,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "boundary_gap_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "boundary_closure_missing" in codes


def test_validate_import_source_constraints_reports_space_topology_mismatch(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "gap-between-spaces.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "kitchen_candidate",
                "space_id": "kitchen_001",
                "type": "kitchen",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [3000, 0, 0], [3000, 2400, 0], [0, 2400, 0]],
            },
            {
                "id": "balcony_candidate",
                "space_id": "balcony_001",
                "type": "balcony",
                "confidence": 0.72,
                "footprint": [[4300, 0, 0], [5600, 0, 0], [5600, 2400, 0], [4300, 2400, 0]],
            },
        ],
        "walls": [
            {
                "wall_id": "w_kitchen_east",
                "path": [[3000, 0, 0], [3000, 2400, 0]],
                "space_refs": ["kitchen_001"],
                "confidence": 0.72,
            },
            {
                "wall_id": "w_balcony_west",
                "path": [[4300, 0, 0], [4300, 2400, 0]],
                "space_refs": ["balcony_001"],
                "confidence": 0.72,
            },
        ],
        "openings": [
            {
                "id": "balcony_access_001",
                "type": "door",
                "host_wall": "w_balcony_west",
                "source_interval": [650, 1410],
                "height": 2100,
                "sill_height": 0,
                "open_to_space": "balcony_001",
                "access_from_space": "kitchen_001",
            }
        ],
        "constraints": {
            "opening_constraints": [
                {
                    "id": "balcony_access_001",
                    "open_to_space": "balcony_001",
                    "access_from_space": "kitchen_001",
                    "require_host_space_refs": True,
                }
            ],
            "space_constraints": [
                {
                    "id": "balcony_001",
                    "bounds": {"min": [3000, 0, 0], "max": [4300, 2400, 0]},
                    "bounds_tolerance": 1,
                }
            ],
            "adjacency_constraints": [
                {
                    "id": "kitchen_balcony_source_access",
                    "space_ids": ["kitchen_001", "balcony_001"],
                    "require_shared_wall": True,
                    "require_opening": True,
                    "opening_id": "balcony_access_001",
                }
            ],
        },
    }
    interpretation_path = tmp_path / "gap_between_spaces_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "opening_host_space_refs_mismatch" in codes
    assert "space_bounds_mismatch" in codes
    assert "adjacency_shared_wall_missing" in codes


def test_interpreted_import_persists_and_checks_embedded_source_constraints(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = json.loads(
        make_balcony_access_wrong_exterior_host_interpretation(tmp_path).read_text(
            encoding="utf-8"
        )
    )
    interpretation["constraints"] = {
        "opening_constraints": [
            {
                "id": "balcony_access_001",
                "host_wall": "w_kitchen_balcony",
                "access_from_space": "kitchen_001",
                "open_to_space": "balcony_001",
                "source_interval": [650, 1410],
                "interval_tolerance": 1,
            }
        ]
    }
    interpretation_path = tmp_path / "interpretation_with_constraints.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    constraints_path = project / "imports" / "import_001" / "constraints.json"
    extracted = json.loads(
        (
            project
            / "imports"
            / "import_001"
            / "extracted"
            / "interpretation.json"
        ).read_text(encoding="utf-8")
    )

    assert constraints_path.exists()
    assert result["source_fidelity"]["status"] == "passed"
    assert extracted["source_constraints_path"] == "imports/import_001/constraints.json"


def test_interpreted_opening_source_interval_does_not_require_width(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "interval-only-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [3000, 0, 0], [3000, 2400, 0], [0, 2400, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_room_south",
                "path": [[0, 0, 0], [3000, 0, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.72,
            }
        ],
        "openings": [
            {
                "id": "door_001",
                "type": "door",
                "host_wall": "w_room_south",
                "source_interval": [400, 1200],
                "height": 2100,
                "sill_height": 0,
                "open_to_space": "room_001",
            }
        ],
    }
    interpretation_path = tmp_path / "interval_only_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    design_model, errors = load_design_model(str(project / "design_model.json"))

    assert errors == []
    opening = design_model["openings"]["door_001"]
    assert opening["offset"] == 400
    assert opening["width"] == 800


def test_source_constraints_allow_negative_region_boundary_walls(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "negative-boundary-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[1000, 0, 0], [2200, 0, 0], [2200, 1000, 0], [1000, 1000, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_room_west",
                "path": [[1000, 0, 0], [1000, 1000, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.72,
            }
        ],
        "openings": [],
        "constraints": {
            "negative_region_constraints": [
                {
                    "id": "outside_left",
                    "bounds": {"min": [0, 0, 0], "max": [1000, 1000, 0]},
                    "max_wall_overlap_length": 0,
                    "forbid_boundary_enclosure": True,
                    "coordinate_tolerance": 1,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "negative_boundary_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )

    assert result["source_fidelity"]["status"] == "passed"


def test_validate_import_source_constraints_reports_negative_region_boundary_enclosure(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "negative-boundary-enclosure-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "living_room",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [1000, 0, 0], [1000, 1000, 0], [0, 1000, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_shared_east",
                "path": [[1000, 0, 0], [1000, 1000, 0]],
                "space_refs": ["room_001"],
                "confidence": 0.72,
            },
            {
                "wall_id": "w_negative_bottom",
                "path": [[1000, 0, 0], [2000, 0, 0]],
                "space_refs": [],
                "confidence": 0.62,
            },
            {
                "wall_id": "w_negative_east",
                "path": [[2000, 0, 0], [2000, 1000, 0]],
                "space_refs": [],
                "confidence": 0.62,
            },
            {
                "wall_id": "w_negative_top",
                "path": [[1000, 1000, 0], [2000, 1000, 0]],
                "space_refs": [],
                "confidence": 0.62,
            },
        ],
        "openings": [],
        "constraints": {
            "wall_constraints": [
                {"id": "w_shared_east", "path": [[1000, 0, 0], [1000, 1000, 0]]},
                {"id": "w_negative_bottom", "path": [[1000, 0, 0], [2000, 0, 0]]},
                {"id": "w_negative_east", "path": [[2000, 0, 0], [2000, 1000, 0]]},
                {"id": "w_negative_top", "path": [[1000, 1000, 0], [2000, 1000, 0]]},
            ],
            "negative_region_constraints": [
                {
                    "id": "outside_right",
                    "bounds": {"min": [1000, 0, 0], "max": [2000, 1000, 0]},
                    "forbid_spaces": True,
                    "forbid_boundary_enclosure": True,
                    "coordinate_tolerance": 1,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "negative_boundary_enclosure_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    codes = {failure["code"] for failure in result["source_fidelity"]["failures"]}

    assert result["source_fidelity"]["status"] == "failed"
    assert "negative_region_boundary_enclosure" in codes


def test_positive_boundary_adjacent_to_negative_region_can_close_without_enclosing(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "positive-boundary-near-outside-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "balcony_candidate",
                "space_id": "balcony_001",
                "type": "balcony",
                "name": "Balcony",
                "confidence": 0.76,
                "footprint": [[0, 1000, 0], [1000, 1000, 0], [1000, 2000, 0], [0, 2000, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_balcony_outside_boundary",
                "path": [[0, 1000, 0], [1000, 1000, 0]],
                "space_refs": ["balcony_001"],
                "confidence": 0.72,
            }
        ],
        "openings": [
            {
                "id": "balcony_boundary_window",
                "type": "window",
                "host_wall": "w_balcony_outside_boundary",
                "source_interval": [100, 900],
                "height": 2200,
                "sill_height": 0,
                "open_to_space": "balcony_001",
            }
        ],
        "constraints": {
            "boundary_closure_constraints": [
                {
                    "id": "balcony_external_edge",
                    "path": [[0, 1000, 0], [1000, 1000, 0]],
                    "space_refs": ["balcony_001"],
                    "required_opening_type": "window",
                    "path_tolerance": 1,
                }
            ],
            "negative_region_constraints": [
                {
                    "id": "outside_below_balcony",
                    "bounds": {"min": [0, 0, 0], "max": [1000, 1000, 0]},
                    "forbid_spaces": True,
                    "forbid_boundary_enclosure": True,
                    "coordinate_tolerance": 1,
                }
            ],
        },
    }
    interpretation_path = tmp_path / "positive_boundary_near_negative_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )

    assert result["source_fidelity"]["status"] == "passed"


def test_source_fidelity_can_require_extracted_constraint_evidence(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "manual-constraint-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "other",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [2000, 0, 0], [2000, 2000, 0], [0, 2000, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_room_south",
                "path": [[0, 0, 0], [2000, 0, 0]],
                "space_refs": ["room_001"],
            }
        ],
        "constraints": {
            "wall_constraints": [
                {
                    "id": "w_room_south",
                    "path": [[0, 0, 0], [2000, 0, 0]],
                    "path_tolerance": 1,
                }
            ]
        },
    }
    interpretation_path = tmp_path / "manual_constraint_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    result = validate_import_source_constraints(
        project,
        "import_001",
        require_extracted_evidence=True,
        update_state=False,
    )
    codes = {failure["code"] for failure in result["failures"]}

    assert result["status"] == "failed"
    assert "constraint_evidence_not_extracted" in codes
    assert result["evidence_origin"]["origin_counts"] == {"missing": 1}


def test_source_fidelity_accepts_extracted_constraint_evidence(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "extracted-constraint-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "other",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [2000, 0, 0], [2000, 2000, 0], [0, 2000, 0]],
            }
        ],
        "walls": [
            {
                "wall_id": "w_room_south",
                "path": [[0, 0, 0], [2000, 0, 0]],
                "space_refs": ["room_001"],
            }
        ],
        "constraints": {
            "provenance": {"origin": "vision_extracted"},
            "wall_constraints": [
                {
                    "id": "w_room_south",
                    "path": [[0, 0, 0], [2000, 0, 0]],
                    "path_tolerance": 1,
                }
            ],
        },
    }
    interpretation_path = tmp_path / "extracted_constraint_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    result = validate_import_source_constraints(
        project,
        "import_001",
        require_extracted_evidence=True,
        update_state=False,
    )

    assert result["status"] == "passed"
    assert result["evidence_origin"]["origin_counts"] == {"vision_extracted": 1}


def test_source_fidelity_requires_strong_extracted_door_evidence(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "weak-door-evidence-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "bedroom",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [2400, 0, 0], [2400, 2000, 0], [0, 2000, 0]],
            },
            {
                "id": "hall_candidate",
                "space_id": "hallway_001",
                "type": "hallway",
                "name": "Hallway",
                "confidence": 0.76,
                "footprint": [[0, -900, 0], [2400, -900, 0], [2400, 0, 0], [0, 0, 0]],
            },
        ],
        "walls": [
            {
                "wall_id": "w_room_south",
                "path": [[0, 0, 0], [2400, 0, 0]],
                "space_refs": ["room_001", "hallway_001"],
            }
        ],
        "openings": [
            {
                "id": "room_door_001",
                "type": "door",
                "host_wall": "w_room_south",
                "source_interval": [600, 1400],
                "height": 2100,
                "sill_height": 0,
                "open_to_space": "room_001",
                "access_from_space": "hallway_001",
            }
        ],
        "constraints": {
            "provenance": {"origin": "vision_extracted"},
            "opening_constraints": [
                {
                    "id": "room_door_001",
                    "type": "door",
                    "host_wall": "w_room_south",
                    "open_to_space": "room_001",
                    "interval": [600, 1400],
                }
            ],
        },
    }
    interpretation_path = tmp_path / "weak_door_evidence_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    result = validate_import_source_constraints(
        project,
        "import_001",
        require_extracted_evidence=True,
        update_state=False,
    )
    codes = {failure["code"] for failure in result["failures"]}

    assert result["status"] == "failed"
    assert "opening_source_host_axis_missing" in codes
    assert "opening_source_access_space_missing" in codes
    assert "opening_host_space_refs_not_required" in codes


def test_source_fidelity_accepts_strong_extracted_door_evidence(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "strong-door-evidence-plan.png")
    interpretation = {
        "version": "1.0",
        "scale": {"units": "mm", "source": "visible_dimensions", "confidence": 0.72},
        "space_candidates": [
            {
                "id": "room_candidate",
                "space_id": "room_001",
                "type": "bedroom",
                "name": "Room",
                "confidence": 0.76,
                "footprint": [[0, 0, 0], [2400, 0, 0], [2400, 2000, 0], [0, 2000, 0]],
            },
            {
                "id": "hall_candidate",
                "space_id": "hallway_001",
                "type": "hallway",
                "name": "Hallway",
                "confidence": 0.76,
                "footprint": [[0, -900, 0], [2400, -900, 0], [2400, 0, 0], [0, 0, 0]],
            },
        ],
        "walls": [
            {
                "wall_id": "w_room_south",
                "path": [[0, 0, 0], [2400, 0, 0]],
                "space_refs": ["room_001", "hallway_001"],
            }
        ],
        "openings": [
            {
                "id": "room_door_001",
                "type": "door",
                "host_wall": "w_room_south",
                "source_interval": [600, 1400],
                "height": 2100,
                "sill_height": 0,
                "open_to_space": "room_001",
                "access_from_space": "hallway_001",
            }
        ],
        "constraints": {
            "provenance": {"origin": "vision_extracted"},
            "opening_constraints": [
                {
                    "id": "room_door_001",
                    "type": "door",
                    "host_wall": "w_room_south",
                    "host_wall_axis": "horizontal",
                    "open_to_space": "room_001",
                    "access_from_space": "hallway_001",
                    "require_host_space_refs": True,
                    "interval": [600, 1400],
                    "interval_tolerance": 1,
                }
            ],
        },
    }
    interpretation_path = tmp_path / "strong_door_evidence_interpretation.json"
    interpretation_path.write_text(
        json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation_path,
    )
    result = validate_import_source_constraints(
        project,
        "import_001",
        require_extracted_evidence=True,
        update_state=False,
    )

    assert result["status"] == "passed"
    assert result["evidence_origin"]["origin_counts"] == {"vision_extracted": 1}


def test_interpreted_import_normalizes_overlapping_hosted_openings(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_overlapping_hosted_openings_interpretation(tmp_path)

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
    plan = build_project_execution_plan(project)

    door = design_model["openings"]["room_door_001"]
    window = design_model["openings"]["room_glazing_001"]
    wall_operation = next(
        operation
        for operation in plan["bridge_operations"]
        if operation["payload"].get("wall_id") == "w_room_east"
    )
    intervals = [
        (opening["offset"], opening["offset"] + opening["width"])
        for opening in wall_operation["payload"]["openings"]
    ]

    assert "source_opening_conflicts_normalized_during_generation" in (
        result["quality_flags"]
    )
    assert extracted["opening_conflicts"]["status"] == "normalized"
    assert extracted["opening_conflicts"]["adjusted_openings"][0]["opening_id"] == (
        "room_glazing_001"
    )
    assert door["offset"] == 600.0
    assert door["width"] == 700.0
    assert window["offset"] == 200.0
    assert window["width"] == 400.0
    assert wall_operation["operation_type"] == "create_wall_with_openings"
    assert intervals == [(200.0, 600.0), (600.0, 1300.0)]


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
    assert summary["imports"][0]["timing"]["slowest_phase"]["name"]
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


def test_boundary_coverage_does_not_auto_fill_source_evidence_short_gap(tmp_path):
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
    create_source_evidence_short_boundary_gap(project)

    review = review_imported_boundary_coverage(project, "import_001")
    repair = repair_imported_boundary_coverage(
        project,
        "import_001",
        notes="Do not auto-fill a short gap without source evidence.",
    )
    design_model = json.loads((project / "design_model.json").read_text(encoding="utf-8"))
    short_gap = next(
        gap
        for gap in review["gaps"]
        if gap["interval"] == [3400.0, 3900.0]
    )

    assert review["recommended_repair_count"] == 0
    assert repair["status"] == "unchanged"
    assert repair["added_walls"] == []
    assert short_gap["interval"] == [3400.0, 3900.0]
    assert short_gap["classification"] == "candidate_opening_or_intentional_gap"
    assert short_gap["source_evidence_repair"]["repair_recommended"] is False
    assert "space adjacency alone is insufficient" in (
        short_gap["source_evidence_repair"]["reasons"][0]
    )
    assert "source_backed_boundary_wall_added" not in (
        design_model["import_sessions"]["import_001"]["quality_flags"]
    )


def test_boundary_coverage_keeps_living_hallway_circulation_gap_open(tmp_path):
    project = tmp_path / "project"
    init_project(project, template="empty")
    source = make_source(tmp_path, "plan.png")
    interpretation = make_open_passage_boundary_gap_interpretation(tmp_path)

    import_floorplan_to_model(
        project,
        source_path=source,
        import_id="import_001",
        source_interpretation_path=interpretation,
    )

    review = review_imported_boundary_coverage(project, "import_001")
    repair = repair_imported_boundary_coverage(
        project,
        "import_001",
        notes="Keep doorless circulation edges open.",
    )
    circulation_gap = next(
        gap
        for gap in review["gaps"]
        if gap["interval"] == [1200.0, 2500.0]
    )

    assert review["status"] == "gaps_found"
    assert review["recommended_repair_count"] == 0
    assert circulation_gap["classification"] == (
        "candidate_circulation_opening_or_intentional_gap"
    )
    assert circulation_gap["circulation_gap"] is True
    assert circulation_gap["repair_recommended"] is False
    assert {
        space["type"]
        for space in circulation_gap["adjacent_spaces"]
    } == {"living_room", "hallway"}
    assert repair["status"] == "unchanged"
    assert repair["added_walls"] == []


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
