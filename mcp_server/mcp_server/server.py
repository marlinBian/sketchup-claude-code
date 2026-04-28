"""FastMCP entry point for SketchUp Agent Harness MCP server."""

import json
from pathlib import Path
from typing import Any
from mcp.server import Server
from mcp.types import Tool, Resource, TextContent
from mcp.server.fastmcp import FastMCP

from mcp_server.tools import model_tools, query_tools, placement_tools
from mcp_server.bridge.socket_bridge import SocketBridge
from mcp_server.protocol.jsonrpc import JsonRpcRequest
from mcp_server.resources import design_model_mcp
from mcp_server.resources.asset_lock_schema import build_assets_lock
from mcp_server.resources.component_manifest_schema import validate_component_library
from mcp_server.resources.design_model_schema import load_design_model, save_design_model
from mcp_server.resources.snapshot_manifest_schema import (
    append_snapshot_entry,
    append_visual_feedback_entry,
    load_snapshot_manifest,
    snapshot_entry,
    snapshot_output_path,
    validate_snapshot_manifest,
    visual_feedback_entry,
)
from mcp_server.resources.design_rules_schema import (
    create_default_design_rules,
    effective_design_rules,
    load_design_rules,
    save_design_rules,
)
from mcp_server.resources.project_files import (
    assets_lock_path,
    design_rules_path,
    find_design_model_path,
    project_component_library_path,
    snapshot_manifest_path,
)
from mcp_server.project_assets import (
    refresh_project_asset_lock as refresh_project_asset_lock_file,
)
from mcp_server.project_state import read_project_state
from mcp_server.project_versions import (
    list_project_versions as list_project_versions_file,
    restore_project_version as restore_project_version_file,
    save_project_version as save_project_version_file,
)
from mcp_server.smoke import validate_project as run_project_validation
from mcp_server.tools.local_library_search import (
    format_search_results,
    get_categories,
    get_component_by_id,
    load_effective_library,
    load_project_library,
    normalize_category,
    save_project_library,
    search_library,
)
from mcp_server.tools.bathroom_planner import (
    component_dimensions,
    component_dimensions_for_rules,
    plan_bathroom_project,
    save_bathroom_plan,
)
from mcp_server.tools.project_executor import (
    bridge_operation_for_component_instance,
    build_project_execution_plan,
    execute_project_execution_plan,
)
from mcp_server.tools.trace_executor import (
    execute_bridge_operations,
    sync_execution_report_to_design_model,
)

# Create FastMCP server
mcp = FastMCP("sketchup-mcp")


def project_rules_or_default(project_path: str | None) -> dict[str, Any] | None:
    """Load effective design rules from defaults, profile, and project."""
    rules, errors = effective_design_rules(project_path)
    if errors:
        raise ValueError("; ".join(errors))
    return rules


def load_or_create_project_design_rules(
    project_path: str,
) -> tuple[Path, dict[str, Any], list[str]]:
    """Load project design rules or create default rules in memory."""
    path = design_rules_path(project_path)
    if Path(path).exists():
        rules, errors = load_design_rules(path)
        if errors or rules is None:
            return path, {}, errors
        return path, rules, []

    return path, create_default_design_rules(), []


def default_layer_for_component(component: dict[str, Any]) -> str:
    """Return a design model layer for a component manifest category."""
    return {
        "appliance": "Fixtures",
        "decor": "Other",
        "fixture": "Fixtures",
        "furniture": "Furniture",
        "lighting": "Lighting",
        "opening": "Doors",
        "other": "Other",
    }.get(str(component.get("category", "other")), "Other")


def next_component_instance_id(
    design_model: dict[str, Any],
    component: dict[str, Any],
) -> str:
    """Return a deterministic unused instance ID for a manifest component."""
    base = str(component.get("subcategory") or component["id"])
    existing = set(design_model.get("components", {}).keys())
    index = 1
    while True:
        instance_id = f"{base}_{index:03d}"
        if instance_id not in existing:
            return instance_id
        index += 1


def component_instance_bounds(
    position: list[float],
    dimensions: dict[str, float],
    insertion_offset: list[float],
) -> dict[str, list[float]]:
    """Return axis-aligned bounds from insertion point, dimensions, and offset."""
    min_x = position[0] - float(insertion_offset[0])
    min_y = position[1] - float(insertion_offset[1])
    min_z = position[2] - float(insertion_offset[2])
    return {
        "min": [min_x, min_y, min_z],
        "max": [
            min_x + dimensions["width"],
            min_y + dimensions["depth"],
            min_z + dimensions["height"],
        ],
    }


def component_instance_anchors(
    position: list[float],
    bounds: dict[str, list[float]],
    dimensions: dict[str, float],
) -> dict[str, list[float]]:
    """Return generic world-space anchors for a component instance."""
    min_x, min_y, min_z = bounds["min"]
    return {
        "insertion": position,
        "bottom": [
            min_x + dimensions["width"] / 2,
            min_y + dimensions["depth"] / 2,
            min_z,
        ],
        "center": [
            min_x + dimensions["width"] / 2,
            min_y + dimensions["depth"] / 2,
            min_z + dimensions["height"] / 2,
        ],
        "back": [
            min_x + dimensions["width"] / 2,
            bounds["max"][1],
            min_z,
        ],
    }


def refresh_project_assets_lock(
    project_path: str,
    design_model: dict[str, Any],
) -> Path:
    """Refresh assets.lock.json from current design model component refs."""
    library, library_errors = load_effective_library(project_path)
    if library_errors:
        raise ValueError("; ".join(library_errors))
    lock_path = assets_lock_path(project_path)
    lock_path.write_text(
        json.dumps(
            build_assets_lock(design_model, library, project_path=project_path),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return lock_path


def selection_info_from_bridge(limit: int = 100) -> dict[str, Any]:
    """Read current SketchUp selection metadata from the Ruby bridge."""
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"selection_{id(selection_info_from_bridge)}",
                "operation_type": "get_selection_info",
                "payload": {"limit": limit},
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        result = response.get("result", {})
        selection_info = result.get("selection_info")
        if not isinstance(selection_info, dict):
            raise RuntimeError("Bridge response did not include selection_info.")
        return selection_info
    finally:
        bridge.disconnect()


def component_asset_paths(
    project_path: str,
    component_id: str,
    skp_path: str | None = None,
) -> tuple[str, str]:
    """Return manifest and absolute output paths for a project-local SKP asset."""
    manifest_path = skp_path or f"assets/components/{component_id}.skp"
    output_path = Path(manifest_path).expanduser()
    if not output_path.is_absolute():
        output_path = Path(project_path).expanduser().resolve() / manifest_path
    return manifest_path, str(output_path)


def save_selected_component_asset_to_bridge(
    output_path: str,
    selection_index: int = 0,
    selection_entity_id: str | None = None,
    definition_name: str | None = None,
) -> dict[str, Any]:
    """Ask the SketchUp bridge to save the selected component as a SKP asset."""
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": (
                    "save_selected_component_"
                    f"{id(save_selected_component_asset_to_bridge)}"
                ),
                "operation_type": "save_selected_component",
                "payload": {
                    "output_path": output_path,
                    "selection_index": selection_index,
                    "entity_id": selection_entity_id,
                    "definition_name": definition_name,
                },
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Bridge response did not include result.")
        return result
    finally:
        bridge.disconnect()


def bounds_dimensions(bounds: dict[str, Any]) -> dict[str, float]:
    """Return positive dimensions from a SketchUp bounding box in millimeters."""
    minimum = bounds.get("min")
    maximum = bounds.get("max")
    if not isinstance(minimum, list) or not isinstance(maximum, list):
        raise ValueError("selection bounding_box must include min and max lists.")
    if len(minimum) != 3 or len(maximum) != 3:
        raise ValueError("selection bounding_box min and max must be 3D points.")

    width = float(maximum[0]) - float(minimum[0])
    depth = float(maximum[1]) - float(minimum[1])
    height = float(maximum[2]) - float(minimum[2])
    if width <= 0 or depth <= 0 or height <= 0:
        raise ValueError(
            "selected entity bounds are degenerate; select a 3D group or "
            "component, or register dimensions explicitly."
        )
    return {"width": width, "depth": depth, "height": height}


def select_entity_summary(
    selection_info: dict[str, Any],
    selection_index: int = 0,
    selection_entity_id: str | None = None,
) -> dict[str, Any]:
    """Pick one entity summary from bridge selection metadata."""
    entities = selection_info.get("entities", [])
    if not isinstance(entities, list) or not entities:
        raise ValueError("no SketchUp entities selected.")

    if selection_entity_id:
        for entity in entities:
            if str(entity.get("entityID")) == str(selection_entity_id):
                return entity
        raise ValueError(f"selected entity not found: {selection_entity_id}")

    if selection_index < 0 or selection_index >= len(entities):
        raise ValueError(
            f"selection_index out of range: {selection_index}; "
            f"selected_count={len(entities)}"
        )
    entity = entities[selection_index]
    if not isinstance(entity, dict):
        raise ValueError("selection entity summary must be an object.")
    return entity


def selected_visual_feedback_action(
    manifest: dict[str, Any],
    review_id: str,
    action_index: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Return one visual feedback review/action pair or an error message."""
    review = next(
        (item for item in manifest.get("reviews", []) if item.get("id") == review_id),
        None,
    )
    if review is None:
        return None, None, f"review not found: {review_id}"

    actions = review.get("actions", [])
    if action_index < 0 or action_index >= len(actions):
        return review, None, f"action_index out of range: {action_index}"

    action = actions[action_index]
    if not isinstance(action, dict):
        return review, None, "visual feedback action must be an object."
    return review, action, None


def component_manifest_insertion_offset(
    component: dict[str, Any] | None,
    dimensions: dict[str, float],
) -> list[float]:
    """Return insertion offset for component bounds recalculation."""
    if component:
        offset = component.get("insertion_point", {}).get("offset")
        if isinstance(offset, list) and len(offset) == 3:
            return [float(offset[0]), float(offset[1]), float(offset[2])]
    return [float(dimensions["width"]) / 2, 0.0, 0.0]


def apply_component_visual_action(
    project_path: str,
    design_model: dict[str, Any],
    target: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply one structured visual feedback action to a component instance."""
    components = design_model.setdefault("components", {})
    if target not in components:
        raise ValueError(f"component target not found: {target}")

    instance = components[target]
    manifest = None
    if payload.get("component_ref"):
        manifest = get_component_by_id(
            str(payload["component_ref"]),
            project_path=project_path,
        )
        if manifest is None:
            raise ValueError(f"component manifest not found: {payload['component_ref']}")
        instance["component_ref"] = manifest["id"]
        instance["type"] = str(manifest.get("subcategory") or manifest.get("category"))
        instance["name"] = str(payload.get("name") or manifest["name"])
        instance["dimensions"] = component_dimensions(manifest)
        instance["clearance"] = manifest.get("clearance", {})
        instance["layer"] = str(
            payload.get("layer") or default_layer_for_component(manifest)
        )
        instance["skp_path"] = placement_tools.resolve_skp_path(
            placement_tools.component_skp_path(manifest)
        )

    for key, value in payload.items():
        if key in {"component_ref"}:
            continue
        if key in {
            "position",
            "rotation",
            "layer",
            "name",
            "dimensions",
            "clearance",
            "semantic_anchor",
            "relative_to",
            "materials",
        }:
            instance[key] = value

    dimensions = instance.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError(f"component target has invalid dimensions: {target}")
    normalized_dimensions = {
        "width": float(dimensions["width"]),
        "depth": float(dimensions["depth"]),
        "height": float(dimensions["height"]),
    }
    instance["dimensions"] = normalized_dimensions

    position = instance.get("position")
    if not isinstance(position, list) or len(position) != 3:
        raise ValueError(f"component target has invalid position: {target}")
    normalized_position = [
        float(position[0]),
        float(position[1]),
        float(position[2]),
    ]
    instance["position"] = normalized_position

    if manifest is None and instance.get("component_ref"):
        manifest = get_component_by_id(
            str(instance["component_ref"]),
            project_path=project_path,
        )
    insertion_offset = component_manifest_insertion_offset(manifest, normalized_dimensions)
    bounds = component_instance_bounds(
        normalized_position,
        normalized_dimensions,
        insertion_offset,
    )
    instance["bounds"] = bounds
    instance["anchors"] = component_instance_anchors(
        normalized_position,
        bounds,
        normalized_dimensions,
    )
    instance.setdefault("source", {})
    instance["source"]["visual_feedback"] = {
        "kind": "structured_visual_action",
    }
    return instance


def apply_lighting_visual_action(
    design_model: dict[str, Any],
    target: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply one structured visual feedback action to a lighting instance."""
    lighting = design_model.setdefault("lighting", {})
    if target not in lighting:
        raise ValueError(f"lighting target not found: {target}")
    lighting[target].update(payload)
    lighting[target].setdefault("source", {})
    lighting[target]["source"]["visual_feedback"] = {
        "kind": "structured_visual_action",
    }
    return lighting[target]


def apply_material_visual_action(
    design_model: dict[str, Any],
    target: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply one structured material action to project metadata or a component."""
    if target in design_model.get("components", {}):
        component = design_model["components"][target]
        component.setdefault("materials", {})
        component["materials"].update(payload)
        return component["materials"]

    metadata = design_model.setdefault("metadata", {})
    metadata.setdefault("materials", {})
    metadata["materials"][target] = payload
    return metadata["materials"]


def apply_rule_visual_action(
    project_path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply one structured visual feedback action to project design rules."""
    path, rules, errors = load_or_create_project_design_rules(project_path)
    if errors:
        raise ValueError("; ".join(errors))

    rule_kind = str(payload.get("rule_kind") or payload.get("kind") or "")
    rules["source"] = str(payload.get("source") or "visual_feedback_override")

    if rule_kind == "clearance":
        rule_set = str(payload.get("rule_set") or "")
        clearance_name = str(payload.get("clearance_name") or "")
        if not rule_set or not clearance_name or "value" not in payload:
            raise ValueError(
                "rule payload must include rule_set, clearance_name, and value."
            )
        value = float(payload["value"])
        if value < 0:
            raise ValueError("clearance value must be non-negative.")
        rules.setdefault("rule_sets", {})
        rules["rule_sets"].setdefault(
            rule_set,
            {
                "description": f"Project-local {rule_set} rules.",
                "clearances": {},
            },
        )
        rules["rule_sets"][rule_set].setdefault("clearances", {})
        rules["rule_sets"][rule_set]["clearances"][clearance_name] = value
        applied = {
            "rule_kind": rule_kind,
            "rule_set": rule_set,
            "clearance_name": clearance_name,
            "value": value,
            "units": "mm",
        }
    elif rule_kind == "fixture_dimension":
        rule_set = str(payload.get("rule_set") or "")
        fixture_name = str(payload.get("fixture_name") or "")
        dimensions = payload.get("dimensions")
        if not rule_set or not fixture_name or not isinstance(dimensions, dict):
            raise ValueError(
                "rule payload must include rule_set, fixture_name, and dimensions."
            )
        normalized_dimensions = {
            "width": float(dimensions["width"]),
            "depth": float(dimensions["depth"]),
            "height": float(dimensions["height"]),
        }
        if any(value < 0 for value in normalized_dimensions.values()):
            raise ValueError("fixture dimensions must be non-negative.")
        rules.setdefault("rule_sets", {})
        rules["rule_sets"].setdefault(
            rule_set,
            {
                "description": f"Project-local {rule_set} rules.",
                "clearances": {},
            },
        )
        rules["rule_sets"][rule_set].setdefault("fixture_dimensions", {})
        rules["rule_sets"][rule_set]["fixture_dimensions"][fixture_name] = (
            normalized_dimensions
        )
        applied = {
            "rule_kind": rule_kind,
            "rule_set": rule_set,
            "fixture_name": fixture_name,
            "dimensions": normalized_dimensions,
            "units": "mm",
        }
    elif rule_kind == "preference":
        preference_name = str(payload.get("preference_name") or "")
        if not preference_name or "value" not in payload:
            raise ValueError(
                "rule payload must include preference_name and value."
            )
        value = str(payload["value"])
        rules.setdefault("preferences", {})
        rules["preferences"][preference_name] = value
        applied = {
            "rule_kind": rule_kind,
            "preference_name": preference_name,
            "value": value,
        }
    else:
        raise ValueError(
            "rule payload must set rule_kind to clearance, fixture_dimension, "
            "or preference."
        )

    saved, save_errors = save_design_rules(path, rules)
    if not saved:
        raise ValueError("; ".join(save_errors))

    applied["design_rules_path"] = str(path)
    applied["source"] = rules["source"]
    return applied


@mcp.tool()
async def get_bridge_info() -> TextContent:
    """Get live SketchUp bridge version and supported operation metadata."""
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"bridge_info_{id(get_bridge_info)}",
                "operation_type": "get_bridge_info",
                "payload": {},
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        result = response.get("result", {})
        return TextContent(
            type="text",
            text=json.dumps(
                result.get("bridge_info", {}),
                ensure_ascii=False,
                indent=2,
            ),
        )
    finally:
        bridge.disconnect()


@mcp.tool()
async def get_scene_info() -> TextContent:
    """Get current SketchUp scene information.

    Returns model bounding box, entity counts by type, and layer list.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"query_{id(get_scene_info)}",
                "operation_type": "get_scene_info",
                "payload": {},
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        result = response.get("result", {})
        return TextContent(type="text", text=str(result.get("scene_info", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def get_selection_info(limit: int = 100) -> TextContent:
    """Get current SketchUp selection information for component registration."""
    try:
        selection_info = selection_info_from_bridge(limit=limit)
        return TextContent(
            type="text",
            text=json.dumps(
                selection_info,
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Selection info failed: {str(e)}")


@mcp.tool()
async def get_design_rules(project_path: str) -> TextContent:
    """Read project-local design rules."""
    try:
        path = design_rules_path(project_path)
        rules, errors = load_design_rules(path)
        if errors:
            return TextContent(type="text", text=f"Design rules failed: {'; '.join(errors)}")
        return TextContent(
            type="text",
            text=json.dumps(rules, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Design rules failed: {str(e)}")


@mcp.tool()
async def set_design_clearance(
    project_path: str,
    rule_set: str,
    clearance_name: str,
    value: float,
    source: str = "project_user_override",
) -> TextContent:
    """Set one project-local clearance value in millimeters."""
    try:
        path, rules, errors = load_or_create_project_design_rules(project_path)
        if errors:
            return TextContent(
                type="text",
                text=f"Design rules failed: {'; '.join(errors)}",
            )

        rules["source"] = source
        rules.setdefault("rule_sets", {})
        rules["rule_sets"].setdefault(
            rule_set,
            {
                "description": f"Project-local {rule_set} rules.",
                "clearances": {},
            },
        )
        rules["rule_sets"][rule_set].setdefault("clearances", {})
        rules["rule_sets"][rule_set]["clearances"][clearance_name] = value

        saved, save_errors = save_design_rules(path, rules)
        if not saved:
            return TextContent(
                type="text",
                text=f"Design rules failed: {'; '.join(save_errors)}",
            )

        response = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "design_rules_path": str(path),
            "rule_set": rule_set,
            "clearance_name": clearance_name,
            "value": value,
            "units": "mm",
            "source": source,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Design rules failed: {str(e)}")


@mcp.tool()
async def set_fixture_dimension(
    project_path: str,
    rule_set: str,
    fixture_name: str,
    width: float,
    depth: float,
    height: float,
    source: str = "project_user_override",
) -> TextContent:
    """Set one project-local fixture dimension in millimeters."""
    try:
        path, rules, errors = load_or_create_project_design_rules(project_path)
        if errors:
            return TextContent(
                type="text",
                text=f"Design rules failed: {'; '.join(errors)}",
            )

        rules["source"] = source
        rules.setdefault("rule_sets", {})
        rules["rule_sets"].setdefault(
            rule_set,
            {
                "description": f"Project-local {rule_set} rules.",
                "clearances": {},
            },
        )
        rules["rule_sets"][rule_set].setdefault("fixture_dimensions", {})
        rules["rule_sets"][rule_set]["fixture_dimensions"][fixture_name] = {
            "width": width,
            "depth": depth,
            "height": height,
        }

        saved, save_errors = save_design_rules(path, rules)
        if not saved:
            return TextContent(
                type="text",
                text=f"Design rules failed: {'; '.join(save_errors)}",
            )

        response = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "design_rules_path": str(path),
            "rule_set": rule_set,
            "fixture_name": fixture_name,
            "dimensions": {
                "width": width,
                "depth": depth,
                "height": height,
            },
            "units": "mm",
            "source": source,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Design rules failed: {str(e)}")


@mcp.tool()
async def set_design_preference(
    project_path: str,
    preference_name: str,
    value: str,
    source: str = "project_user_override",
) -> TextContent:
    """Set one project-local free-form design preference."""
    try:
        path, rules, errors = load_or_create_project_design_rules(project_path)
        if errors:
            return TextContent(
                type="text",
                text=f"Design rules failed: {'; '.join(errors)}",
            )

        rules["source"] = source
        rules.setdefault("preferences", {})
        rules["preferences"][preference_name] = value

        saved, save_errors = save_design_rules(path, rules)
        if not saved:
            return TextContent(
                type="text",
                text=f"Design rules failed: {'; '.join(save_errors)}",
            )

        response = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "design_rules_path": str(path),
            "preference_name": preference_name,
            "value": value,
            "source": source,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Design rules failed: {str(e)}")


@mcp.tool()
async def get_project_state(
    project_path: str,
    include_rules: bool = True,
    include_assets: bool = True,
    include_visual_feedback: bool = True,
    include_versions: bool = True,
    include_execution: bool = True,
) -> TextContent:
    """Read the project truth plus compact supporting project state."""
    try:
        response = read_project_state(
            project_path,
            include_rules=include_rules,
            include_assets=include_assets,
            include_visual_feedback=include_visual_feedback,
            include_versions=include_versions,
            include_execution=include_execution,
        )
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project state failed: {str(e)}")


@mcp.tool()
async def list_project_components(
    project_path: str,
    include_lighting: bool = True,
) -> TextContent:
    """List component-like instances currently referenced by a project."""
    try:
        path = find_design_model_path(project_path)
        design_model, errors = load_design_model(str(path))
        if errors or design_model is None:
            return TextContent(
                type="text",
                text=f"Project components failed: {'; '.join(errors)}",
            )

        components = [
            {**component, "id": component_id, "kind": "component"}
            for component_id, component in design_model.get("components", {}).items()
        ]
        if include_lighting:
            components.extend(
                {**lighting, "id": lighting_id, "kind": "lighting"}
                for lighting_id, lighting in design_model.get("lighting", {}).items()
            )

        response = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "design_model_path": str(path),
            "count": len(components),
            "components": components,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project components failed: {str(e)}")


@mcp.tool()
async def validate_design_project(project_path: str) -> TextContent:
    """Validate core project files using the same checks as the CLI."""
    try:
        result = run_project_validation(project_path)
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project validation failed: {str(e)}")


@mcp.tool()
async def refresh_project_asset_lock(project_path: str) -> TextContent:
    """Regenerate assets.lock.json from current project truth and components."""
    try:
        result = refresh_project_asset_lock_file(project_path)
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project asset lock failed: {str(e)}")


@mcp.tool()
async def create_wall(
    start_x: float,
    start_y: float,
    start_z: float,
    end_x: float,
    end_y: float,
    end_z: float,
    height: float,
    thickness: float,
    alignment: str = "center",
) -> TextContent:
    """Create a wall in SketchUp.

    Args:
        start_x, start_y, start_z: Start point coordinates in mm
        end_x, end_y, end_z: End point coordinates in mm
        height: Wall height in mm
        thickness: Wall thickness in mm
        alignment: Wall alignment - "center", "inner", or "outer"

    Returns:
        JSON string with entity_id and spatial_delta of created wall.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"wall_{id(create_wall)}",
                "operation_type": "create_wall",
                "payload": {
                    "start": [start_x, start_y, start_z],
                    "end": [end_x, end_y, end_z],
                    "height": height,
                    "thickness": thickness,
                    "alignment": alignment,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_face(vertices: list[list[float]], layer: str | None = None) -> TextContent:
    """Create a face from vertices."""
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"face_{id(create_face)}",
                "operation_type": "create_face",
                "payload": {"vertices": vertices, "layer": layer},
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_box(
    corner_x: float,
    corner_y: float,
    corner_z: float,
    width: float,
    depth: float,
    height: float,
) -> TextContent:
    """Create a 3D box."""
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"box_{id(create_box)}",
                "operation_type": "create_box",
                "payload": {
                    "corner": [corner_x, corner_y, corner_z],
                    "width": width,
                    "depth": depth,
                    "height": height,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def place_component(
    component_name: str,
    position_x: float = 0,
    position_y: float = 0,
    position_z: float = 0,
    rotation: float = 0,
    scale: float = 1,
) -> TextContent:
    """Place a furniture component from the component library.

    Args:
        component_name: Name of component (e.g., "现代双人沙发")
        position_x, position_y, position_z: Position in mm
        rotation: Rotation angle in degrees
        scale: Scale factor (1.0 = default size)
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        # First find the component in library
        component = placement_tools.find_component_by_name(component_name)
        if not component:
            return TextContent(type="text", text=f"Error: Component not found: {component_name}")

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"place_{id(place_component)}",
                "operation_type": "place_component",
                "payload": {
                    "skp_path": placement_tools.resolve_skp_path(
                        placement_tools.component_skp_path(component)
                    ),
                    "position": [position_x, position_y, position_z],
                    "rotation": rotation,
                    "scale": scale,
                    "component_id": component["id"],
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def apply_material(
    entity_ids: list[str],
    color: str | None = None,
    material_id: str | None = None,
    texture_scale_x: int | None = None,
    texture_scale_y: int | None = None,
) -> TextContent:
    """Apply material to entities.

    Args:
        entity_ids: List of entity IDs to apply material to
        color: Hex color (e.g., "#C67B5C") or RGB array [r, g, b]
        material_id: Optional SketchUp material name
        texture_scale_x: Texture scale X in mm
        texture_scale_y: Texture scale Y in mm
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        texture_scale = None
        if texture_scale_x and texture_scale_y:
            texture_scale = [texture_scale_x, texture_scale_y]

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"material_{id(apply_material)}",
                "operation_type": "apply_material",
                "payload": {
                    "entity_ids": entity_ids,
                    "color": color,
                    "material_id": material_id,
                    "texture_scale": texture_scale,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def apply_style(
    style_name: str,
    entity_ids: list[str] | None = None,
) -> TextContent:
    """Apply a complete style preset to the model or specific entities.

    Args:
        style_name: Style preset name.
                    Options: "japandi_cream", "modern_industrial", "scandinavian",
                             "mediterranean", "bohemian", "contemporary_minimalist"
        entity_ids: Optional list of entity IDs to apply style to.
                    If None, applies to all faces in the model.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"style_{id(apply_style)}",
                "operation_type": "apply_style",
                "payload": {
                    "style_name": style_name,
                    "entity_ids": entity_ids,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def place_lighting(
    lighting_type: str,
    position_x: float,
    position_y: float,
    position_z: float = 0,
    ceiling_height: float = 2400,
    mount_height: float = 2000,
    rotation: float = 0,
) -> TextContent:
    """Place a lighting fixture.

    Args:
        lighting_type: Type - "spotlight", "chandelier", "floor_lamp"
        position_x, position_y, position_z: Position in mm
        ceiling_height: Ceiling height for spotlight placement
        mount_height: Mount height for chandelier
        rotation: Rotation angle in degrees
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"light_{id(place_lighting)}",
                "operation_type": "place_lighting",
                "payload": {
                    "lighting_type": lighting_type,
                    "position": [position_x, position_y, position_z],
                    "ceiling_height": ceiling_height,
                    "mount_height": mount_height,
                    "rotation": rotation,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def set_camera_view(
    view_preset: str | None = None,
    eye_x: float | None = None,
    eye_y: float | None = None,
    eye_z: float | None = None,
    target_x: float | None = None,
    target_y: float | None = None,
    target_z: float | None = None,
) -> TextContent:
    """Set the camera view position.

    Args:
        view_preset: Preset name - "panoramic", "living_room_birdseye",
                     "master_bedroom", "dining_area", "front_entrance"
        eye_x/y/z: Custom camera eye position (required for custom view)
        target_x/y/z: Custom camera target position
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        payload = {"view_preset": view_preset}

        if view_preset is None and eye_x is not None:
            payload["eye"] = [eye_x, eye_y or 0, eye_z or 0]
            payload["target"] = [target_x or 0, target_y or 0, target_z or 0]

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"camera_{id(set_camera_view)}",
                "operation_type": "set_camera_view",
                "payload": payload,
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {}).get("view_info", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def capture_design(
    output_path: str,
    view_preset: str | None = None,
    width: int = 1920,
    height: int = 1080,
    return_base64: bool = False,
) -> TextContent:
    """Capture the current design view to an image file.

    Args:
        output_path: Full path to output image file
        view_preset: Optional view preset to set before capture
        width: Image width in pixels
        height: Image height in pixels
        return_base64: If True, return base64 encoded image for Claude vision

    Returns:
        Capture info including base64 image if requested.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"capture_{id(capture_design)}",
                "operation_type": "capture_design",
                "payload": {
                    "output_path": output_path,
                    "view_preset": view_preset,
                    "width": width,
                    "height": height,
                    "return_base64": return_base64,
                },
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")

        result = response.get("result", {})
        capture_info = result.get("capture_info", {})

        # If base64 requested, read the file and encode
        if return_base64:
            import base64
            try:
                with open(output_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                capture_info["image_base64"] = img_data
            except Exception as e:
                capture_info["image_base64_error"] = str(e)

        return TextContent(type="text", text=str(capture_info))
    finally:
        bridge.disconnect()


@mcp.tool()
async def capture_project_snapshot(
    project_path: str,
    view_preset: str | None = "top",
    label: str | None = None,
    width: int = 1920,
    height: int = 1080,
    return_base64: bool = False,
    prompt: str | None = None,
) -> TextContent:
    """Capture a project snapshot and record provenance.

    Args:
        project_path: Designer project directory containing design_model.json.
        view_preset: Optional SketchUp camera preset.
        label: Optional filename-safe label. Defaults to view preset.
        width: Image width in pixels.
        height: Image height in pixels.
        return_base64: If True, return base64 encoded image for vision review.
        prompt: Optional user prompt that requested this visual artifact.

    Returns:
        JSON string with capture info and the snapshot manifest entry.
    """
    output_path = snapshot_output_path(
        project_path=project_path,
        view_preset=view_preset,
        label=label,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"snapshot_{id(capture_project_snapshot)}",
                "operation_type": "capture_design",
                "payload": {
                    "output_path": str(output_path),
                    "view_preset": view_preset,
                    "width": width,
                    "height": height,
                    "return_base64": return_base64,
                },
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")

        result = response.get("result", {})
        capture_info = result.get("capture_info", {})

        if return_base64:
            import base64
            try:
                with open(output_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                capture_info["image_base64"] = img_data
            except Exception as e:
                capture_info["image_base64_error"] = str(e)

        entry = snapshot_entry(
            project_path=project_path,
            output_path=output_path,
            view_preset=view_preset,
            width=width,
            height=height,
            prompt=prompt,
        )
        append_snapshot_entry(project_path, entry)

        response_payload = {
            "capture_info": capture_info,
            "snapshot": entry,
            "manifest_path": str(snapshot_manifest_path(project_path)),
        }
        return TextContent(
            type="text",
            text=json.dumps(response_payload, ensure_ascii=False),
        )
    finally:
        bridge.disconnect()


@mcp.tool()
async def record_visual_feedback(
    project_path: str,
    summary: str,
    actions: list[dict[str, Any]],
    source_snapshot_id: str | None = None,
    source_snapshot_file: str | None = None,
    prompt: str | None = None,
    reviewer: str = "agent",
    renderer_tool: str | None = None,
    renderer_model: str | None = None,
) -> TextContent:
    """Record advisory visual feedback as structured proposed actions.

    This tool does not mutate design_model.json. It stores the interpretation
    step that must happen between visual review and structured model changes.
    """
    try:
        entry = visual_feedback_entry(
            summary=summary,
            actions=actions,
            source_snapshot_id=source_snapshot_id,
            source_snapshot_file=source_snapshot_file,
            prompt=prompt,
            reviewer=reviewer,
            renderer_tool=renderer_tool,
            renderer_model=renderer_model,
        )
        append_visual_feedback_entry(project_path, entry)
        response_payload = {
            "visual_feedback": entry,
            "manifest_path": str(snapshot_manifest_path(project_path)),
            "advisory": True,
        }
        return TextContent(
            type="text",
            text=json.dumps(response_payload, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Visual feedback failed: {str(e)}")


@mcp.tool()
async def list_visual_feedback(project_path: str) -> TextContent:
    """List advisory visual feedback reviews for a project."""
    try:
        manifest_path = snapshot_manifest_path(project_path)
        manifest, errors = load_snapshot_manifest(manifest_path)
        if errors or manifest is None:
            return TextContent(
                type="text",
                text=f"Visual feedback failed: {'; '.join(errors)}",
            )
        response_payload = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "manifest_path": str(manifest_path),
            "reviews": manifest.get("reviews", []),
        }
        return TextContent(
            type="text",
            text=json.dumps(response_payload, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Visual feedback failed: {str(e)}")


@mcp.tool()
async def update_visual_feedback_action_status(
    project_path: str,
    review_id: str,
    action_index: int,
    status: str,
) -> TextContent:
    """Update one visual feedback action status without mutating design truth."""
    try:
        if status not in {"proposed", "accepted", "rejected", "applied"}:
            return TextContent(
                type="text",
                text=(
                    "Visual feedback failed: status must be one of proposed, "
                    "accepted, rejected, applied."
                ),
            )

        manifest_path = snapshot_manifest_path(project_path)
        manifest, errors = load_snapshot_manifest(manifest_path)
        if errors or manifest is None:
            return TextContent(
                type="text",
                text=f"Visual feedback failed: {'; '.join(errors)}",
            )

        reviews = manifest.get("reviews", [])
        review = next(
            (item for item in reviews if item.get("id") == review_id),
            None,
        )
        if review is None:
            return TextContent(
                type="text",
                text=f"Visual feedback failed: review not found: {review_id}",
            )

        actions = review.get("actions", [])
        if action_index < 0 or action_index >= len(actions):
            return TextContent(
                type="text",
                text=(
                    "Visual feedback failed: action_index out of range: "
                    f"{action_index}"
                ),
            )

        actions[action_index]["status"] = status
        is_valid, validation_errors = validate_snapshot_manifest(manifest)
        if not is_valid:
            return TextContent(
                type="text",
                text=f"Visual feedback failed: {'; '.join(validation_errors)}",
            )

        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        response_payload = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "manifest_path": str(manifest_path),
            "review_id": review_id,
            "action_index": action_index,
            "status": status,
            "action": actions[action_index],
            "advisory": True,
        }
        return TextContent(
            type="text",
            text=json.dumps(response_payload, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Visual feedback failed: {str(e)}")


@mcp.tool()
async def apply_visual_feedback_action(
    project_path: str,
    review_id: str,
    action_index: int,
) -> TextContent:
    """Apply one supported visual feedback action to structured project truth."""
    try:
        manifest_path = snapshot_manifest_path(project_path)
        manifest, manifest_errors = load_snapshot_manifest(manifest_path)
        if manifest_errors or manifest is None:
            return TextContent(
                type="text",
                text=f"Visual feedback apply failed: {'; '.join(manifest_errors)}",
            )

        review, action, action_error = selected_visual_feedback_action(
            manifest,
            review_id,
            action_index,
        )
        if action_error or action is None:
            return TextContent(
                type="text",
                text=f"Visual feedback apply failed: {action_error}",
            )

        action_type = str(action.get("type"))
        target = str(action.get("target"))
        payload = action.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return TextContent(
                type="text",
                text="Visual feedback apply failed: action payload must be an object.",
            )

        design_model_path = find_design_model_path(project_path)
        design_model, model_errors = load_design_model(str(design_model_path))
        if model_errors or design_model is None:
            return TextContent(
                type="text",
                text=f"Visual feedback apply failed: {'; '.join(model_errors)}",
            )

        applied: dict[str, Any]
        refresh_lock = False
        rules_path = None
        if action_type == "component":
            applied = apply_component_visual_action(
                project_path,
                design_model,
                target,
                payload,
            )
            refresh_lock = True
        elif action_type == "lighting":
            applied = apply_lighting_visual_action(design_model, target, payload)
            refresh_lock = bool(payload.get("component_ref"))
        elif action_type == "material":
            applied = apply_material_visual_action(design_model, target, payload)
        elif action_type == "rule":
            applied = apply_rule_visual_action(project_path, payload)
            rules_path = applied.get("design_rules_path")
        elif action_type == "style":
            style = (
                payload.get("style")
                or payload.get("style_name")
                or payload.get("value")
            )
            if not style:
                return TextContent(
                    type="text",
                    text="Visual feedback apply failed: style payload must include style.",
                )
            design_model.setdefault("metadata", {})["style"] = str(style)
            applied = {"style": str(style)}
        elif action_type == "note":
            applied = {"note": action.get("intent", "")}
        else:
            return TextContent(
                type="text",
                text=(
                    "Visual feedback apply failed: action type is not supported "
                    f"for automatic application: {action_type}"
                ),
            )

        design_model.setdefault("metadata", {})
        design_model["metadata"].setdefault("visual_feedback", {})
        design_model["metadata"]["visual_feedback"]["last_applied"] = {
            "review_id": review_id,
            "action_index": action_index,
            "type": action_type,
            "target": target,
        }

        saved, save_errors = save_design_model(str(design_model_path), design_model)
        if not saved:
            return TextContent(
                type="text",
                text=f"Visual feedback apply failed: {'; '.join(save_errors)}",
            )

        lock_path = None
        if refresh_lock:
            lock_path = refresh_project_assets_lock(project_path, design_model)

        action["status"] = "applied"
        is_valid, validation_errors = validate_snapshot_manifest(manifest)
        if not is_valid:
            return TextContent(
                type="text",
                text=f"Visual feedback apply failed: {'; '.join(validation_errors)}",
            )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        response_payload = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "design_model_path": str(design_model_path),
            "design_rules_path": str(rules_path) if rules_path else None,
            "assets_lock_path": str(lock_path) if lock_path else None,
            "manifest_path": str(manifest_path),
            "review_id": review_id,
            "action_index": action_index,
            "action": action,
            "applied": applied,
            "status": "applied",
            "source_review": review,
        }
        return TextContent(
            type="text",
            text=json.dumps(response_payload, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Visual feedback apply failed: {str(e)}")


@mcp.tool()
async def cleanup_model(
    layer_names: list[str] | None = None,
    tag: str | None = None,
) -> TextContent:
    """Clean up AI-generated content from the model.

    Args:
        layer_names: Specific layer names to clean. If None, cleans all AI layers.
                     Options: "Walls", "Furniture", "Fixtures", "Lighting", "Materials"
        tag: Alternative cleanup by component definition name containing tag.

    Returns:
        Cleanup summary with deleted count and entity IDs.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"cleanup_{id(cleanup_model)}",
                "operation_type": "cleanup_model",
                "payload": {
                    "layer_names": layer_names,
                    "tag": tag,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")

        result = response.get("result", {})
        cleanup_info = result.get("cleanup_info", {})

        return TextContent(type="text", text=str(cleanup_info))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_door(
    wall_id: str,
    position_x: float,
    position_y: float = 0,
    width: float = 900,
    height: float = 2100,
    swing_direction: str = "left",
) -> TextContent:
    """Create a door in a SketchUp wall with frame and swing panel.

    Args:
        wall_id: Entity ID of the wall to place door in
        position_x: Position along the wall from start in mm
        position_y: Position from wall face in mm (default 0)
        width: Door width in mm (default 900mm)
        height: Door height in mm (default 2100mm)
        swing_direction: "left" or "right" swing

    Returns:
        JSON string with entity_id and spatial_delta of created door.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"door_{id(create_door)}",
                "operation_type": "create_door",
                "payload": {
                    "wall_id": wall_id,
                    "position_x": position_x,
                    "position_y": position_y,
                    "width": width,
                    "height": height,
                    "swing_direction": swing_direction,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_window(
    wall_id: str,
    position_x: float,
    position_y: float = 0,
    width: float = 1200,
    height: float = 1000,
    sill_height: float = 900,
) -> TextContent:
    """Create a window in a SketchUp wall with frame and glass.

    Args:
        wall_id: Entity ID of the wall to place window in
        position_x: Position along the wall from start in mm
        position_y: Position from wall face in mm (default 0)
        width: Window width in mm (default 1200mm)
        height: Window height in mm (default 1000mm)
        sill_height: Height from floor to windowsill in mm (default 900mm)

    Returns:
        JSON string with entity_id and spatial_delta of created window.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"window_{id(create_window)}",
                "operation_type": "create_window",
                "payload": {
                    "wall_id": wall_id,
                    "position_x": position_x,
                    "position_y": position_y,
                    "width": width,
                    "height": height,
                    "sill_height": sill_height,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_stairs(
    start_x: float,
    start_y: float,
    start_z: float,
    end_x: float,
    end_y: float,
    end_z: float,
    width: float = 1000,
    num_steps: int | None = None,
) -> TextContent:
    """Create a staircase between two levels in SketchUp.

    Args:
        start_x, start_y, start_z: Start position (bottom of stairs) in mm
        end_x, end_y, end_z: End position (top of stairs) in mm
        width: Stair width in mm (default 1000mm)
        num_steps: Number of steps (calculated from rise if not provided)

    Returns:
        JSON string with entity_id, spatial_delta, and stairs_info of created stairs.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"stairs_{id(create_stairs)}",
                "operation_type": "create_stairs",
                "payload": {
                    "start_x": start_x,
                    "start_y": start_y,
                    "start_z": start_z,
                    "end_x": end_x,
                    "end_y": end_y,
                    "end_z": end_z,
                    "width": width,
                    "num_steps": num_steps,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def search_local_library(
    query: str,
    category: str | None = None,
    limit: int = 10,
    project_path: str | None = None,
) -> TextContent:
    """Search local component library for matching components.

    Use this to find furniture, fixtures, and lighting from the user's
    local SketchUp component library before using place_component.

    Args:
        query: Search query (e.g., "sofa", "dining table", "北欧风格")
        category: Optional category filter - "furniture", "fixture", "lighting"
        limit: Maximum number of results (default 10)

    Returns:
        List of matching components with IDs and paths for place_component.
    """
    try:
        library, errors = load_effective_library(project_path)
        if errors:
            return TextContent(type="text", text=f"Search failed: {'; '.join(errors)}")
        results = search_library(
            query,
            category=category,
            limit=limit,
            library_data=library,
        )
        formatted = format_search_results(results)
        return TextContent(type="text", text=formatted)
    except Exception as e:
        return TextContent(type="text", text=f"Search failed: {str(e)}")


@mcp.tool()
async def search_components(
    query: str,
    category: str | None = None,
    limit: int = 10,
    project_path: str | None = None,
) -> TextContent:
    """Search the component registry and return machine-readable results."""
    try:
        library, errors = load_effective_library(project_path)
        if errors:
            return TextContent(
                type="text",
                text=f"Component search failed: {'; '.join(errors)}",
            )
        results = search_library(
            query,
            category=category,
            limit=limit,
            library_data=library,
        )
        response = {
            "query": query,
            "category": category,
            "limit": limit,
            "project_path": project_path,
            "count": len(results),
            "components": results,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Component search failed: {str(e)}")


@mcp.tool()
async def get_component_manifest(
    component_id: str,
    project_path: str | None = None,
) -> TextContent:
    """Read one component manifest entry by canonical registry ID."""
    try:
        component = get_component_by_id(component_id, project_path=project_path)
        if component is None:
            return TextContent(
                type="text",
                text=f"Component not found: {component_id}",
            )
        response = {
            "component_id": component_id,
            "project_path": project_path,
            "component": component,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Component manifest failed: {str(e)}")


@mcp.tool()
async def register_project_component(
    project_path: str,
    component_id: str,
    name: str,
    category: str,
    width: float,
    depth: float,
    height: float,
    subcategory: str | None = None,
    skp_path: str | None = None,
    procedural_fallback: str | None = "box_component",
    insertion_offset_x: float | None = None,
    insertion_offset_y: float = 0,
    insertion_offset_z: float = 0,
    anchor_back: str | None = None,
    anchor_bottom: str | None = "floor",
    clearance_front: float | None = None,
    clearance_left: float | None = None,
    clearance_right: float | None = None,
    aliases_en: list[str] | None = None,
    aliases_zh_cn: list[str] | None = None,
    tags: list[str] | None = None,
    license_type: str = "unknown",
    license_source: str = "project_local",
    license_author: str | None = None,
    license_url: str | None = None,
    redistribution: str = "Project-local component metadata.",
    overwrite: bool = False,
) -> TextContent:
    """Register one project-local semantic component manifest entry."""
    try:
        if width <= 0 or depth <= 0 or height <= 0:
            return TextContent(
                type="text",
                text="Project component failed: dimensions must be positive.",
            )

        category_value = normalize_category(category) or category
        project_library, errors = load_project_library(project_path)
        if errors:
            return TextContent(
                type="text",
                text=f"Project component failed: {'; '.join(errors)}",
            )

        packaged = get_component_by_id(component_id)
        project_existing = get_component_by_id(component_id, library_data=project_library)
        if packaged is not None and project_existing is None:
            return TextContent(
                type="text",
                text=(
                    "Project component failed: component ID already exists in "
                    f"packaged registry: {component_id}"
                ),
            )
        if project_existing is not None and not overwrite:
            return TextContent(
                type="text",
                text=f"Project component failed: component already exists: {component_id}",
            )

        anchors = {}
        if anchor_bottom:
            anchors["bottom"] = anchor_bottom
        if anchor_back:
            anchors["back"] = anchor_back
        if not anchors:
            anchors["center"] = "free"

        clearance = {}
        for key, value in (
            ("front", clearance_front),
            ("left", clearance_left),
            ("right", clearance_right),
        ):
            if value is not None:
                clearance[key] = value

        assets = {"skp_path": skp_path or f"assets/components/{component_id}.skp"}
        if procedural_fallback:
            assets["procedural_fallback"] = procedural_fallback

        license_info = {
            "type": license_type,
            "source": license_source,
            "redistribution": redistribution,
        }
        if license_author:
            license_info["author"] = license_author
        if license_url:
            license_info["url"] = license_url

        component = {
            "id": component_id,
            "name": name,
            "category": category_value,
            "dimensions": {
                "width": width,
                "depth": depth,
                "height": height,
            },
            "bounds": {
                "min": [0, 0, 0],
                "max": [width, depth, height],
            },
            "insertion_point": {
                "offset": [
                    insertion_offset_x if insertion_offset_x is not None else width / 2,
                    insertion_offset_y,
                    insertion_offset_z,
                ],
                "description": "Project-local insertion point.",
            },
            "anchors": anchors,
            "clearance": clearance,
            "assets": assets,
            "license": license_info,
            "aliases": {
                "en": aliases_en or [],
                "zh-CN": aliases_zh_cn or [],
            },
        }
        if subcategory:
            component["subcategory"] = subcategory
        if tags:
            component["tags"] = tags

        if overwrite:
            project_library["components"] = [
                item
                for item in project_library.get("components", [])
                if item.get("id") != component_id
            ]
        project_library.setdefault("components", []).append(component)

        is_valid, validation_errors = validate_component_library(project_library)
        if not is_valid:
            return TextContent(
                type="text",
                text=f"Project component failed: {'; '.join(validation_errors)}",
            )

        saved, save_errors = save_project_library(project_path, project_library)
        if not saved:
            return TextContent(
                type="text",
                text=f"Project component failed: {'; '.join(save_errors)}",
            )

        response = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "component_library_path": str(project_component_library_path(project_path)),
            "component_id": component_id,
            "component": component,
            "overwritten": project_existing is not None and overwrite,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project component failed: {str(e)}")


@mcp.tool()
async def register_selected_component(
    project_path: str,
    component_id: str,
    category: str = "other",
    name: str | None = None,
    subcategory: str | None = None,
    selection_index: int = 0,
    selection_entity_id: str | None = None,
    skp_path: str | None = None,
    procedural_fallback: str | None = "box_component",
    anchor_back: str | None = None,
    anchor_bottom: str | None = "floor",
    clearance_front: float | None = None,
    clearance_left: float | None = None,
    clearance_right: float | None = None,
    aliases_en: list[str] | None = None,
    aliases_zh_cn: list[str] | None = None,
    tags: list[str] | None = None,
    export_asset: bool = False,
    license_type: str = "project_local",
    license_author: str | None = None,
    license_url: str | None = None,
    redistribution: str = "Project-local metadata inferred from SketchUp selection.",
    overwrite: bool = False,
) -> TextContent:
    """Register a project-local component from the current SketchUp selection."""
    try:
        selection_info = selection_info_from_bridge(limit=max(selection_index + 1, 100))
        entity = select_entity_summary(
            selection_info,
            selection_index=selection_index,
            selection_entity_id=selection_entity_id,
        )
        dimensions = bounds_dimensions(entity.get("bounding_box", {}))
        inferred_name = (
            name
            or entity.get("definition_name")
            or entity.get("name")
            or component_id.replace("_", " ").title()
        )
        merged_tags = list(tags or [])
        for tag in ("project-local", "sketchup-selection"):
            if tag not in merged_tags:
                merged_tags.append(tag)

        manifest_skp_path = skp_path
        asset_export = None
        if export_asset:
            project_library, errors = load_project_library(project_path)
            if errors:
                return TextContent(
                    type="text",
                    text=(
                        "Project component from selection failed: "
                        f"{'; '.join(errors)}"
                    ),
                )
            packaged = get_component_by_id(component_id)
            project_existing = get_component_by_id(
                component_id,
                library_data=project_library,
            )
            if packaged is not None and project_existing is None:
                return TextContent(
                    type="text",
                    text=(
                        "Project component from selection failed: component ID "
                        f"already exists in packaged registry: {component_id}"
                    ),
                )
            if project_existing is not None and not overwrite:
                return TextContent(
                    type="text",
                    text=(
                        "Project component from selection failed: component already "
                        f"exists: {component_id}"
                    ),
                )
            manifest_skp_path, output_path = component_asset_paths(
                project_path,
                component_id,
                skp_path,
            )
            asset_export = save_selected_component_asset_to_bridge(
                output_path=output_path,
                selection_index=selection_index,
                selection_entity_id=selection_entity_id,
                definition_name=str(inferred_name),
            )

        response = await register_project_component(
            project_path=project_path,
            component_id=component_id,
            name=str(inferred_name),
            category=category,
            width=dimensions["width"],
            depth=dimensions["depth"],
            height=dimensions["height"],
            subcategory=subcategory,
            skp_path=manifest_skp_path,
            procedural_fallback=procedural_fallback,
            insertion_offset_x=dimensions["width"] / 2,
            insertion_offset_y=0,
            insertion_offset_z=0,
            anchor_back=anchor_back,
            anchor_bottom=anchor_bottom,
            clearance_front=clearance_front,
            clearance_left=clearance_left,
            clearance_right=clearance_right,
            aliases_en=aliases_en or [str(inferred_name)],
            aliases_zh_cn=aliases_zh_cn,
            tags=merged_tags,
            license_type=license_type,
            license_source="sketchup_selection",
            license_author=license_author,
            license_url=license_url,
            redistribution=redistribution,
            overwrite=overwrite,
        )

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            return TextContent(
                type="text",
                text=response.text.replace(
                    "Project component failed:",
                    "Project component from selection failed:",
                    1,
                ),
            )

        data["source_selection"] = {
            "entity_id": str(entity.get("entityID", "")),
            "type": entity.get("type"),
            "name": entity.get("name"),
            "definition_name": entity.get("definition_name"),
            "layer": entity.get("layer"),
            "bounding_box": entity.get("bounding_box"),
        }
        data["selection_count"] = selection_info.get("selected_count")
        if asset_export is not None:
            data["asset_export"] = asset_export
        return TextContent(
            type="text",
            text=json.dumps(data, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(
            type="text",
            text=f"Project component from selection failed: {str(e)}",
        )


@mcp.tool()
async def add_component_instance(
    project_path: str,
    component_id: str,
    position_x: float,
    position_y: float,
    position_z: float = 0,
    instance_id: str | None = None,
    rotation: float = 0,
    layer: str | None = None,
    name: str | None = None,
) -> TextContent:
    """Add a semantic component instance to design_model.json and assets.lock.json."""
    try:
        design_model_path = find_design_model_path(project_path)
        design_model, model_errors = load_design_model(str(design_model_path))
        if model_errors or design_model is None:
            return TextContent(
                type="text",
                text=f"Component instance failed: {'; '.join(model_errors)}",
            )

        component = get_component_by_id(component_id, project_path=project_path)
        if component is None:
            return TextContent(
                type="text",
                text=f"Component instance failed: component not found: {component_id}",
            )

        rules = project_rules_or_default(project_path)
        dimensions = (
            component_dimensions_for_rules(component, rules)
            if rules
            else component_dimensions(component)
        )
        position = [position_x, position_y, position_z]
        insertion_offset = component["insertion_point"]["offset"]
        bounds = component_instance_bounds(position, dimensions, insertion_offset)
        chosen_id = instance_id or next_component_instance_id(design_model, component)
        if chosen_id in design_model.get("components", {}):
            return TextContent(
                type="text",
                text=f"Component instance failed: instance already exists: {chosen_id}",
            )

        instance = {
            "type": str(component.get("subcategory") or component.get("category")),
            "name": name or str(component["name"]),
            "component_ref": component["id"],
            "position": position,
            "dimensions": dimensions,
            "bounds": bounds,
            "anchors": component_instance_anchors(position, bounds, dimensions),
            "clearance": component.get("clearance", {}),
            "rotation": rotation,
            "layer": layer or default_layer_for_component(component),
            "skp_path": placement_tools.resolve_skp_path(
                placement_tools.component_skp_path(component)
            ),
            "source": {
                "kind": "component_registry",
                "component_id": component["id"],
                "bounds": "axis_aligned_from_insertion_offset",
            },
        }

        design_model.setdefault("components", {})
        design_model["components"][chosen_id] = instance
        saved, save_errors = save_design_model(str(design_model_path), design_model)
        if not saved:
            return TextContent(
                type="text",
                text=f"Component instance failed: {'; '.join(save_errors)}",
            )

        library, library_errors = load_effective_library(project_path)
        if library_errors:
            return TextContent(
                type="text",
                text=f"Component instance failed: {'; '.join(library_errors)}",
            )
        lock_path = assets_lock_path(project_path)
        lock_path.write_text(
            json.dumps(
                build_assets_lock(design_model, library, project_path=project_path),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        response = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "design_model_path": str(design_model_path),
            "assets_lock_path": str(lock_path),
            "instance_id": chosen_id,
            "component_id": component["id"],
            "instance": instance,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Component instance failed: {str(e)}")


@mcp.tool()
async def execute_component_instance(
    project_path: str,
    instance_id: str,
    stop_on_error: bool = True,
) -> TextContent:
    """Execute one project component instance against the SketchUp bridge."""
    try:
        design_model_path = find_design_model_path(project_path)
        design_model, model_errors = load_design_model(str(design_model_path))
        if model_errors or design_model is None:
            return TextContent(
                type="text",
                text=f"Component execution failed: {'; '.join(model_errors)}",
            )

        instance = design_model.get("components", {}).get(instance_id)
        if instance is None:
            return TextContent(
                type="text",
                text=f"Component execution failed: instance not found: {instance_id}",
            )

        component_id = instance.get("component_ref")
        component = get_component_by_id(component_id, project_path=project_path)
        if component is None:
            return TextContent(
                type="text",
                text=f"Component execution failed: component not found: {component_id}",
            )

        operation = bridge_operation_for_component_instance(
            instance_id=instance_id,
            instance=instance,
            component=component,
            project_path=project_path,
        )
        execution_report = execute_bridge_operations(
            [operation],
            stop_on_error=stop_on_error,
        )

        entity_id = None
        if execution_report.get("status") == "success":
            first_result = execution_report["results"][0]["response"].get("result", {})
            entity_ids = first_result.get("entity_ids", [])
            if entity_ids:
                entity_id = str(entity_ids[0])
                design_model["components"][instance_id]["entity_id"] = entity_id
                saved, save_errors = save_design_model(str(design_model_path), design_model)
                if not saved:
                    return TextContent(
                        type="text",
                        text=f"Component execution failed: {'; '.join(save_errors)}",
                    )

        response = {
            "project_path": str(Path(project_path).expanduser().resolve()),
            "design_model_path": str(design_model_path),
            "instance_id": instance_id,
            "component_id": component_id,
            "entity_id": entity_id,
            "operation": operation,
            "execution_report": execution_report,
        }
        return TextContent(
            type="text",
            text=json.dumps(response, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Component execution failed: {str(e)}")


@mcp.tool()
async def plan_project_execution(
    project_path: str,
    include_spaces: bool = True,
    include_components: bool = True,
    include_lighting: bool = True,
    include_scene_info: bool = True,
) -> TextContent:
    """Build a bridge operation trace from current design_model.json truth."""
    try:
        plan = build_project_execution_plan(
            project_path,
            include_spaces=include_spaces,
            include_components=include_components,
            include_lighting=include_lighting,
            include_scene_info=include_scene_info,
        )
        return TextContent(
            type="text",
            text=json.dumps(plan, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project execution failed: {str(e)}")


@mcp.tool()
async def execute_project_model(
    project_path: str,
    stop_on_error: bool = True,
    allow_partial: bool = False,
    include_spaces: bool = True,
    include_components: bool = True,
    include_lighting: bool = True,
    include_scene_info: bool = True,
) -> TextContent:
    """Execute current design_model.json truth against the SketchUp bridge."""
    try:
        plan = execute_project_execution_plan(
            project_path,
            stop_on_error=stop_on_error,
            allow_partial=allow_partial,
            include_spaces=include_spaces,
            include_components=include_components,
            include_lighting=include_lighting,
            include_scene_info=include_scene_info,
            execute_fn=execute_bridge_operations,
        )
        return TextContent(
            type="text",
            text=json.dumps(plan, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project execution failed: {str(e)}")


@mcp.tool()
async def list_local_library_categories(project_path: str | None = None) -> TextContent:
    """List all available categories in the local component library.

    Returns:
        List of categories like "furniture", "fixture", "lighting".
    """
    try:
        library, errors = load_effective_library(project_path)
        if errors:
            return TextContent(
                type="text",
                text=f"Failed to load categories: {'; '.join(errors)}",
            )
        categories = get_categories(library)
        if not categories:
            return TextContent(type="text", text="No categories found in library.")
        return TextContent(
            type="text",
            text="Available categories:\n- " + "\n- ".join(categories),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Failed to load categories: {str(e)}")


@mcp.tool()
async def plan_bathroom(
    project_name: str = "bathroom_mvp",
    width: float = 2000,
    depth: float = 1800,
    ceiling_height: float = 2400,
    project_path: str | None = None,
) -> TextContent:
    """Plan a small bathroom without requiring a live SketchUp bridge.

    Generates a design_model, design_rules, validation report, and bridge
    operation trace for the first vertical slice. If project_path is provided,
    design_model.json and design_rules.json are written into that directory.
    """
    try:
        plan = plan_bathroom_project(
            project_name=project_name,
            width=width,
            depth=depth,
            ceiling_height=ceiling_height,
            rules=project_rules_or_default(project_path),
        )
        if project_path:
            plan["written_files"] = save_bathroom_plan(project_path, plan)
        return TextContent(
            type="text",
            text=json.dumps(plan, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Bathroom planning failed: {str(e)}")


@mcp.tool()
async def execute_bathroom_plan(
    project_name: str = "bathroom_mvp",
    width: float = 2000,
    depth: float = 1800,
    ceiling_height: float = 2400,
    project_path: str | None = None,
    stop_on_error: bool = True,
) -> TextContent:
    """Plan and execute the seed bathroom operation trace in SketchUp."""
    try:
        plan = plan_bathroom_project(
            project_name=project_name,
            width=width,
            depth=depth,
            ceiling_height=ceiling_height,
            rules=project_rules_or_default(project_path),
        )
        if project_path:
            plan["written_files"] = save_bathroom_plan(project_path, plan)
        plan["execution_report"] = execute_bridge_operations(
            plan["bridge_operations"],
            stop_on_error=stop_on_error,
        )
        if project_path and plan["execution_report"].get("status") == "success":
            sync_report = sync_execution_report_to_design_model(
                plan["design_model"],
                plan["execution_report"],
            )
            design_model_path = find_design_model_path(project_path)
            saved, save_errors = save_design_model(str(design_model_path), plan["design_model"])
            sync_report["saved"] = saved
            sync_report["errors"] = save_errors
            plan["execution_sync"] = sync_report
        return TextContent(
            type="text",
            text=json.dumps(plan, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Bathroom execution failed: {str(e)}")

@mcp.tool()
async def generate_report(project_name: str, project_dir: str = "./designs") -> TextContent:
    """Generate a design report with snapshots and component list.

    Args:
        project_name: Name of the project
        project_dir: Base directory for designs

    Returns:
        Path to generated report and summary.
    """
    try:
        from mcp_server.tools.report_tools import generate_design_report

        result = generate_design_report(project_name, project_dir)
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Error generating report: {str(e)}")


@mcp.tool()
async def generate_project_report(
    project_path: str,
    output_path: str | None = None,
) -> TextContent:
    """Generate an English-first Markdown report from a project workspace."""
    try:
        from mcp_server.tools.report_tools import generate_project_report as generate

        result = generate(project_path, output_path=output_path)
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Error generating project report: {str(e)}")


@mcp.tool()
async def save_project_version(
    project_path: str,
    version_tag: str,
    description: str = "",
    overwrite: bool = False,
) -> TextContent:
    """Save current structured project truth into a project-local version."""
    try:
        result = save_project_version_file(
            project_path,
            version_tag=version_tag,
            description=description,
            overwrite=overwrite,
        )
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project version failed: {str(e)}")


@mcp.tool()
async def list_project_versions(project_path: str) -> TextContent:
    """List project-local structured truth versions."""
    try:
        result = list_project_versions_file(project_path)
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project versions failed: {str(e)}")


@mcp.tool()
async def restore_project_version(
    project_path: str,
    version_tag: str,
    overwrite_current: bool = False,
) -> TextContent:
    """Restore a project-local structured truth version into current files."""
    try:
        result = restore_project_version_file(
            project_path,
            version_tag=version_tag,
            overwrite_current=overwrite_current,
        )
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project version restore failed: {str(e)}")


@mcp.tool()
async def save_version(
    project_name: str,
    version_tag: str,
    description: str = "",
    project_dir: str = "./designs",
    overwrite: bool = False,
) -> TextContent:
    """Compatibility alias for saving structured project truth as a version.

    Args:
        project_name: Name of the project
        version_tag: Version identifier (e.g., "v1.0", "draft_2")
        description: Brief description of this version
        project_dir: Base directory for designs
        overwrite: Whether to replace an existing version tag

    Returns:
        JSON summary for the saved project version.
    """
    try:
        result = save_project_version_file(
            Path(project_dir).expanduser() / project_name,
            version_tag=version_tag,
            description=description,
            overwrite=overwrite,
        )
        result["compatibility_alias"] = "save_version"
        result["preferred_tool"] = "save_project_version"
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project version failed: {str(e)}")


@mcp.tool()
async def list_versions(project_name: str, project_dir: str = "./designs") -> TextContent:
    """Compatibility alias for listing structured project truth versions.

    Args:
        project_name: Name of the project
        project_dir: Base directory for designs

    Returns:
        JSON summary for saved project versions.
    """
    try:
        result = list_project_versions_file(Path(project_dir).expanduser() / project_name)
        result["compatibility_alias"] = "list_versions"
        result["preferred_tool"] = "list_project_versions"
        return TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Project versions failed: {str(e)}")


@mcp.tool()
async def search_sketchfab_models(
    query: str,
    count: int = 10,
    sort: str = "relevance",
) -> TextContent:
    """Search Sketchfab for 3D models.

    Use this to find furniture, fixtures, and decorative objects from
    Sketchfab's library of Creative Commons licensed 3D models.

    Args:
        query: Search query (e.g., "modern sofa", "floor lamp", "potted plant")
        count: Number of results to return (max 50)
        sort: Sort order - "relevance", "newest", "likes", "views"

    Returns:
        List of matching 3D models with download links and metadata.
    """
    from mcp_server.tools.sketchfab_tools import search_models

    try:
        results = search_models(
            query=query,
            count=count,
            sort=sort,
        )
        return TextContent(type="text", text=str(results))
    except Exception as e:
        return TextContent(type="text", text=f"Search failed: {str(e)}")


@mcp.tool()
async def get_sketchfab_model(model_uid: str) -> TextContent:
    """Get detailed information about a Sketchfab model.

    Args:
        model_uid: Sketchfab model UID (from search results)

    Returns:
        Detailed model information including download formats and links.
    """
    from mcp_server.tools.sketchfab_tools import get_model_info

    try:
        info = get_model_info(model_uid)
        return TextContent(type="text", text=str(info))
    except Exception as e:
        return TextContent(type="text", text=f"Failed to get model info: {str(e)}")


@mcp.tool()
async def download_sketchfab_model(
    model_uid: str,
    format_hint: str | None = "obj",
    output_dir: str | None = None,
) -> TextContent:
    """Download a Sketchfab 3D model.

    Downloads the model in the specified format (OBJ recommended for SketchUp).
    After download, models can be imported into SketchUp.

    Args:
        model_uid: Sketchfab model UID (from search results)
        format_hint: Preferred format - "obj" (recommended for SketchUp), "gltf", "glb"
        output_dir: Output directory (defaults to ~/SketchUp/SCC/downloaded_models/)

    Returns:
        Download status and file path.
    """
    from pathlib import Path
    from mcp_server.tools.sketchfab_tools import download_model

    try:
        output_path = Path(output_dir) if output_dir else None
        result = download_model(
            uid=model_uid,
            format_hint=format_hint,
            output_dir=output_path,
        )
        return TextContent(type="text", text=str(result))
    except Exception as e:
        return TextContent(type="text", text=f"Download failed: {str(e)}")


@mcp.tool()
async def search_and_download_sketchfab(
    query: str,
    format_hint: str = "obj",
) -> TextContent:
    """Search Sketchfab and download the top result in one step.

    Convenience function that searches for models and downloads the
    first downloadable result.

    Args:
        query: Search query (e.g., "minimalist coffee table")
        format_hint: Preferred format - "obj" (recommended for SketchUp), "gltf", "glb"

    Returns:
        Search results and download status.
    """
    from pathlib import Path
    from mcp_server.tools.sketchfab_tools import search_and_download

    try:
        result = search_and_download(
            query=query,
            format_hint=format_hint,
        )
        return TextContent(type="text", text=str(result))
    except Exception as e:
        return TextContent(type="text", text=f"Search and download failed: {str(e)}")


@mcp.tool()
async def search_warehouse(query: str) -> TextContent:
    """Get a SketchUp 3D Warehouse search URL.

    Opens the 3D Warehouse search page in your browser where you can
    browse and download 3D models.

    Note: 3D Warehouse does not have a public API, so this tool provides
    a search URL that you can open in your browser.

    Args:
        query: Search query (e.g., "modern sofa", "floor lamp")

    Returns:
        URL to open in browser for searching 3D Warehouse.
    """
    from mcp_server.tools.warehouse_tool import search_warehouse_url

    url = search_warehouse_url(query)
    return TextContent(type="text", text=f"Open this URL in your browser to search 3D Warehouse:\n\n{url}")


@mcp.tool()
async def download_from_warehouse(warehouse_url: str) -> TextContent:
    """Get guidance for downloading a model from SketchUp 3D Warehouse URL.

    Note: 3D Warehouse does not have a public API. This tool provides
    guidance for the manual download process.

    Args:
        warehouse_url: Full URL to a 3D Warehouse model page
                       (e.g., https://3dwarehouse.sketchup.com/model/abc123/...)

    Returns:
        Instructions for downloading the model.
    """
    from mcp_server.tools.warehouse_tool import download_from_warehouse

    result = download_from_warehouse(warehouse_url)
    return TextContent(type="text", text=result.message)


@mcp.tool()
async def get_warehouse_model_info(warehouse_url: str) -> TextContent:
    """Extract model information from a SketchUp 3D Warehouse URL.

    Note: 3D Warehouse does not have a public API. This tool does
    best-effort extraction of model ID from the URL pattern.

    Args:
        warehouse_url: Full URL to a 3D Warehouse model page

    Returns:
        Model ID and URL extracted from the link.
    """
    from mcp_server.tools.warehouse_tool import get_model_info_from_url

    info = get_model_info_from_url(warehouse_url)
    return TextContent(type="text", text=str(info))


@mcp.tool()
async def move_entity(
    entity_ids: list[str],
    delta_x: float,
    delta_y: float,
    delta_z: float,
) -> TextContent:
    """Move entities by a delta in mm.

    Args:
        entity_ids: List of entity IDs to move
        delta_x: Delta X in mm
        delta_y: Delta Y in mm
        delta_z: Delta Z in mm

    Returns:
        JSON string with entity_ids and status of moved entities.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"move_{id(move_entity)}",
                "operation_type": "move_entity",
                "payload": {
                    "entity_ids": entity_ids,
                    "delta": [delta_x, delta_y, delta_z],
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def rotate_entity(
    entity_ids: list[str],
    center_x: float,
    center_y: float,
    center_z: float,
    axis: str,
    angle: float,
) -> TextContent:
    """Rotate entities around a center point and axis.

    Args:
        entity_ids: List of entity IDs to rotate
        center_x: Center X coordinate in mm
        center_y: Center Y coordinate in mm
        center_z: Center Z coordinate in mm
        axis: Rotation axis - "+x", "-x", "+y", "-y", "+z", "-z"
        angle: Rotation angle in degrees

    Returns:
        JSON string with entity_ids and status of rotated entities.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"rotate_{id(rotate_entity)}",
                "operation_type": "rotate_entity",
                "payload": {
                    "entity_ids": entity_ids,
                    "center": [center_x, center_y, center_z],
                    "axis": axis,
                    "angle": angle,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def scale_entity(
    entity_ids: list[str],
    center_x: float,
    center_y: float,
    center_z: float,
    scale: float | list[float],
) -> TextContent:
    """Scale entities uniformly or non-uniformly around a center point.

    Args:
        entity_ids: List of entity IDs to scale
        center_x: Center X coordinate in mm
        center_y: Center Y coordinate in mm
        center_z: Center Z coordinate in mm
        scale: Uniform scale factor (float) or [sx, sy, sz] for non-uniform scaling

    Returns:
        JSON string with entity_ids and status of scaled entities.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"scale_{id(scale_entity)}",
                "operation_type": "scale_entity",
                "payload": {
                    "entity_ids": entity_ids,
                    "center": [center_x, center_y, center_z],
                    "scale": scale,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def copy_entity(
    entity_ids: list[str],
    delta_x: float,
    delta_y: float,
    delta_z: float,
) -> TextContent:
    """Create copies of entities and translate them by delta.

    Args:
        entity_ids: List of entity IDs to copy
        delta_x: Delta X in mm
        delta_y: Delta Y in mm
        delta_z: Delta Z in mm

    Returns:
        JSON string with entity_ids of the new copies.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"copy_{id(copy_entity)}",
                "operation_type": "copy_entity",
                "payload": {
                    "entity_ids": entity_ids,
                    "delta": [delta_x, delta_y, delta_z],
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


def main() -> None:
    """Run the MCP server after all tools have been registered."""
    mcp.run()


if __name__ == "__main__":
    main()
