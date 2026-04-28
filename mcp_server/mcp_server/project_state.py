"""Shared project state inspection helpers."""

from pathlib import Path
from typing import Any

from mcp_server.project_assets import asset_lock_counts
from mcp_server.resources.asset_lock_schema import load_assets_lock
from mcp_server.resources.design_model_schema import load_design_model
from mcp_server.resources.design_rules_schema import (
    designer_profile_path_from_env,
    effective_design_rules,
    load_design_rules,
)
from mcp_server.resources.project_files import (
    assets_lock_path,
    design_rules_path,
    find_design_model_path,
    snapshot_manifest_path,
)
from mcp_server.resources.snapshot_manifest_schema import load_snapshot_manifest


def summarize_design_rules(project_path: str | Path) -> dict[str, Any]:
    """Return project and effective design-rule state for agent inspection."""
    path = design_rules_path(project_path)
    profile_path = designer_profile_path_from_env()
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "valid": False,
        "profile_path": str(profile_path) if profile_path else None,
        "effective_valid": False,
        "effective_rules": None,
    }

    project_errors: list[str] = []
    if path.exists():
        project_rules, project_errors = load_design_rules(path)
        if project_errors or project_rules is None:
            summary["errors"] = project_errors
        else:
            summary.update(
                {
                    "valid": True,
                    "source": project_rules.get("source"),
                    "units": project_rules.get("units"),
                    "rule_sets": sorted(project_rules.get("rule_sets", {}).keys()),
                    "preferences": project_rules.get("preferences", {}),
                    "project_rules": project_rules,
                }
            )
    else:
        project_errors = [f"File not found: {path}"]
        summary["errors"] = project_errors

    effective_rules, effective_errors = effective_design_rules(project_path)
    if effective_errors or effective_rules is None:
        summary["effective_errors"] = effective_errors
        return summary

    summary.update(
        {
            "effective_valid": True,
            "effective_source": effective_rules.get("source"),
            "effective_rule_sets": sorted(effective_rules.get("rule_sets", {}).keys()),
            "effective_preferences": effective_rules.get("preferences", {}),
            "effective_rules": effective_rules,
        }
    )
    return summary


def summarize_assets_lock(project_path: str | Path) -> dict[str, Any]:
    """Return a compact asset-lock summary for project state inspection."""
    path = assets_lock_path(project_path)
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "valid": False,
        "asset_count": 0,
        "cached_asset_count": 0,
        "referenced_asset_count": 0,
        "missing_asset_count": 0,
        "assets": [],
    }
    if not path.exists():
        summary["errors"] = [f"File not found: {path}"]
        return summary

    assets_lock, errors = load_assets_lock(path)
    if errors or assets_lock is None:
        summary["errors"] = errors
        return summary

    assets = assets_lock.get("assets", [])
    compact_assets = [
        {
            "component_id": asset.get("component_id"),
            "component_name": asset.get("component_name"),
            "category": asset.get("category"),
            "used_by": asset.get("used_by", []),
            "source": asset.get("source", {}),
            "cache": asset.get("cache", {}),
        }
        for asset in assets
    ]
    summary.update(
        {
            "valid": True,
            **asset_lock_counts(assets_lock),
            "assets": compact_assets,
        }
    )
    return summary


def summarize_snapshot_manifest(project_path: str | Path) -> dict[str, Any]:
    """Return a compact visual review summary for project state inspection."""
    path = snapshot_manifest_path(project_path)
    summary: dict[str, Any] = {
        "manifest_path": str(path),
        "exists": path.exists(),
        "valid": False,
        "snapshot_count": 0,
        "review_count": 0,
        "action_count": 0,
        "pending_action_count": 0,
        "accepted_action_count": 0,
        "applied_action_count": 0,
        "pending_actions": [],
    }
    if not path.exists():
        summary["errors"] = [f"File not found: {path}"]
        return summary

    manifest, errors = load_snapshot_manifest(path)
    if errors or manifest is None:
        summary["errors"] = errors
        return summary

    snapshots = manifest.get("snapshots", [])
    reviews = manifest.get("reviews", [])
    pending_actions: list[dict[str, Any]] = []
    accepted_count = 0
    applied_count = 0
    action_count = 0
    for review in reviews:
        for action_index, action in enumerate(review.get("actions", [])):
            action_count += 1
            status = action.get("status")
            if status == "accepted":
                accepted_count += 1
            if status == "applied":
                applied_count += 1
            if status in {"proposed", "accepted"}:
                pending_actions.append(
                    {
                        "review_id": review.get("id"),
                        "action_index": action_index,
                        "type": action.get("type"),
                        "target": action.get("target"),
                        "intent": action.get("intent"),
                        "status": status,
                        "payload": action.get("payload", {}),
                        "rationale": action.get("rationale"),
                    }
                )

    latest_snapshot = None
    if snapshots:
        latest = snapshots[-1]
        latest_snapshot = {
            "id": latest.get("id"),
            "file": latest.get("file"),
            "created_at": latest.get("created_at"),
        }

    summary.update(
        {
            "valid": True,
            "snapshot_count": len(snapshots),
            "review_count": len(reviews),
            "action_count": action_count,
            "pending_action_count": len(pending_actions),
            "accepted_action_count": accepted_count,
            "applied_action_count": applied_count,
            "pending_actions": pending_actions,
            "latest_snapshot": latest_snapshot,
        }
    )
    return summary


def read_project_state(
    project_path: str | Path,
    include_rules: bool = True,
    include_assets: bool = True,
    include_visual_feedback: bool = True,
) -> dict[str, Any]:
    """Read design_model.json plus optional supporting project summaries."""
    resolved_project_path = Path(project_path).expanduser().resolve()
    model_path = find_design_model_path(resolved_project_path)
    design_model, errors = load_design_model(str(model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))

    state: dict[str, Any] = {
        "project_path": str(resolved_project_path),
        "design_model_path": str(model_path),
        "project_files": {
            "design_model_path": str(model_path),
            "design_rules_path": str(design_rules_path(resolved_project_path)),
            "assets_lock_path": str(assets_lock_path(resolved_project_path)),
            "snapshot_manifest_path": str(
                snapshot_manifest_path(resolved_project_path)
            ),
        },
        "design_model": design_model,
    }
    if include_rules:
        state["design_rules"] = summarize_design_rules(resolved_project_path)
    if include_assets:
        state["assets_lock"] = summarize_assets_lock(resolved_project_path)
    if include_visual_feedback:
        state["visual_feedback"] = summarize_snapshot_manifest(resolved_project_path)
    return state
