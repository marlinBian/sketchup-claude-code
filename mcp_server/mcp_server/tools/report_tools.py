"""Design report generation tools."""

from pathlib import Path
from typing import Any

from mcp_server.project_state import read_project_state


def generate_project_report(
    project_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Generate an English-first Markdown report for one design project."""
    root = Path(project_path).expanduser().resolve()
    state = read_project_state(root)
    report_path = (
        Path(output_path).expanduser().resolve()
        if output_path
        else root / "reports" / "design_report.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_project_report(state)
    report_path.write_text(report, encoding="utf-8")

    return {
        "project_path": str(root),
        "report_path": str(report_path),
        "space_count": len(state["design_model"].get("spaces", {})),
        "component_count": len(state["design_model"].get("components", {})),
        "lighting_count": len(state["design_model"].get("lighting", {})),
        "asset_count": state.get("assets_lock", {}).get("asset_count", 0),
        "snapshot_count": state.get("visual_feedback", {}).get("snapshot_count", 0),
        "pending_visual_action_count": state.get("visual_feedback", {}).get(
            "pending_action_count",
            0,
        ),
    }


def generate_design_report(
    project_name: str,
    project_dir: str = "./designs",
    output_format: str = "markdown",
) -> dict[str, Any]:
    """Backward-compatible wrapper around project workspace report generation."""
    if output_format != "markdown":
        raise ValueError("Only markdown reports are currently supported.")
    return generate_project_report(Path(project_dir).expanduser() / project_name)


def build_project_report(state: dict[str, Any]) -> str:
    """Build a Markdown report from project state."""
    design_model = state["design_model"]
    metadata = design_model.get("metadata", {})
    validation = design_model.get("validation", {})
    assets = state.get("assets_lock", {})
    visual_feedback = state.get("visual_feedback", {})
    design_rules = state.get("design_rules", {})

    lines = [
        f"# {design_model.get('project_name', 'SketchUp Design')} Design Report",
        "",
        "## Project Summary",
        "",
        f"- Project path: `{state['project_path']}`",
        f"- Source model: `{state['design_model_path']}`",
        f"- Units: {metadata.get('units', 'mm')}",
        f"- Style: {metadata.get('style', 'not specified')}",
        f"- Spaces: {len(design_model.get('spaces', {}))}",
        f"- Components: {len(design_model.get('components', {}))}",
        f"- Lighting items: {len(design_model.get('lighting', {}))}",
        "",
        "## Validation",
        "",
        f"- Valid: {validation.get('valid', 'not recorded')}",
    ]

    checks = validation.get("checks", [])
    if checks:
        lines.extend(["", "| Check | Valid | Actual | Required | Source |", "| --- | --- | ---: | ---: | --- |"])
        for check in checks:
            lines.append(
                "| {name} | {valid} | {actual} | {required} | {source} |".format(
                    name=check.get("name", ""),
                    valid=check.get("valid", ""),
                    actual=check.get("actual", ""),
                    required=check.get("required", ""),
                    source=check.get("source", ""),
                )
            )

    lines.extend(
        [
            "",
            "## Effective Design Rules",
            "",
            f"- Rules source: {design_rules.get('effective_source', 'not available')}",
            f"- Rule sets: {', '.join(design_rules.get('effective_rule_sets', [])) or 'none'}",
            f"- Preferences: {len(design_rules.get('effective_preferences', {}))}",
            "",
            "## Components",
            "",
        ]
    )

    components = design_model.get("components", {})
    if components:
        lines.extend(["| Instance | Component Ref | Layer | Position |", "| --- | --- | --- | --- |"])
        for instance_id, component in components.items():
            lines.append(
                "| {instance_id} | {component_ref} | {layer} | {position} |".format(
                    instance_id=instance_id,
                    component_ref=component.get("component_ref", ""),
                    layer=component.get("layer", ""),
                    position=component.get("position", []),
                )
            )
    else:
        lines.append("No component instances are recorded.")

    lines.extend(
        [
            "",
            "## Assets",
            "",
            f"- Assets: {assets.get('asset_count', 0)}",
            f"- Cached: {assets.get('cached_asset_count', 0)}",
            f"- Referenced: {assets.get('referenced_asset_count', 0)}",
            f"- Missing metadata: {assets.get('missing_asset_count', 0)}",
            "",
            "## Visual Review",
            "",
            f"- Snapshots: {visual_feedback.get('snapshot_count', 0)}",
            f"- Reviews: {visual_feedback.get('review_count', 0)}",
            f"- Pending actions: {visual_feedback.get('pending_action_count', 0)}",
            "",
            "## Notes",
            "",
            "This report is generated from structured project truth. Screenshots and "
            "visual feedback are advisory artifacts; `design_model.json` remains the "
            "source of truth.",
            "",
        ]
    )
    return "\n".join(lines)


async def generate_and_save_report(
    project_name: str,
    project_dir: str = "./designs",
) -> dict[str, Any]:
    """Async wrapper for report generation."""
    return generate_design_report(project_name, project_dir)
