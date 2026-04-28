"""Canonical project file names and lookup helpers."""

from pathlib import Path

DESIGN_MODEL_FILENAME = "design_model.json"
LEGACY_DESIGN_MODEL_FILENAME = ".design_model.json"
DESIGN_RULES_FILENAME = "design_rules.json"
ASSETS_LOCK_FILENAME = "assets.lock.json"
ASSETS_CACHE_DIR = "assets/components"
SNAPSHOTS_DIR = "snapshots"
SNAPSHOT_MANIFEST_FILENAME = "manifest.json"


def find_design_model_path(project_path: str | Path) -> Path:
    """Return the canonical design model path, falling back to legacy hidden file.

    New projects must use ``design_model.json``. The hidden
    ``.design_model.json`` name remains readable during the migration window so
    existing demo projects do not break.
    """
    root = Path(project_path)
    canonical_path = root / DESIGN_MODEL_FILENAME
    if canonical_path.exists():
        return canonical_path

    legacy_path = root / LEGACY_DESIGN_MODEL_FILENAME
    if legacy_path.exists():
        return legacy_path

    return canonical_path


def design_rules_path(project_path: str | Path) -> Path:
    """Return the project-local design rules path."""
    return Path(project_path) / DESIGN_RULES_FILENAME


def assets_lock_path(project_path: str | Path) -> Path:
    """Return the project-local asset lock path."""
    return Path(project_path) / ASSETS_LOCK_FILENAME


def assets_cache_path(project_path: str | Path) -> Path:
    """Return the project-local component asset cache path."""
    return Path(project_path) / ASSETS_CACHE_DIR


def snapshots_path(project_path: str | Path) -> Path:
    """Return the project-local snapshots directory path."""
    return Path(project_path) / SNAPSHOTS_DIR


def snapshot_manifest_path(project_path: str | Path) -> Path:
    """Return the project-local snapshot manifest path."""
    return snapshots_path(project_path) / SNAPSHOT_MANIFEST_FILENAME
