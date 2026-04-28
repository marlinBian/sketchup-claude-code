"""Project layout validation helpers for component placement."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_server.resources.design_model_schema import load_design_model
from mcp_server.resources.project_files import find_design_model_path


def normalize_bounds(
    bounds: dict[str, Any],
    label: str,
) -> tuple[dict[str, list[float]] | None, list[str]]:
    """Return normalized 3D bounds or validation errors."""
    minimum = bounds.get("min")
    maximum = bounds.get("max")
    if not isinstance(minimum, list) or not isinstance(maximum, list):
        return None, [f"{label} bounds must include min and max lists."]
    if len(minimum) != 3 or len(maximum) != 3:
        return None, [f"{label} bounds min and max must be 3D points."]

    normalized = {
        "min": [float(minimum[0]), float(minimum[1]), float(minimum[2])],
        "max": [float(maximum[0]), float(maximum[1]), float(maximum[2])],
    }
    if any(normalized["max"][idx] <= normalized["min"][idx] for idx in range(3)):
        return None, [f"{label} bounds must have positive extents."]
    return normalized, []


def bounds_inside(
    inner: dict[str, list[float]],
    outer: dict[str, list[float]],
    *,
    tolerance: float = 0.001,
) -> list[str]:
    """Return errors when inner bounds exceed outer bounds."""
    errors: list[str] = []
    axes = ("x", "y", "z")
    for idx, axis in enumerate(axes):
        if inner["min"][idx] < outer["min"][idx] - tolerance:
            errors.append(
                f"min_{axis} {inner['min'][idx]} is outside space minimum "
                f"{outer['min'][idx]}"
            )
        if inner["max"][idx] > outer["max"][idx] + tolerance:
            errors.append(
                f"max_{axis} {inner['max'][idx]} is outside space maximum "
                f"{outer['max'][idx]}"
            )
    return errors


def overlap_3d(
    first: dict[str, list[float]],
    second: dict[str, list[float]],
    *,
    tolerance: float = 0.001,
) -> dict[str, float] | None:
    """Return 3D overlap extents, or None when boxes do not overlap."""
    overlap = {
        axis: min(first["max"][idx], second["max"][idx])
        - max(first["min"][idx], second["min"][idx])
        for idx, axis in enumerate(("x", "y", "z"))
    }
    if all(value > tolerance for value in overlap.values()):
        return overlap
    return None


def component_wall_side(component: dict[str, Any]) -> str | None:
    """Return semantic wall side provenance for a component instance."""
    source = component.get("source", {})
    if not isinstance(source, dict):
        return None
    semantic = source.get("semantic_placement", {})
    if not isinstance(semantic, dict):
        return None
    wall_side = semantic.get("wall_side")
    if wall_side in {"north", "south", "east", "west"}:
        return str(wall_side)
    return None


def explicit_component_space(
    component: dict[str, Any],
    spaces: dict[str, Any],
) -> str | None:
    """Return explicit component space provenance when present."""
    relative_to = component.get("relative_to")
    if isinstance(relative_to, str) and relative_to in spaces:
        return relative_to

    source = component.get("source", {})
    if not isinstance(source, dict):
        return None
    semantic = source.get("semantic_placement", {})
    if not isinstance(semantic, dict):
        return None
    space_id = semantic.get("space_id")
    if isinstance(space_id, str) and space_id in spaces:
        return space_id
    return None


def infer_component_space(
    component_bounds: dict[str, list[float]],
    spaces: dict[str, dict[str, list[float]]],
) -> str | None:
    """Infer a component space when exactly one space contains its bounds."""
    matches = [
        space_id
        for space_id, bounds in spaces.items()
        if not bounds_inside(component_bounds, bounds)
    ]
    return matches[0] if len(matches) == 1 else None


def front_clearance_available(
    component_bounds: dict[str, list[float]],
    space_bounds: dict[str, list[float]],
    wall_side: str,
) -> float:
    """Return available front clearance for a wall-backed component."""
    if wall_side == "north":
        return component_bounds["min"][1] - space_bounds["min"][1]
    if wall_side == "south":
        return space_bounds["max"][1] - component_bounds["max"][1]
    if wall_side == "east":
        return component_bounds["min"][0] - space_bounds["min"][0]
    return space_bounds["max"][0] - component_bounds["max"][0]


def normalized_spaces(
    design_model: dict[str, Any],
) -> tuple[dict[str, dict[str, list[float]]], list[dict[str, Any]]]:
    """Return normalized project spaces and validation checks."""
    spaces: dict[str, dict[str, list[float]]] = {}
    checks: list[dict[str, Any]] = []
    for space_id, space in design_model.get("spaces", {}).items():
        if not isinstance(space, dict) or not isinstance(space.get("bounds"), dict):
            checks.append(
                {
                    "name": "space_bounds",
                    "valid": False,
                    "space_id": space_id,
                    "errors": [f"space bounds missing: {space_id}"],
                }
            )
            continue
        bounds, errors = normalize_bounds(space["bounds"], f"space {space_id}")
        checks.append(
            {
                "name": "space_bounds",
                "valid": not errors,
                "space_id": space_id,
                "errors": errors,
            }
        )
        if bounds is not None:
            spaces[space_id] = bounds
    return spaces, checks


def normalized_components(
    design_model: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Return normalized component instances and validation checks."""
    components: dict[str, dict[str, Any]] = {}
    checks: list[dict[str, Any]] = []
    for instance_id, component in design_model.get("components", {}).items():
        if not isinstance(component, dict) or not isinstance(component.get("bounds"), dict):
            checks.append(
                {
                    "name": "component_bounds",
                    "valid": False,
                    "instance_id": instance_id,
                    "errors": [f"component bounds missing: {instance_id}"],
                }
            )
            continue
        bounds, errors = normalize_bounds(
            component["bounds"],
            f"component {instance_id}",
        )
        checks.append(
            {
                "name": "component_bounds",
                "valid": not errors,
                "instance_id": instance_id,
                "errors": errors,
            }
        )
        if bounds is not None:
            components[instance_id] = {
                "instance": component,
                "bounds": bounds,
            }
    return components, checks


def validate_layout_model(design_model: dict[str, Any]) -> dict[str, Any]:
    """Validate component containment, physical overlap, and simple clearances."""
    spaces, space_checks = normalized_spaces(design_model)
    components, component_checks = normalized_components(design_model)
    checks = [*space_checks, *component_checks]
    component_spaces: dict[str, str | None] = {}

    for instance_id, payload in components.items():
        component = payload["instance"]
        bounds = payload["bounds"]
        space_id = explicit_component_space(component, design_model.get("spaces", {}))
        if space_id is None:
            space_id = infer_component_space(bounds, spaces)
        component_spaces[instance_id] = space_id

        if space_id is None:
            checks.append(
                {
                    "name": "component_space",
                    "valid": True,
                    "instance_id": instance_id,
                    "status": "not_linked",
                }
            )
            continue

        containment_errors = bounds_inside(bounds, spaces[space_id])
        checks.append(
            {
                "name": "component_containment",
                "valid": not containment_errors,
                "instance_id": instance_id,
                "space_id": space_id,
                "errors": containment_errors,
            }
        )

        clearance = component.get("clearance", {})
        required_front = (
            clearance.get("front") if isinstance(clearance, dict) else None
        )
        wall_side = component_wall_side(component)
        if isinstance(required_front, (int, float)) and wall_side is not None:
            available = front_clearance_available(bounds, spaces[space_id], wall_side)
            checks.append(
                {
                    "name": "front_clearance",
                    "valid": available >= float(required_front),
                    "instance_id": instance_id,
                    "space_id": space_id,
                    "wall_side": wall_side,
                    "available": available,
                    "required": float(required_front),
                    "units": "mm",
                }
            )

    instance_ids = sorted(components.keys())
    for index, first_id in enumerate(instance_ids):
        first_space = component_spaces.get(first_id)
        if first_space is None:
            continue
        for second_id in instance_ids[index + 1 :]:
            if component_spaces.get(second_id) != first_space:
                continue
            overlap = overlap_3d(
                components[first_id]["bounds"],
                components[second_id]["bounds"],
            )
            if overlap is None:
                continue
            checks.append(
                {
                    "name": "component_overlap",
                    "valid": False,
                    "space_id": first_space,
                    "instances": [first_id, second_id],
                    "overlap": overlap,
                    "units": "mm",
                }
            )

    return {
        "ok": all(check.get("valid", False) for check in checks),
        "checked": len(checks),
        "failed_count": sum(1 for check in checks if not check.get("valid", False)),
        "component_spaces": component_spaces,
        "checks": checks,
    }


def validate_project_layout(project_path: str | Path) -> dict[str, Any]:
    """Validate layout checks for a project design model file."""
    root = Path(project_path).expanduser().resolve()
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        return {
            "project_path": str(root),
            "ok": False,
            "errors": errors,
            "checks": [],
        }

    result = validate_layout_model(design_model)
    result.update(
        {
            "project_path": str(root),
            "design_model_path": str(design_model_path),
        }
    )
    return result
