"""Project asset lock maintenance helpers."""

import json
from pathlib import Path
from typing import Any

from mcp_server.resources.asset_lock_schema import build_assets_lock
from mcp_server.resources.design_model_schema import load_design_model
from mcp_server.resources.project_files import assets_lock_path, find_design_model_path
from mcp_server.tools.local_library_search import load_effective_library


def asset_lock_counts(assets_lock: dict[str, Any]) -> dict[str, int]:
    """Return cache status counts for an asset lock."""
    assets = assets_lock.get("assets", [])
    return {
        "asset_count": len(assets),
        "cached_asset_count": sum(
            1 for asset in assets if asset.get("cache", {}).get("status") == "cached"
        ),
        "referenced_asset_count": sum(
            1
            for asset in assets
            if asset.get("cache", {}).get("status") == "referenced"
        ),
        "missing_asset_count": sum(
            1 for asset in assets if asset.get("cache", {}).get("status") == "missing"
        ),
    }


def refresh_project_asset_lock(project_path: str | Path) -> dict[str, Any]:
    """Regenerate assets.lock.json from design truth and effective components."""
    root = Path(project_path).expanduser().resolve()
    design_model_path = find_design_model_path(root)
    design_model, model_errors = load_design_model(str(design_model_path))
    if model_errors or design_model is None:
        raise ValueError("; ".join(model_errors))

    library, library_errors = load_effective_library(root)
    if library_errors:
        raise ValueError("; ".join(library_errors))

    lock = build_assets_lock(design_model, library, project_path=root)
    lock_path = assets_lock_path(root)
    lock_path.write_text(
        json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "assets_lock_path": str(lock_path),
        **asset_lock_counts(lock),
        "assets_lock": lock,
    }
