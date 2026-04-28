"""Render brief generation from structured project truth."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_server.resources.design_model_schema import load_design_model
from mcp_server.resources.design_rules_schema import effective_design_rules
from mcp_server.resources.project_files import (
    DESIGN_MODEL_FILENAME,
    find_design_model_path,
    snapshot_manifest_path,
)
from mcp_server.resources.snapshot_manifest_schema import load_snapshot_manifest


def _dimensions_from_bounds(bounds: dict[str, Any]) -> dict[str, float] | None:
    """Return width/depth/height from min/max bounds."""
    minimum = bounds.get("min")
    maximum = bounds.get("max")
    if not isinstance(minimum, list) or not isinstance(maximum, list):
        return None
    if len(minimum) != 3 or len(maximum) != 3:
        return None
    return {
        "width": float(maximum[0]) - float(minimum[0]),
        "depth": float(maximum[1]) - float(minimum[1]),
        "height": float(maximum[2]) - float(minimum[2]),
    }


def _format_vector(value: Any) -> str:
    """Return a compact coordinate vector for prompt text."""
    if not isinstance(value, list):
        return "unknown"
    return "[" + ", ".join(str(round(float(item), 2)) for item in value) + "]"


def _format_dimensions(dimensions: dict[str, Any] | None) -> str:
    """Return compact millimeter dimensions for prompt text."""
    if not dimensions:
        return "unknown size"
    width = dimensions.get("width")
    depth = dimensions.get("depth")
    height = dimensions.get("height")
    return f"{width}w x {depth}d x {height}h mm"


def _space_summaries(design_model: dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact structured space summaries."""
    summaries = []
    for space_id, space in sorted(design_model.get("spaces", {}).items()):
        bounds = space.get("bounds", {}) if isinstance(space, dict) else {}
        summaries.append(
            {
                "id": space_id,
                "type": space.get("type", "other") if isinstance(space, dict) else "other",
                "dimensions": _dimensions_from_bounds(bounds) or {},
                "center": space.get("center") if isinstance(space, dict) else None,
            }
        )
    return summaries


def _component_summaries(design_model: dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact structured component summaries."""
    summaries = []
    for instance_id, component in sorted(design_model.get("components", {}).items()):
        if not isinstance(component, dict):
            continue
        summaries.append(
            {
                "id": instance_id,
                "name": component.get("name"),
                "type": component.get("type"),
                "component_ref": component.get("component_ref"),
                "position": component.get("position"),
                "dimensions": component.get("dimensions", {}),
                "rotation": component.get("rotation", 0),
                "layer": component.get("layer"),
            }
        )
    return summaries


def _lighting_summaries(design_model: dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact structured lighting summaries."""
    summaries = []
    for lighting_id, lighting in sorted(design_model.get("lighting", {}).items()):
        if not isinstance(lighting, dict):
            continue
        summaries.append(
            {
                "id": lighting_id,
                "type": lighting.get("type"),
                "component_ref": lighting.get("component_ref"),
                "position": lighting.get("position"),
            }
        )
    return summaries


def _latest_or_requested_snapshot(
    project_path: Path,
    source_snapshot_id: str | None,
    source_snapshot_file: str | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return the requested or latest snapshot manifest entry."""
    warnings: list[str] = []
    manifest_file = snapshot_manifest_path(project_path)

    if source_snapshot_file and not source_snapshot_id:
        return {"file": source_snapshot_file}, warnings

    if not manifest_file.exists():
        if source_snapshot_id:
            warnings.append(f"Snapshot manifest not found for {source_snapshot_id}.")
        return None, warnings

    manifest, errors = load_snapshot_manifest(manifest_file)
    if errors or manifest is None:
        warnings.extend(errors)
        return None, warnings

    snapshots = manifest.get("snapshots", [])
    if source_snapshot_id:
        for snapshot in snapshots:
            if snapshot.get("id") == source_snapshot_id:
                return snapshot, warnings
        warnings.append(f"Snapshot not found: {source_snapshot_id}")
        return None, warnings

    if source_snapshot_file:
        for snapshot in snapshots:
            if snapshot.get("file") == source_snapshot_file:
                return snapshot, warnings
        return {"file": source_snapshot_file}, warnings

    if snapshots:
        return snapshots[-1], warnings
    return None, warnings


def build_render_brief(
    project_path: str | Path,
    render_goal: str,
    *,
    style_intent: str | None = None,
    source_snapshot_id: str | None = None,
    source_snapshot_file: str | None = None,
    renderer_tool: str = "image_renderer",
    renderer_model: str | None = None,
    width: int = 1024,
    height: int = 1024,
) -> dict[str, Any]:
    """Build a renderer-ready prompt from project truth and snapshot provenance."""
    if width <= 0 or height <= 0:
        raise ValueError("render brief width and height must be positive.")

    root = Path(project_path).expanduser().resolve()
    model_path = find_design_model_path(root)
    design_model, model_errors = load_design_model(model_path)
    if model_errors or design_model is None:
        raise ValueError("; ".join(model_errors))

    spaces = _space_summaries(design_model)
    components = _component_summaries(design_model)
    lighting = _lighting_summaries(design_model)
    snapshot, warnings = _latest_or_requested_snapshot(
        root,
        source_snapshot_id,
        source_snapshot_file,
    )

    effective_rules, rule_errors = effective_design_rules(root)
    if rule_errors:
        warnings.extend(rule_errors)
    preferences = effective_rules.get("preferences", {}) if effective_rules else {}
    metadata = design_model.get("metadata", {})

    prompt_lines = [
        "Create an advisory interior render from SketchUp Agent Harness project truth.",
        f"Render goal: {render_goal}",
        "Preserve the model geometry, fixture positions, proportions, openings, and clearances.",
        f"Source model: {DESIGN_MODEL_FILENAME}. Units: millimeters.",
    ]
    if snapshot:
        prompt_lines.append(
            "Use the source snapshot as the camera/composition reference: "
            f"{snapshot.get('id', 'snapshot')} ({snapshot.get('file')})."
        )
    else:
        prompt_lines.append(
            "No source snapshot is attached; use the structured model summary as layout truth."
        )
    if style_intent:
        prompt_lines.append(f"Style intent: {style_intent}")
    if metadata.get("style"):
        prompt_lines.append(f"Project style metadata: {metadata['style']}")
    if preferences:
        prompt_lines.append(f"Designer preferences: {preferences}")

    prompt_lines.append("Spaces:")
    for space in spaces:
        prompt_lines.append(
            "- "
            f"{space['id']}: {space['type']}, "
            f"{_format_dimensions(space.get('dimensions'))}, "
            f"center {_format_vector(space.get('center'))}"
        )

    prompt_lines.append("Components:")
    for component in components:
        prompt_lines.append(
            "- "
            f"{component['id']}: {component.get('name') or component.get('type')}, "
            f"ref {component.get('component_ref')}, "
            f"at {_format_vector(component.get('position'))}, "
            f"{_format_dimensions(component.get('dimensions'))}, "
            f"rotation {component.get('rotation', 0)} degrees"
        )

    if lighting:
        prompt_lines.append("Lighting:")
        for light in lighting:
            prompt_lines.append(
                "- "
                f"{light['id']}: {light.get('type')}, "
                f"ref {light.get('component_ref')}, "
                f"at {_format_vector(light.get('position'))}"
            )

    negative_prompt = (
        "Do not change the floor plan, move fixtures, invent extra doors or "
        "windows, alter dimensions, remove required clearances, or treat the "
        "render as construction truth."
    )

    prompt = "\n".join(prompt_lines)
    source_snapshot_id_value = snapshot.get("id") if snapshot else source_snapshot_id
    source_snapshot_file_value = snapshot.get("file") if snapshot else source_snapshot_file

    return {
        "project_path": str(root),
        "source_model": str(model_path),
        "advisory": True,
        "renderer": {
            "tool": renderer_tool,
            **({"model": renderer_model} if renderer_model else {}),
        },
        "dimensions": {
            "width": width,
            "height": height,
        },
        "source_snapshot": snapshot,
        "render_goal": render_goal,
        "style_intent": style_intent,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "record_render_artifact_hint": {
            "project_path": str(root),
            "artifact_path": "<path-or-url-returned-by-renderer>",
            "prompt": prompt,
            "renderer_tool": renderer_tool,
            "renderer_model": renderer_model,
            "source_snapshot_id": source_snapshot_id_value,
            "source_snapshot_file": source_snapshot_file_value,
            "width": width,
            "height": height,
        },
        "warnings": warnings,
    }
