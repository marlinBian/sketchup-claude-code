"""SketchUp Ruby bridge installation helpers."""

from __future__ import annotations

import json
import re
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
SKETCHUP_VERSION_RE = re.compile(r"\bSketchUp\s+(\d{4})\b")


def repo_root_from_package() -> Path:
    """Return the source checkout root when running from this repository."""
    return Path(__file__).resolve().parents[2]


def default_bridge_source() -> Path:
    """Return the default bridge source directory."""
    repo_source = repo_root_from_package() / "su_bridge"
    if repo_source.exists():
        return repo_source
    return packaged_bridge_source()


def packaged_bridge_source() -> Path:
    """Return the packaged bridge runtime directory from an installed wheel."""
    return Path(__file__).resolve().parent / "packaged" / "su_bridge"


def sketchup_version_from_name(name: str) -> str | None:
    """Return the SketchUp year version embedded in a file or directory name."""
    match = SKETCHUP_VERSION_RE.search(name)
    return match.group(1) if match else None


def version_sort_value(version: str | None) -> int:
    """Return a sortable integer for a SketchUp year version."""
    if version is None:
        return -1
    try:
        return int(version)
    except ValueError:
        return -1


def installed_sketchup_app_versions(
    applications_dir: str | Path = "/Applications",
) -> list[str]:
    """Return detected macOS SketchUp app versions, newest first."""
    root = Path(applications_dir).expanduser()
    if not root.exists():
        return []

    versions: set[str] = set()
    for path in root.glob("SketchUp*"):
        version = sketchup_version_from_name(path.name)
        if version is None:
            continue
        if path.suffix == ".app" and path.is_dir():
            versions.add(version)
            continue
        if path.is_dir() and (path / "SketchUp.app").is_dir():
            versions.add(version)

    return sorted(versions, key=version_sort_value, reverse=True)


def sketchup_plugins_dir_for_version(home: str | Path, version: str) -> Path:
    """Return the canonical macOS Plugins directory for one SketchUp version."""
    return (
        Path(home).expanduser()
        / "Library"
        / "Application Support"
        / f"SketchUp {version}"
        / "SketchUp"
        / "Plugins"
    )


def installed_sketchup_plugin_dirs(
    home: str | Path | None = None,
    applications_dir: str | Path = "/Applications",
) -> list[Path]:
    """Return detected macOS SketchUp plugin directories, newest first."""
    home_path = Path(home).expanduser() if home is not None else Path.home()
    app_support = home_path / "Library" / "Application Support"
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

    installed_versions = installed_sketchup_app_versions(applications_dir)
    installed_rank = {version: index for index, version in enumerate(installed_versions)}

    def sort_key(path: Path) -> tuple[int, int, int, str]:
        version = sketchup_version_from_name(path.parent.parent.name)
        if version in installed_rank:
            return (0, installed_rank[version], 0, str(path))
        return (1, 0, -version_sort_value(version), str(path))

    return sorted(candidates, key=sort_key)


def default_plugins_dir(
    sketchup_version: str | None = None,
    home: str | Path | None = None,
    applications_dir: str | Path = "/Applications",
) -> Path:
    """Return the target SketchUp Plugins directory for macOS."""
    home_path = Path(home).expanduser() if home is not None else Path.home()
    if sketchup_version:
        return sketchup_plugins_dir_for_version(home_path, sketchup_version)

    app_versions = installed_sketchup_app_versions(applications_dir)
    if app_versions:
        return sketchup_plugins_dir_for_version(home_path, app_versions[0])

    detected = installed_sketchup_plugin_dirs(home_path, applications_dir)
    if detected:
        return detected[0]

    return sketchup_plugins_dir_for_version(home_path, "2024")


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
