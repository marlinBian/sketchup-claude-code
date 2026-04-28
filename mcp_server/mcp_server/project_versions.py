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
