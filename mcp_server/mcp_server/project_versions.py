"""Project version snapshot helpers."""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_server.resources.project_files import (
    assets_lock_path,
    design_rules_path,
    find_design_model_path,
    project_component_library_path,
    snapshot_manifest_path,
)

VERSION_TAG_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def utc_now() -> str:
    """Return an ISO8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def project_versions_path(project_path: str | Path) -> Path:
    """Return the project-local versions directory."""
    return Path(project_path).expanduser().resolve() / "versions"


def validate_version_tag(version_tag: str) -> None:
    """Raise ValueError when a version tag is unsafe for a directory name."""
    if not VERSION_TAG_PATTERN.match(version_tag):
        raise ValueError(
            "Version tag must contain only letters, numbers, dots, underscores, "
            "or hyphens."
        )


def _version_root(project_path: Path, version_tag: str) -> Path:
    """Return the root directory for a saved version or current project truth."""
    if version_tag == "current":
        return project_path
    validate_version_tag(version_tag)
    return project_versions_path(project_path) / version_tag


def version_source_files(project_path: Path) -> list[tuple[str, Path]]:
    """Return project truth files that should be copied into a version snapshot."""
    candidates = [
        ("design_model.json", find_design_model_path(project_path)),
        ("design_rules.json", design_rules_path(project_path)),
        ("assets.lock.json", assets_lock_path(project_path)),
        ("component_library.json", project_component_library_path(project_path)),
        ("snapshots/manifest.json", snapshot_manifest_path(project_path)),
    ]
    return [(relative_path, path) for relative_path, path in candidates if path.exists()]


def comparable_version_files() -> list[str]:
    """Return project truth files included in version comparison."""
    return [
        "design_model.json",
        "design_rules.json",
        "assets.lock.json",
        "component_library.json",
        "snapshots/manifest.json",
    ]


def save_project_version(
    project_path: str | Path,
    version_tag: str,
    description: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Save current structured project truth into versions/<version_tag>."""
    validate_version_tag(version_tag)
    root = Path(project_path).expanduser().resolve()
    version_path = project_versions_path(root) / version_tag
    if version_path.exists() and not overwrite:
        raise FileExistsError(f"Project version already exists: {version_tag}")
    version_path.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    for relative_path, source_path in version_source_files(root):
        target_path = version_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied_files.append(relative_path)

    metadata = {
        "version": version_tag,
        "created_at": utc_now(),
        "description": description,
        "source_project_path": str(root),
        "files": copied_files,
    }
    metadata_path = version_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "project_path": str(root),
        "version": version_tag,
        "version_path": str(version_path),
        "metadata_path": str(metadata_path),
        "files": copied_files,
    }


def list_project_versions(project_path: str | Path) -> dict[str, Any]:
    """List saved project truth snapshots."""
    root = Path(project_path).expanduser().resolve()
    versions_root = project_versions_path(root)
    versions: list[dict[str, Any]] = []
    if versions_root.exists():
        for version_path in sorted(path for path in versions_root.iterdir() if path.is_dir()):
            metadata_path = version_path / "metadata.json"
            item: dict[str, Any] = {
                "version": version_path.name,
                "version_path": str(version_path),
                "metadata_path": str(metadata_path),
            }
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    item.update(metadata)
                except json.JSONDecodeError:
                    item["metadata_error"] = "Invalid JSON"
            versions.append(item)

    return {
        "project_path": str(root),
        "versions_path": str(versions_root),
        "count": len(versions),
        "versions": versions,
    }


def _load_json_file(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load one JSON file for version comparison."""
    if not path.exists():
        return None, [f"File not found: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return None, [
            f"Invalid JSON in {path}: {error.msg} at line {error.lineno}, "
            f"column {error.colno}"
        ]
    if not isinstance(data, dict):
        return None, [f"JSON file must contain an object: {path}"]
    return data, []


def _collection_diff(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Return added, removed, and changed keys for two object maps."""
    base_keys = set(base.keys())
    head_keys = set(head.keys())
    shared = base_keys & head_keys
    changed = sorted(key for key in shared if base[key] != head[key])
    return {
        "added": sorted(head_keys - base_keys),
        "removed": sorted(base_keys - head_keys),
        "changed": changed,
        "unchanged_count": len(shared) - len(changed),
    }


def _design_model_diff(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Return design-model-specific version changes."""
    result: dict[str, Any] = {
        "project_name_changed": base.get("project_name") != head.get("project_name"),
        "spaces": _collection_diff(base.get("spaces", {}), head.get("spaces", {})),
        "components": _collection_diff(
            base.get("components", {}),
            head.get("components", {}),
        ),
        "lighting": _collection_diff(
            base.get("lighting", {}),
            head.get("lighting", {}),
        ),
    }
    base_style = base.get("metadata", {}).get("style")
    head_style = head.get("metadata", {}).get("style")
    if base_style != head_style:
        result["style"] = {"base": base_style, "head": head_style}
    return result


def _design_rules_diff(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Return design-rules-specific version changes."""
    return {
        "source_changed": base.get("source") != head.get("source"),
        "rule_sets": _collection_diff(
            base.get("rule_sets", {}),
            head.get("rule_sets", {}),
        ),
        "preferences": _collection_diff(
            base.get("preferences", {}),
            head.get("preferences", {}),
        ),
    }


def _assets_lock_diff(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Return asset-lock-specific version changes."""
    base_assets = {
        str(asset.get("component_id")): asset
        for asset in base.get("assets", [])
        if isinstance(asset, dict) and asset.get("component_id")
    }
    head_assets = {
        str(asset.get("component_id")): asset
        for asset in head.get("assets", [])
        if isinstance(asset, dict) and asset.get("component_id")
    }
    return {"assets": _collection_diff(base_assets, head_assets)}


def _component_library_diff(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Return project component-library changes."""
    return {
        "components": _collection_diff(
            base.get("components", {}),
            head.get("components", {}),
        )
    }


def _snapshot_manifest_diff(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Return visual manifest count changes."""
    return {
        "snapshots": {
            "base_count": len(base.get("snapshots", [])),
            "head_count": len(head.get("snapshots", [])),
        },
        "renders": {
            "base_count": len(base.get("renders", [])),
            "head_count": len(head.get("renders", [])),
        },
        "reviews": {
            "base_count": len(base.get("reviews", [])),
            "head_count": len(head.get("reviews", [])),
        },
    }


def _file_specific_diff(
    relative_path: str,
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Return domain-specific diff details for a project truth file."""
    if relative_path == "design_model.json":
        return _design_model_diff(base, head)
    if relative_path == "design_rules.json":
        return _design_rules_diff(base, head)
    if relative_path == "assets.lock.json":
        return _assets_lock_diff(base, head)
    if relative_path == "component_library.json":
        return _component_library_diff(base, head)
    if relative_path == "snapshots/manifest.json":
        return _snapshot_manifest_diff(base, head)
    return {"top_level": _collection_diff(base, head)}


def compare_project_versions(
    project_path: str | Path,
    base_version: str,
    head_version: str = "current",
) -> dict[str, Any]:
    """Compare saved project truth versions or a saved version to current truth."""
    root = Path(project_path).expanduser().resolve()
    base_root = _version_root(root, base_version)
    head_root = _version_root(root, head_version)
    if base_version != "current" and not base_root.is_dir():
        raise FileNotFoundError(f"Project version not found: {base_version}")
    if head_version != "current" and not head_root.is_dir():
        raise FileNotFoundError(f"Project version not found: {head_version}")

    files: dict[str, Any] = {}
    changed_files: list[str] = []
    errors: list[str] = []
    for relative_path in comparable_version_files():
        base_path = base_root / relative_path
        head_path = head_root / relative_path
        base_exists = base_path.exists()
        head_exists = head_path.exists()
        if not base_exists and not head_exists:
            continue
        if base_exists and not head_exists:
            files[relative_path] = {"status": "removed"}
            changed_files.append(relative_path)
            continue
        if head_exists and not base_exists:
            files[relative_path] = {"status": "added"}
            changed_files.append(relative_path)
            continue

        base_data, base_errors = _load_json_file(base_path)
        head_data, head_errors = _load_json_file(head_path)
        if base_errors or head_errors or base_data is None or head_data is None:
            file_errors = base_errors + head_errors
            files[relative_path] = {"status": "error", "errors": file_errors}
            errors.extend(file_errors)
            changed_files.append(relative_path)
            continue

        if base_data == head_data:
            files[relative_path] = {"status": "unchanged"}
            continue

        files[relative_path] = {
            "status": "changed",
            "details": _file_specific_diff(relative_path, base_data, head_data),
        }
        changed_files.append(relative_path)

    return {
        "project_path": str(root),
        "base_version": base_version,
        "head_version": head_version,
        "base_path": str(base_root),
        "head_path": str(head_root),
        "changed": bool(changed_files),
        "changed_files": changed_files,
        "files": files,
        "errors": errors,
    }


def restore_project_version(
    project_path: str | Path,
    version_tag: str,
    overwrite_current: bool = False,
) -> dict[str, Any]:
    """Restore a structured project truth snapshot into the project workspace."""
    validate_version_tag(version_tag)
    if not overwrite_current:
        raise ValueError("Restoring a version requires overwrite_current=True.")

    root = Path(project_path).expanduser().resolve()
    version_path = project_versions_path(root) / version_tag
    metadata_path = version_path / "metadata.json"
    if not version_path.is_dir():
        raise FileNotFoundError(f"Project version not found: {version_tag}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Project version metadata not found: {metadata_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    files = [
        str(path)
        for path in metadata.get("files", [])
        if isinstance(path, str)
    ]
    restored_files: list[str] = []
    for relative_path in files:
        source_path = version_path / relative_path
        if not source_path.exists():
            continue
        target_path = root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        restored_files.append(relative_path)

    return {
        "project_path": str(root),
        "version": version_tag,
        "version_path": str(version_path),
        "restored_files": restored_files,
    }
