"""SketchUp Ruby bridge installation helpers."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IGNORED_BRIDGE_PATTERNS = (
    ".bundle",
    "vendor",
    "*.gem",
    "*.log",
    ".DS_Store",
)


def repo_root_from_package() -> Path:
    """Return the source checkout root when running from this repository."""
    return Path(__file__).resolve().parents[2]


def default_bridge_source() -> Path:
    """Return the default bridge source directory."""
    return repo_root_from_package() / "su_bridge"


def installed_sketchup_plugin_dirs(home: str | Path | None = None) -> list[Path]:
    """Return detected macOS SketchUp plugin directories, newest first."""
    root = (
        Path(home).expanduser()
        if home is not None
        else Path.home()
    ) / "Library" / "Application Support" / "SketchUp"
    if not root.exists():
        return []

    candidates: list[Path] = []
    for app_dir in root.glob("SketchUp *"):
        plugins_dir = app_dir / "SketchUp" / "Plugins"
        if plugins_dir.exists():
            candidates.append(plugins_dir)

    return sorted(candidates, key=lambda path: path.parent.parent.name, reverse=True)


def default_plugins_dir(
    sketchup_version: str | None = None,
    home: str | Path | None = None,
) -> Path:
    """Return the target SketchUp Plugins directory for macOS."""
    home_path = Path(home).expanduser() if home is not None else Path.home()
    if sketchup_version:
        return (
            home_path
            / "Library"
            / "Application Support"
            / "SketchUp"
            / f"SketchUp {sketchup_version}"
            / "SketchUp"
            / "Plugins"
        )

    detected = installed_sketchup_plugin_dirs(home_path)
    if detected:
        return detected[0]

    return (
        home_path
        / "Library"
        / "Application Support"
        / "SketchUp"
        / "SketchUp 2024"
        / "SketchUp"
        / "Plugins"
    )


def install_bridge(
    plugins_dir: str | Path | None = None,
    source_dir: str | Path | None = None,
    sketchup_version: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Install the Ruby bridge into a SketchUp Plugins directory."""
    source = Path(source_dir).expanduser().resolve() if source_dir else default_bridge_source()
    if not source.exists():
        raise FileNotFoundError(f"Bridge source not found: {source}")
    if not (source / "lib" / "su_bridge.rb").exists():
        raise FileNotFoundError(f"Invalid bridge source: {source}")

    target_root = (
        Path(plugins_dir).expanduser().resolve()
        if plugins_dir
        else default_plugins_dir(sketchup_version).expanduser().resolve()
    )
    target = target_root / "su_bridge"
    backup_path = None
    if target.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = target_root / f"su_bridge.backup-{timestamp}"

    result = {
        "source": str(source),
        "plugins_dir": str(target_root),
        "target": str(target),
        "target_exists": target.exists(),
        "backup_path": str(backup_path) if backup_path else None,
        "dry_run": dry_run,
        "installed": False,
        "force": force,
        "load_command": f"load '{target / 'lib' / 'su_bridge.rb'}'; SuBridge.start",
    }

    if dry_run:
        return result

    if target.exists() and not force:
        raise FileExistsError(
            f"Bridge already exists: {target}. Use --force to replace it."
        )

    target_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert backup_path is not None
        shutil.move(str(target), str(backup_path))
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(*IGNORED_BRIDGE_PATTERNS),
    )
    result["installed"] = True
    return result
