"""Build bridge execution traces from project design_model.json truth."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any

from mcp_server.resources.design_model_schema import load_design_model, save_design_model
from mcp_server.resources.project_files import find_design_model_path
from mcp_server.tools import placement_tools
from mcp_server.tools.local_library_search import (
    get_component_by_id,
    load_effective_library,
)
from mcp_server.tools.trace_executor import (
    execute_bridge_operations,
    sync_execution_report_to_design_model,
)


DEFAULT_WALL_THICKNESS = 100.0
MIN_WALL_SEGMENT_LENGTH = 1.0
DEFAULT_CLEAN_LAYERS = [
    "Walls",
    "Doors",
    "Windows",
    "Fixtures",
    "Furniture",
    "Lighting",
    "Materials",
]


def utc_now() -> str:
    """Return an ISO8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _xyz(value: Any, field_name: str) -> list[float]:
    """Return a three-number coordinate list."""
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{field_name} must be a three-number list.")
    return [float(value[0]), float(value[1]), float(value[2])]


def _segment_length(start: list[float], end: list[float]) -> float:
    """Return the length of a wall baseline segment in millimeters."""
    return math.dist(start, end)


def _point_at_segment_distance(
    start: list[float],
    end: list[float],
    distance: float,
) -> list[float]:
    """Interpolate a point on a segment at a distance from its start."""
    length = _segment_length(start, end)
    if length <= 0:
        raise ValueError("Cannot interpolate a zero-length segment.")
    ratio = distance / length
    return [
        start[index] + (end[index] - start[index]) * ratio
        for index in range(3)
    ]


def _wall_path_length(path: list[Any], wall_id: str) -> float:
    """Return total baseline length for a wall path."""
    length = 0.0
    for index in range(len(path) - 1):
        start = _xyz(path[index], f"{wall_id}.path[{index}]")
        end = _xyz(path[index + 1], f"{wall_id}.path[{index + 1}]")
        length += _segment_length(start, end)
    return length


def _opening_cut_intervals_for_wall(
    wall_id: str,
    wall: dict[str, Any],
    openings: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return opening intervals that should cut a host wall's plan trace."""
    if not openings:
        return []

    path = wall.get("path")
    if not isinstance(path, list) or len(path) < 2:
        return []

    wall_length = _wall_path_length(path, wall_id)
    intervals: list[dict[str, Any]] = []
    for opening_id in sorted(openings):
        opening = openings[opening_id]
        if opening.get("host_wall") != wall_id:
            continue
        try:
            offset = float(opening.get("offset", 0))
            width = float(opening.get("width", 0))
        except (TypeError, ValueError):
            continue
        if width <= 0:
            continue
        start = max(offset, 0.0)
        end = min(offset + width, wall_length)
        if end - start <= MIN_WALL_SEGMENT_LENGTH:
            continue
        intervals.append(
            {
                "opening_id": opening_id,
                "start": start,
                "end": end,
            }
        )

    intervals.sort(key=lambda interval: (interval["start"], interval["end"]))
    return intervals


def _solid_intervals_for_wall_span(
    span_start: float,
    span_end: float,
    cut_intervals: list[dict[str, Any]],
) -> list[tuple[float, float]]:
    """Return solid sub-intervals after subtracting openings from one wall span."""
    cursor = span_start
    solid_intervals: list[tuple[float, float]] = []
    for interval in cut_intervals:
        cut_start = max(float(interval["start"]), span_start)
        cut_end = min(float(interval["end"]), span_end)
        if cut_end <= span_start or cut_start >= span_end:
            continue
        if cut_start - cursor > MIN_WALL_SEGMENT_LENGTH:
            solid_intervals.append((cursor, cut_start))
        cursor = max(cursor, cut_end)
    if span_end - cursor > MIN_WALL_SEGMENT_LENGTH:
        solid_intervals.append((cursor, span_end))
    return solid_intervals


def _manifest_dimensions(component: dict[str, Any]) -> dict[str, float]:
    """Return normalized dimensions from a component manifest."""
    dimensions = component.get("dimensions")
    if isinstance(dimensions, dict):
        return {
            "width": float(dimensions["width"]),
            "depth": float(dimensions["depth"]),
            "height": float(dimensions["height"]),
        }

    bounds = component.get("bounds")
    if isinstance(bounds, dict):
        min_point = _xyz(bounds.get("min"), "component.bounds.min")
        max_point = _xyz(bounds.get("max"), "component.bounds.max")
        return {
            "width": max_point[0] - min_point[0],
            "depth": max_point[1] - min_point[1],
            "height": max_point[2] - min_point[2],
        }

    raise ValueError(f"Component dimensions are missing: {component.get('id')}")


def _instance_dimensions(
    instance: dict[str, Any],
    component: dict[str, Any],
) -> dict[str, float]:
    """Return instance dimensions, falling back to manifest dimensions."""
    dimensions = instance.get("dimensions")
    if isinstance(dimensions, dict):
        return {
            "width": float(dimensions["width"]),
            "depth": float(dimensions["depth"]),
            "height": float(dimensions["height"]),
        }
    return _manifest_dimensions(component)


def resolve_project_skp_path(
    skp_path: str,
    project_path: str | Path | None = None,
) -> str:
    """Resolve environment and project-relative SKP paths for bridge payloads."""
    resolved = placement_tools.resolve_skp_path(str(skp_path))
    path = Path(resolved).expanduser()
    if path.is_absolute():
        return str(path)
    if project_path is None:
        return resolved
    return str((Path(project_path).expanduser().resolve() / path).resolve())


def bridge_operation_for_component_instance(
    instance_id: str,
    instance: dict[str, Any],
    component: dict[str, Any],
    project_path: str | Path | None = None,
    *,
    default_layer: str = "Other",
) -> dict[str, Any]:
    """Build one place_component operation from a design model instance."""
    raw_skp_path = instance.get("skp_path") or placement_tools.component_skp_path(component)
    assets = component.get("assets", {})
    dimensions = _instance_dimensions(instance, component)

    return {
        "operation_id": f"place_{instance_id}",
        "operation_type": "place_component",
        "payload": {
            "component_id": component["id"],
            "instance_id": instance_id,
            "name": instance.get("name") or component.get("name") or instance_id,
            "skp_path": resolve_project_skp_path(raw_skp_path, project_path),
            "procedural_fallback": assets.get("procedural_fallback"),
            "dimensions": dimensions,
            "layer": instance.get("layer", default_layer),
            "position": _xyz(instance.get("position"), f"{instance_id}.position"),
            "rotation": float(instance.get("rotation", 0)),
            "scale": float(instance.get("scale", 1)),
        },
        "rollback_on_failure": True,
    }


def bridge_operation_for_lighting_instance(
    instance_id: str,
    instance: dict[str, Any],
    component: dict[str, Any] | None,
    project_path: str | Path | None = None,
    *,
    ceiling_height: float = 2400.0,
) -> dict[str, Any]:
    """Build a bridge operation for a design model lighting instance."""
    if component is not None:
        return bridge_operation_for_component_instance(
            instance_id=instance_id,
            instance={
                **instance,
                "name": instance.get("name") or component.get("name") or instance_id,
                "layer": instance.get("layer", "Lighting"),
            },
            component=component,
            project_path=project_path,
            default_layer="Lighting",
        )

    position = _xyz(instance.get("position"), f"{instance_id}.position")
    lighting_type = str(instance.get("type") or "other")
    return {
        "operation_id": f"place_{instance_id}",
        "operation_type": "place_lighting",
        "payload": {
            "instance_id": instance_id,
            "lighting_type": lighting_type,
            "position": position,
            "ceiling_height": ceiling_height,
            "mount_height": position[2],
            "rotation": float(instance.get("rotation", 0)),
            "scale": float(instance.get("scale", 1)),
        },
        "rollback_on_failure": True,
    }


def bridge_operations_for_space(
    space_id: str,
    space: dict[str, Any],
    *,
    wall_thickness: float = DEFAULT_WALL_THICKNESS,
) -> list[dict[str, Any]]:
    """Build rectangular wall operations from a space bounds object."""
    bounds = space.get("bounds", {})
    min_point = _xyz(bounds.get("min"), f"{space_id}.bounds.min")
    max_point = _xyz(bounds.get("max"), f"{space_id}.bounds.max")
    min_x, min_y, min_z = min_point
    max_x, max_y, max_z = max_point
    height = max(max_z - min_z, 0)
    if height <= 0:
        raise ValueError(f"{space_id}.bounds height must be positive.")

    walls = [
        ("south", [min_x, min_y, min_z], [max_x, min_y, min_z]),
        ("east", [max_x, min_y, min_z], [max_x, max_y, min_z]),
        ("north", [max_x, max_y, min_z], [min_x, max_y, min_z]),
        ("west", [min_x, max_y, min_z], [min_x, min_y, min_z]),
    ]
    return [
        {
            "operation_id": f"wall_{space_id}_{side}",
            "operation_type": "create_wall",
            "payload": {
                "space_id": space_id,
                "wall_side": side,
                "wall_id": f"{space_id}_{side}",
                "start": start,
                "end": end,
                "height": height,
                "thickness": wall_thickness,
                "alignment": "inner",
            },
            "rollback_on_failure": True,
        }
        for side, start, end in walls
    ]


def bridge_operations_for_wall(
    wall_id: str,
    wall: dict[str, Any],
    openings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build wall operations from explicit design_model walls.

    Hosted openings are compiled as gaps in the solid wall trace so imported
    windows and doors do not appear as continuous full-height walls in plan
    view. Opening marker operations are emitted separately.
    """
    path = wall.get("path")
    if not isinstance(path, list) or len(path) < 2:
        raise ValueError(f"{wall_id}.path must include at least two points.")
    height = float(wall.get("height", 0))
    thickness = float(wall.get("thickness", 0))
    if height <= 0 or thickness <= 0:
        raise ValueError(f"{wall_id}.height and thickness must be positive.")

    cut_intervals = _opening_cut_intervals_for_wall(wall_id, wall, openings)
    operation_segments: list[dict[str, Any]] = []
    cumulative_distance = 0.0
    solid_index = 1
    for index in range(len(path) - 1):
        segment_start = _xyz(path[index], f"{wall_id}.path[{index}]")
        segment_end = _xyz(path[index + 1], f"{wall_id}.path[{index + 1}]")
        segment_length = _segment_length(segment_start, segment_end)
        if segment_length <= MIN_WALL_SEGMENT_LENGTH:
            cumulative_distance += segment_length
            continue

        span_start = cumulative_distance
        span_end = cumulative_distance + segment_length
        solid_intervals = _solid_intervals_for_wall_span(
            span_start,
            span_end,
            cut_intervals,
        )

        for solid_start, solid_end in solid_intervals:
            local_start = solid_start - span_start
            local_end = solid_end - span_start
            start = _point_at_segment_distance(segment_start, segment_end, local_start)
            end = _point_at_segment_distance(segment_start, segment_end, local_end)
            if cut_intervals:
                segment_id = f"{wall_id}_solid_{solid_index:02d}"
                solid_index += 1
            else:
                segment_id = wall_id if len(path) == 2 else f"{wall_id}_{index + 1:02d}"
            operation_segments.append(
                {
                    "segment_id": segment_id,
                    "start": start,
                    "end": end,
                }
            )
        cumulative_distance = span_end

    opening_ids = [interval["opening_id"] for interval in cut_intervals]
    return [
        {
            "operation_id": f"wall_{segment['segment_id']}",
            "operation_type": "create_wall",
            "payload": {
                "wall_id": wall_id,
                "wall_segment_id": segment["segment_id"],
                "start": segment["start"],
                "end": segment["end"],
                "height": height,
                "thickness": thickness,
                "alignment": wall.get("alignment", "inner"),
                "layer": wall.get("layer", "Walls"),
                **({"excluded_opening_ids": opening_ids} if opening_ids else {}),
            },
            "rollback_on_failure": True,
        }
        for segment in operation_segments
    ]


def _opening_box_for_wall(
    opening_id: str,
    opening: dict[str, Any],
    wall: dict[str, Any],
) -> dict[str, Any]:
    """Return an axis-aligned placeholder box payload for an opening."""
    path = wall.get("path", [])
    if not isinstance(path, list) or len(path) < 2:
        raise ValueError(f"{opening_id}.host_wall path is missing.")
    start = _xyz(path[0], f"{opening_id}.host_wall.path[0]")
    end = _xyz(path[1], f"{opening_id}.host_wall.path[1]")
    offset = float(opening.get("offset", 0))
    width = float(opening.get("width", 0))
    height = float(opening.get("height", 0))
    thickness = max(float(wall.get("thickness", DEFAULT_WALL_THICKNESS)), 1.0)
    sill_height = float(opening.get("sill_height", 0))
    if width <= 0 or height <= 0:
        raise ValueError(f"{opening_id}.width and height must be positive.")

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    horizontal = abs(dx) >= abs(dy)
    if horizontal:
        direction = 1.0 if dx >= 0 else -1.0
        x = start[0] + direction * offset
        if direction < 0:
            x -= width
        y = min(start[1], end[1])
        return {
            "corner": [x, y, sill_height],
            "width": width,
            "depth": thickness,
            "height": height,
        }

    direction = 1.0 if dy >= 0 else -1.0
    y = start[1] + direction * offset
    if direction < 0:
        y -= width
    x = min(start[0], end[0])
    return {
        "corner": [x, y, sill_height],
        "width": thickness,
        "depth": width,
        "height": height,
    }


def bridge_operation_for_opening(
    opening_id: str,
    opening: dict[str, Any],
    walls: dict[str, Any],
) -> dict[str, Any]:
    """Build a placeholder operation for an imported door or window opening."""
    host_wall_id = opening.get("host_wall")
    wall = walls.get(host_wall_id)
    if wall is None:
        raise ValueError(f"{opening_id}.host_wall not found: {host_wall_id}")
    box = _opening_box_for_wall(opening_id, opening, wall)
    layer = opening.get("layer")
    if not layer:
        layer = "Windows" if opening.get("type") == "window" else "Doors"
    return {
        "operation_id": f"opening_{opening_id}",
        "operation_type": "create_box",
        "payload": {
            "opening_id": opening_id,
            "host_wall": host_wall_id,
            "opening_type": opening.get("type", "opening"),
            "corner": box["corner"],
            "width": box["width"],
            "depth": box["depth"],
            "height": box["height"],
            "layer": layer,
        },
        "rollback_on_failure": True,
    }


def space_import_has_explicit_walls(
    space: dict[str, Any],
    walls: dict[str, Any],
) -> bool:
    """Return true when imported explicit walls should drive shell execution."""
    source = space.get("source", {}) if isinstance(space, dict) else {}
    import_id = source.get("import_id") if isinstance(source, dict) else None
    if not import_id:
        return False
    for wall in walls.values():
        wall_source = wall.get("source", {}) if isinstance(wall, dict) else {}
        if isinstance(wall_source, dict) and wall_source.get("import_id") == import_id:
            return True
    return False


def build_project_execution_plan(
    project_path: str | Path,
    *,
    include_spaces: bool = True,
    include_walls: bool = True,
    include_openings: bool = True,
    include_components: bool = True,
    include_lighting: bool = True,
    include_scene_info: bool = True,
) -> dict[str, Any]:
    """Build a deterministic bridge operation trace from current project truth."""
    root = Path(project_path).expanduser().resolve()
    design_model_path = find_design_model_path(root)
    design_model, model_errors = load_design_model(str(design_model_path))
    if model_errors or design_model is None:
        raise ValueError("; ".join(model_errors))

    library, library_errors = load_effective_library(root)
    if library_errors:
        raise ValueError("; ".join(library_errors))

    metadata = design_model.get("metadata", {})
    wall_thickness = float(metadata.get("wall_thickness", DEFAULT_WALL_THICKNESS))
    ceiling_height = float(metadata.get("ceiling_height", 2400))
    operations: list[dict[str, Any]] = []
    skipped_instances: list[dict[str, str]] = []
    walls = design_model.get("walls", {})
    openings = design_model.get("openings", {})

    if include_spaces:
        for space_id in sorted(design_model.get("spaces", {})):
            space = design_model["spaces"][space_id]
            if space_import_has_explicit_walls(space, walls):
                continue
            try:
                operations.extend(
                    bridge_operations_for_space(
                        space_id,
                        space,
                        wall_thickness=wall_thickness,
                    )
                )
            except Exception as error:
                skipped_instances.append(
                    {
                        "kind": "space",
                        "id": space_id,
                        "reason": str(error),
                    }
                )

    if include_walls:
        for wall_id in sorted(walls):
            try:
                operations.extend(
                    bridge_operations_for_wall(
                        wall_id,
                        walls[wall_id],
                        openings=openings if include_openings else None,
                    )
                )
            except Exception as error:
                skipped_instances.append(
                    {
                        "kind": "wall",
                        "id": wall_id,
                        "reason": str(error),
                    }
                )

    if include_openings:
        for opening_id in sorted(openings):
            try:
                operations.append(
                    bridge_operation_for_opening(
                        opening_id,
                        openings[opening_id],
                        walls,
                    )
                )
            except Exception as error:
                skipped_instances.append(
                    {
                        "kind": "opening",
                        "id": opening_id,
                        "reason": str(error),
                    }
                )

    if include_components:
        for instance_id in sorted(design_model.get("components", {})):
            instance = design_model["components"][instance_id]
            component_ref = instance.get("component_ref")
            component = get_component_by_id(component_ref, library_data=library)
            if component is None:
                skipped_instances.append(
                    {
                        "kind": "component",
                        "id": instance_id,
                        "reason": f"component not found: {component_ref}",
                    }
                )
                continue
            try:
                operations.append(
                    bridge_operation_for_component_instance(
                        instance_id,
                        instance,
                        component,
                        project_path=root,
                    )
                )
            except Exception as error:
                skipped_instances.append(
                    {
                        "kind": "component",
                        "id": instance_id,
                        "reason": str(error),
                    }
                )

    if include_lighting:
        for instance_id in sorted(design_model.get("lighting", {})):
            instance = design_model["lighting"][instance_id]
            component_ref = instance.get("component_ref")
            component = (
                get_component_by_id(component_ref, library_data=library)
                if component_ref
                else None
            )
            if component_ref and component is None:
                skipped_instances.append(
                    {
                        "kind": "lighting",
                        "id": instance_id,
                        "reason": f"component not found: {component_ref}",
                    }
                )
                continue
            try:
                operations.append(
                    bridge_operation_for_lighting_instance(
                        instance_id,
                        instance,
                        component,
                        project_path=root,
                        ceiling_height=ceiling_height,
                    )
                )
            except Exception as error:
                skipped_instances.append(
                    {
                        "kind": "lighting",
                        "id": instance_id,
                        "reason": str(error),
                    }
                )

    if include_scene_info:
        operations.append(
            {
                "operation_id": "scene_info_after_project_execution",
                "operation_type": "get_scene_info",
                "payload": {},
                "rollback_on_failure": False,
            }
        )

    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "project_name": design_model.get("project_name"),
        "operation_count": len(operations),
        "skipped_count": len(skipped_instances),
        "skipped_instances": skipped_instances,
        "bridge_operations": operations,
        "design_model": design_model,
    }


def cleanup_operation(
    *,
    layer_names: list[str] | None = None,
    tag: str | None = None,
    clean_scope: str = "managed",
) -> dict[str, Any]:
    """Build a bridge cleanup operation for managed SketchUp entities."""
    if clean_scope not in {"managed", "all"}:
        raise ValueError("clean_scope must be 'managed' or 'all'.")
    return {
        "operation_id": "cleanup_before_project_execution",
        "operation_type": "cleanup_model",
        "payload": {
            "layer_names": (
                None if clean_scope == "all" else (layer_names or DEFAULT_CLEAN_LAYERS)
            ),
            "tag": tag,
            "all_entities": clean_scope == "all",
        },
        "rollback_on_failure": True,
    }


def execute_project_cleanup(
    *,
    layer_names: list[str] | None = None,
    tag: str | None = None,
    clean_scope: str = "managed",
    stop_on_error: bool = True,
    execute_fn: Callable[..., dict[str, Any]] = execute_bridge_operations,
) -> dict[str, Any]:
    """Clean managed SketchUp entities before replaying project truth."""
    return execute_fn(
        [
            cleanup_operation(
                layer_names=layer_names,
                tag=tag,
                clean_scope=clean_scope,
            )
        ],
        stop_on_error=stop_on_error,
    )


def execute_project_execution_plan(
    project_path: str | Path,
    *,
    stop_on_error: bool = True,
    allow_partial: bool = False,
    clean_before_execute: bool = False,
    clean_layer_names: list[str] | None = None,
    clean_tag: str | None = None,
    clean_scope: str = "managed",
    include_spaces: bool = True,
    include_walls: bool = True,
    include_openings: bool = True,
    include_components: bool = True,
    include_lighting: bool = True,
    include_scene_info: bool = True,
    execute_fn: Callable[..., dict[str, Any]] = execute_bridge_operations,
) -> dict[str, Any]:
    """Execute the current project truth and sync successful bridge feedback."""
    plan = build_project_execution_plan(
        project_path,
        include_spaces=include_spaces,
        include_walls=include_walls,
        include_openings=include_openings,
        include_components=include_components,
        include_lighting=include_lighting,
        include_scene_info=include_scene_info,
    )
    if plan["skipped_instances"] and not allow_partial:
        return {
            **plan,
            "status": "not_executed",
            "reason": (
                "Project execution plan has skipped instances. Pass "
                "allow_partial=True to execute only planned operations."
            ),
        }

    if clean_before_execute:
        cleanup_report = execute_project_cleanup(
            layer_names=clean_layer_names,
            tag=clean_tag,
            clean_scope=clean_scope,
            stop_on_error=True,
            execute_fn=execute_fn,
        )
        plan["pre_execution_cleanup"] = cleanup_report
        if cleanup_report.get("status") != "success":
            return {
                **plan,
                "status": "cleanup_failed",
                "reason": "Pre-execution cleanup failed; project truth was not replayed.",
            }

    execution_report = execute_fn(
        plan["bridge_operations"],
        stop_on_error=stop_on_error,
    )
    plan["execution_report"] = execution_report
    plan["status"] = execution_report.get("status")

    if execution_report.get("status") == "success":
        sync_report = sync_execution_report_to_design_model(
            plan["design_model"],
            execution_report,
        )
        plan["design_model"].setdefault("metadata", {})
        plan["design_model"]["metadata"]["execution_sync"] = {
            "status": "synced",
            "source": "execute_project_execution_plan",
            "updated_at": utc_now(),
            "operation_count": execution_report.get("executed_count", 0),
        }
        design_model_path = find_design_model_path(project_path)
        saved, save_errors = save_design_model(
            str(design_model_path),
            plan["design_model"],
        )
        sync_report["saved"] = saved
        sync_report["errors"] = save_errors
        plan["execution_sync"] = sync_report

    return plan
