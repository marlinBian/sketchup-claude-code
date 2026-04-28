"""Build bridge execution traces from project design_model.json truth."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_server.resources.design_model_schema import load_design_model
from mcp_server.resources.project_files import find_design_model_path
from mcp_server.tools import placement_tools
from mcp_server.tools.local_library_search import (
    get_component_by_id,
    load_effective_library,
)


DEFAULT_WALL_THICKNESS = 100.0


def _xyz(value: Any, field_name: str) -> list[float]:
    """Return a three-number coordinate list."""
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{field_name} must be a three-number list.")
    return [float(value[0]), float(value[1]), float(value[2])]


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


def build_project_execution_plan(
    project_path: str | Path,
    *,
    include_spaces: bool = True,
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

    if include_spaces:
        for space_id in sorted(design_model.get("spaces", {})):
            space = design_model["spaces"][space_id]
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
