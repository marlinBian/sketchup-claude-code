"""Designer project initialization helpers."""

import json
from pathlib import Path
from typing import Any

from mcp_server.resources.asset_lock_schema import create_empty_assets_lock
from mcp_server.resources.design_model_schema import create_empty_template
from mcp_server.resources.design_rules_schema import create_default_design_rules
from mcp_server.resources.project_files import (
    ASSETS_CACHE_DIR,
    ASSETS_LOCK_FILENAME,
    DESIGN_MODEL_FILENAME,
    DESIGN_RULES_FILENAME,
    assets_cache_path,
    snapshot_manifest_path,
    snapshots_path,
)
from mcp_server.resources.snapshot_manifest_schema import create_empty_snapshot_manifest
from mcp_server.tools.bathroom_planner import plan_bathroom_project, save_bathroom_plan

PROJECT_MCP_FILENAME = ".mcp.json"


def write_json(path: Path, data: dict[str, Any], overwrite: bool) -> None:
    """Write a JSON file unless it exists and overwrite is disabled."""
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_assets_lock() -> dict[str, Any]:
    """Return an empty assets lock file."""
    return create_empty_assets_lock(cache_root=ASSETS_CACHE_DIR)


def default_project_mcp_config() -> dict[str, Any]:
    """Return a project-local MCP config for installed package usage."""
    return {
        "mcpServers": {
            "sketchup-mcp": {
                "command": "python3",
                "args": ["-m", "mcp_server.server"],
            }
        }
    }


def init_project(
    project_path: str | Path,
    project_name: str | None = None,
    template: str = "empty",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Initialize a designer project directory."""
    root = Path(project_path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    name = project_name or root.name
    if template not in {"empty", "bathroom"}:
        raise ValueError("template must be 'empty' or 'bathroom'")

    if template == "bathroom":
        if not overwrite:
            for filename in (DESIGN_MODEL_FILENAME, DESIGN_RULES_FILENAME):
                path = root / filename
                if path.exists():
                    raise FileExistsError(f"Refusing to overwrite existing file: {path}")
        plan = plan_bathroom_project(project_name=name)
        written = save_bathroom_plan(root, plan)
        design_model_path = Path(written["design_model_path"])
        design_rules_path = Path(written["design_rules_path"])
        assets_lock = None
    else:
        design_model_path = root / DESIGN_MODEL_FILENAME
        design_rules_path = root / DESIGN_RULES_FILENAME
        write_json(design_model_path, create_empty_template(name), overwrite)
        write_json(design_rules_path, create_default_design_rules(), overwrite)
        assets_lock = default_assets_lock()

    assets_lock_path = root / ASSETS_LOCK_FILENAME
    mcp_config_path = root / PROJECT_MCP_FILENAME
    assets_cache = assets_cache_path(root)
    snapshots_dir = snapshots_path(root)
    snapshot_manifest = snapshot_manifest_path(root)
    assets_cache.mkdir(parents=True, exist_ok=True)
    snapshots_dir.mkdir(exist_ok=True)

    if assets_lock is not None:
        write_json(assets_lock_path, assets_lock, overwrite)
    if not snapshot_manifest.exists() or overwrite:
        write_json(snapshot_manifest, create_empty_snapshot_manifest(), overwrite)
    write_json(mcp_config_path, default_project_mcp_config(), overwrite)

    return {
        "project_path": str(root),
        "project_name": name,
        "template": template,
        "files": {
            "design_model": str(design_model_path),
            "design_rules": str(design_rules_path),
            "assets_lock": str(assets_lock_path),
            "assets_cache": str(assets_cache),
            "mcp_config": str(mcp_config_path),
            "snapshots": str(snapshots_dir),
            "snapshot_manifest": str(snapshot_manifest),
        },
    }
