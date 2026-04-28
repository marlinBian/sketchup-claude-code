"""Headless bathroom planning for the first vertical slice."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_server.resources.design_rules_schema import create_default_design_rules
from mcp_server.resources.project_files import (
    DESIGN_MODEL_FILENAME,
    DESIGN_RULES_FILENAME,
)
from mcp_server.tools.placement_tools import (
    component_skp_path,
    load_library,
    resolve_skp_path,
)


def utc_now() -> str:
    """Return a UTC ISO8601 timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_component(component_library: dict[str, Any], component_id: str) -> dict[str, Any]:
    """Return a component manifest entry by ID."""
    for component in component_library.get("components", []):
        if component.get("id") == component_id:
            return component
    raise ValueError(f"Missing required component: {component_id}")


def component_dimensions(component: dict[str, Any]) -> dict[str, float]:
    """Return normalized component dimensions."""
    dimensions = component.get("dimensions")
    if dimensions:
        return {
            "width": float(dimensions["width"]),
            "depth": float(dimensions["depth"]),
            "height": float(dimensions["height"]),
        }

    bounds = component["bounds"]
    return {
        "width": float(bounds["max"][0] - bounds["min"][0]),
        "depth": float(bounds["max"][1] - bounds["min"][1]),
        "height": float(bounds["max"][2] - bounds["min"][2]),
    }


def make_bounds(
    min_x: float,
    min_y: float,
    min_z: float,
    width: float,
    depth: float,
    height: float,
) -> dict[str, list[float]]:
    """Create an axis-aligned bounds object."""
    return {
        "min": [min_x, min_y, min_z],
        "max": [min_x + width, min_y + depth, min_z + height],
    }


def check_minimum(
    name: str,
    actual: float,
    required: float,
    source: str,
) -> dict[str, Any]:
    """Return a validation check result."""
    return {
        "name": name,
        "valid": actual >= required,
        "actual": actual,
        "required": required,
        "units": "mm",
        "source": source,
    }


def build_bathroom_components(
    width: float,
    depth: float,
    ceiling_height: float,
    rules: dict[str, Any],
    component_library: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build deterministic component instances for the seed bathroom."""
    bathroom_rules = rules["rule_sets"]["bathroom"]
    mount_center_height = bathroom_rules["clearances"]["mirror_mount_center_height"]

    door_manifest = get_component(component_library, "bathroom_door_700")
    toilet_manifest = get_component(component_library, "toilet_floor_mounted_basic")
    vanity_manifest = get_component(component_library, "vanity_wall_600")
    mirror_manifest = get_component(component_library, "mirror_wall_500")

    door = component_dimensions(door_manifest)
    toilet = component_dimensions(toilet_manifest)
    vanity = component_dimensions(vanity_manifest)
    mirror = component_dimensions(mirror_manifest)

    door_y = (depth - door["width"]) / 2
    toilet_x = (width - toilet["width"]) / 2
    toilet_y = depth - toilet["depth"]
    vanity_x = width - vanity["width"]
    vanity_y = 0
    mirror_x = width - mirror["width"] - 50
    mirror_y = 0
    mirror_z = mount_center_height - mirror["height"] / 2

    return {
        "door_001": {
            "type": "door",
            "name": door_manifest["name"],
            "component_ref": door_manifest["id"],
            "position": [0, door_y, 0],
            "dimensions": door,
            "bounds": make_bounds(0, door_y, 0, 40, door["width"], door["height"]),
            "anchors": {
                "hinge": [0, door_y, 0],
                "bottom": [20, door_y + door["width"] / 2, 0],
            },
            "clearance": copy.deepcopy(door_manifest["clearance"]),
            "rotation": 90,
            "layer": "Doors",
        },
        "toilet_001": {
            "type": "toilet",
            "name": toilet_manifest["name"],
            "component_ref": toilet_manifest["id"],
            "position": [width / 2, toilet_y, 0],
            "dimensions": toilet,
            "bounds": make_bounds(
                toilet_x,
                toilet_y,
                0,
                toilet["width"],
                toilet["depth"],
                toilet["height"],
            ),
            "anchors": {
                "back": [width / 2, depth, 0],
                "bottom": [width / 2, toilet_y + toilet["depth"] / 2, 0],
            },
            "clearance": copy.deepcopy(toilet_manifest["clearance"]),
            "rotation": 180,
            "layer": "Fixtures",
        },
        "vanity_001": {
            "type": "vanity",
            "name": vanity_manifest["name"],
            "component_ref": vanity_manifest["id"],
            "position": [vanity_x + vanity["width"] / 2, vanity_y, 0],
            "dimensions": vanity,
            "bounds": make_bounds(
                vanity_x,
                vanity_y,
                0,
                vanity["width"],
                vanity["depth"],
                vanity["height"],
            ),
            "anchors": {
                "back": [vanity_x + vanity["width"] / 2, 0, 0],
                "bottom": [
                    vanity_x + vanity["width"] / 2,
                    vanity_y + vanity["depth"] / 2,
                    0,
                ],
            },
            "clearance": copy.deepcopy(vanity_manifest["clearance"]),
            "rotation": 0,
            "layer": "Fixtures",
        },
        "mirror_001": {
            "type": "mirror",
            "name": mirror_manifest["name"],
            "component_ref": mirror_manifest["id"],
            "position": [mirror_x + mirror["width"] / 2, mirror_y, mount_center_height],
            "dimensions": mirror,
            "bounds": make_bounds(
                mirror_x,
                mirror_y,
                mirror_z,
                mirror["width"],
                mirror["depth"],
                mirror["height"],
            ),
            "anchors": {
                "back": [mirror_x + mirror["width"] / 2, 0, mount_center_height],
                "center": [
                    mirror_x + mirror["width"] / 2,
                    mirror_y + mirror["depth"] / 2,
                    mount_center_height,
                ],
            },
            "clearance": copy.deepcopy(mirror_manifest["clearance"]),
            "rotation": 0,
            "layer": "Fixtures",
        },
    }


def validate_bathroom_layout(
    width: float,
    depth: float,
    components: dict[str, dict[str, Any]],
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Validate deterministic bathroom clearances."""
    bathroom_rules = rules["rule_sets"]["bathroom"]
    clearances = bathroom_rules["clearances"]
    checks = [
        check_minimum(
            "room_width",
            width,
            1800,
            "built_in_bathroom_minimum",
        ),
        check_minimum(
            "room_depth",
            depth,
            1600,
            "built_in_bathroom_minimum",
        ),
    ]

    toilet_bounds = components["toilet_001"]["bounds"]
    vanity_bounds = components["vanity_001"]["bounds"]
    door_bounds = components["door_001"]["bounds"]

    checks.extend(
        [
            check_minimum(
                "toilet_front_clearance",
                toilet_bounds["min"][1],
                clearances["toilet_front_clearance"],
                "design_rules.bathroom",
            ),
            check_minimum(
                "toilet_left_clearance",
                toilet_bounds["min"][0],
                clearances["toilet_side_clearance"],
                "design_rules.bathroom",
            ),
            check_minimum(
                "toilet_right_clearance",
                width - toilet_bounds["max"][0],
                clearances["toilet_side_clearance"],
                "design_rules.bathroom",
            ),
            check_minimum(
                "vanity_front_clearance",
                depth - vanity_bounds["max"][1],
                clearances["vanity_front_clearance"],
                "design_rules.bathroom",
            ),
            check_minimum(
                "door_swing_clearance",
                components["door_001"]["dimensions"]["width"],
                clearances["door_swing_clearance"],
                "design_rules.bathroom",
            ),
            check_minimum(
                "circulation_clear_width",
                min(
                    toilet_bounds["min"][1],
                    toilet_bounds["min"][0] - door_bounds["max"][0],
                    depth - vanity_bounds["max"][1],
                ),
                clearances["circulation_min_width"],
                "design_rules.bathroom",
            ),
        ]
    )

    return {
        "valid": all(check["valid"] for check in checks),
        "checks": checks,
    }


def build_bridge_operations(
    width: float,
    depth: float,
    ceiling_height: float,
    components: dict[str, dict[str, Any]],
    component_library: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build a bridge operation trace without connecting to SketchUp."""
    wall_height = ceiling_height
    wall_thickness = 100
    operations: list[dict[str, Any]] = [
        {
            "operation_id": "wall_south",
            "operation_type": "create_wall",
            "payload": {
                "start": [0, 0, 0],
                "end": [width, 0, 0],
                "height": wall_height,
                "thickness": wall_thickness,
                "alignment": "inner",
            },
            "rollback_on_failure": True,
        },
        {
            "operation_id": "wall_east",
            "operation_type": "create_wall",
            "payload": {
                "start": [width, 0, 0],
                "end": [width, depth, 0],
                "height": wall_height,
                "thickness": wall_thickness,
                "alignment": "inner",
            },
            "rollback_on_failure": True,
        },
        {
            "operation_id": "wall_north",
            "operation_type": "create_wall",
            "payload": {
                "start": [width, depth, 0],
                "end": [0, depth, 0],
                "height": wall_height,
                "thickness": wall_thickness,
                "alignment": "inner",
            },
            "rollback_on_failure": True,
        },
        {
            "operation_id": "wall_west",
            "operation_type": "create_wall",
            "payload": {
                "start": [0, depth, 0],
                "end": [0, 0, 0],
                "height": wall_height,
                "thickness": wall_thickness,
                "alignment": "inner",
            },
            "rollback_on_failure": True,
        },
    ]

    for instance_id, instance in components.items():
        manifest = get_component(component_library, instance["component_ref"])
        operations.append(
            {
                "operation_id": f"place_{instance_id}",
                "operation_type": "place_component",
                "payload": {
                    "component_id": manifest["id"],
                    "instance_id": instance_id,
                    "skp_path": resolve_skp_path(component_skp_path(manifest)),
                    "procedural_fallback": manifest["assets"].get("procedural_fallback"),
                    "position": instance["position"],
                    "rotation": instance["rotation"],
                    "scale": 1,
                },
                "rollback_on_failure": True,
            }
        )

    light_manifest = get_component(component_library, "ceiling_light_basic")
    operations.append(
        {
            "operation_id": "place_ceiling_light_001",
            "operation_type": "place_component",
            "payload": {
                "component_id": light_manifest["id"],
                "instance_id": "ceiling_light_001",
                "skp_path": resolve_skp_path(component_skp_path(light_manifest)),
                "procedural_fallback": light_manifest["assets"].get(
                    "procedural_fallback"
                ),
                "position": [width / 2, depth / 2, ceiling_height],
                "rotation": 0,
                "scale": 1,
            },
            "rollback_on_failure": True,
        }
    )

    return operations


def plan_bathroom_project(
    project_name: str = "bathroom_mvp",
    width: float = 2000,
    depth: float = 1800,
    ceiling_height: float = 2400,
    rules: dict[str, Any] | None = None,
    component_library: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a deterministic bathroom plan without requiring SketchUp."""
    if width <= 0 or depth <= 0 or ceiling_height <= 0:
        raise ValueError("Bathroom dimensions must be positive millimeter values.")

    rules = copy.deepcopy(rules or create_default_design_rules())
    component_library = copy.deepcopy(component_library or load_library())
    components = build_bathroom_components(
        width=width,
        depth=depth,
        ceiling_height=ceiling_height,
        rules=rules,
        component_library=component_library,
    )
    validation_report = validate_bathroom_layout(width, depth, components, rules)
    now = utc_now()

    design_model = {
        "version": "1.0",
        "project_name": project_name,
        "created_at": now,
        "updated_at": now,
        "metadata": {
            "style": "neutral_seed",
            "ceiling_height": ceiling_height,
            "units": "mm",
            "generator": "bathroom_headless_planner",
        },
        "spaces": {
            "bathroom_001": {
                "type": "bathroom",
                "bounds": {
                    "min": [0, 0, 0],
                    "max": [width, depth, ceiling_height],
                },
                "center": [width / 2, depth / 2, ceiling_height / 2],
            }
        },
        "components": components,
        "lighting": {
            "ceiling_light_001": {
                "type": "recessed_light",
                "position": [width / 2, depth / 2, ceiling_height],
                "component_ref": "ceiling_light_basic",
            }
        },
        "semantic_anchors": {
            "bathroom_001": {
                "center_floor": [width / 2, depth / 2, 0],
                "center_ceiling": [width / 2, depth / 2, ceiling_height],
            }
        },
        "layers": {
            "Doors": {"color": "#8C6A43"},
            "Fixtures": {"color": "#F2F2F2"},
            "Lighting": {"color": "#FFE8A3"},
            "Walls": {"color": "#D9D9D9"},
        },
        "validation": validation_report,
    }

    bridge_operations = build_bridge_operations(
        width=width,
        depth=depth,
        ceiling_height=ceiling_height,
        components=components,
        component_library=component_library,
    )

    return {
        "design_model": design_model,
        "design_rules": rules,
        "validation_report": validation_report,
        "bridge_operations": bridge_operations,
    }


def save_bathroom_plan(project_path: str | Path, plan: dict[str, Any]) -> dict[str, str]:
    """Write a bathroom plan into a project directory."""
    root = Path(project_path)
    root.mkdir(parents=True, exist_ok=True)

    design_model_path = root / DESIGN_MODEL_FILENAME
    design_rules_path = root / DESIGN_RULES_FILENAME

    design_model_path.write_text(
        json.dumps(plan["design_model"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    design_rules_path.write_text(
        json.dumps(plan["design_rules"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "design_model_path": str(design_model_path),
        "design_rules_path": str(design_rules_path),
    }
