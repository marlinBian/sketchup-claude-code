"""SketchUp Ruby bridge installation helpers."""

from __future__ import annotations

import json
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
LOADER_FILENAME = "su_bridge.rb"


def repo_root_from_package() -> Path:
    """Return the source checkout root when running from this repository."""
    return Path(__file__).resolve().parents[2]


def default_bridge_source() -> Path:
    """Return the default bridge source directory."""
    return repo_root_from_package() / "su_bridge"


def installed_sketchup_plugin_dirs(home: str | Path | None = None) -> list[Path]:
    """Return detected macOS SketchUp plugin directories, newest first."""
    app_support = (
        Path(home).expanduser()
        if home is not None
        else Path.home()
    ) / "Library" / "Application Support"
    candidates: list[Path] = []

    for app_dir in app_support.glob("SketchUp *"):
        if not app_dir.is_dir():
            continue
        plugins_dir = app_dir / "SketchUp" / "Plugins"
        if plugins_dir.exists():
            candidates.append(plugins_dir)

    legacy_root = app_support / "SketchUp"
    if legacy_root.exists():
        for app_dir in legacy_root.glob("SketchUp *"):
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


def bridge_loader_content() -> str:
    """Return the SketchUp Plugins root loader for the installed bridge."""
    return """# frozen_string_literal: true

log_path = ENV.fetch("SU_BRIDGE_LOADER_LOG", "/tmp/su_bridge_loader.log")

begin
  require "sketchup.rb"
  require "extensions.rb"

  extension = SketchupExtension.new(
    "SketchUp Agent Harness Bridge",
    "su_bridge/lib/su_bridge"
  )
  extension.description = "Local socket bridge for SketchUp Agent Harness."
  extension.version = "0.1.0"
  extension.creator = "SketchUp Agent Harness"
  Sketchup.register_extension(extension, true)

  bridge_path = File.expand_path("su_bridge/lib/su_bridge.rb", __dir__)
  File.open(log_path, "a") do |log|
    log.puts("[#{Time.now.utc}] loading #{bridge_path}")
  end
  require bridge_path
  SuBridge.start if defined?(SuBridge)
  File.open(log_path, "a") { |log| log.puts("[#{Time.now.utc}] started") }
rescue Exception => error
  File.open(log_path, "a") do |log|
    log.puts("[#{Time.now.utc}] #{error.class}: #{error.message}")
    log.puts(error.backtrace.join("\\n")) if error.backtrace
  end
  raise
end
"""


def enable_bridge_loader_preference(plugins_dir: Path) -> dict[str, Any]:
    """Enable the bridge root loader in SketchUp macOS preferences when present."""
    preferences_path = plugins_dir.parent / "PrivatePreferences.json"
    result = {
        "path": str(preferences_path),
        "exists": preferences_path.exists(),
        "enabled": False,
        "updated": False,
    }
    if not preferences_path.exists():
        return result

    data = json.loads(preferences_path.read_text(encoding="utf-8"))
    extensions = data.setdefault("This Computer Only", {}).setdefault("Extensions", {})
    previous_value = extensions.get(LOADER_FILENAME)
    extensions[LOADER_FILENAME] = 1
    result["enabled"] = True
    result["updated"] = previous_value != 1
    if result["updated"]:
        preferences_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result


def timestamped_backup_path(path: Path, timestamp: str) -> Path:
    """Return an unused backup path next to an existing plugin path."""
    candidate = path.parent / f"{path.name}.backup-{timestamp}"
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        next_candidate = path.parent / f"{path.name}.backup-{timestamp}-{counter}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1


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
    loader = target_root / LOADER_FILENAME
    backup_path = None
    loader_backup_path = None
    if target.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = timestamped_backup_path(target, timestamp)
        if loader.exists():
            loader_backup_path = timestamped_backup_path(loader, timestamp)
    elif loader.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        loader_backup_path = timestamped_backup_path(loader, timestamp)

    result = {
        "source": str(source),
        "plugins_dir": str(target_root),
        "target": str(target),
        "loader": str(loader),
        "loader_preference": None,
        "target_exists": target.exists(),
        "loader_exists": loader.exists(),
        "backup_path": str(backup_path) if backup_path else None,
        "loader_backup_path": str(loader_backup_path) if loader_backup_path else None,
        "dry_run": dry_run,
        "installed": False,
        "force": force,
        "load_command": f"load '{loader}'",
    }

    if dry_run:
        return result

    if (target.exists() or loader.exists()) and not force:
        raise FileExistsError(
            f"Bridge already exists in {target_root}. Use --force to replace it."
        )

    target_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert backup_path is not None
        shutil.move(str(target), str(backup_path))
    if loader.exists():
        assert loader_backup_path is not None
        shutil.move(str(loader), str(loader_backup_path))
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(*IGNORED_BRIDGE_PATTERNS),
    )
    loader.write_text(bridge_loader_content(), encoding="utf-8")
    result["loader_preference"] = enable_bridge_loader_preference(target_root)
    result["installed"] = True
    return result
