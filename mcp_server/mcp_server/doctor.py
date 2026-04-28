"""Environment doctoring for SketchUp Agent Harness."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from mcp_server.bridge_install import (
    LOADER_FILENAME,
    default_bridge_source,
    default_plugins_dir,
    installed_sketchup_plugin_dirs,
)
from mcp_server.resources.design_rules_schema import (
    DESIGNER_PROFILE_ENV,
    designer_profile_path_from_env,
    load_designer_profile_rules,
)
from mcp_server.smoke import DEFAULT_BRIDGE_SOCKET, validate_project


def check(
    name: str,
    ok: bool,
    details: dict[str, Any] | None = None,
    severity: str = "error",
    message: str | None = None,
) -> dict[str, Any]:
    """Return one doctor check."""
    result: dict[str, Any] = {
        "name": name,
        "ok": ok,
        "severity": severity,
    }
    if details:
        result["details"] = details
    if message:
        result["message"] = message
    return result


def bridge_source_check() -> dict[str, Any]:
    """Check whether the bridge runtime source is available."""
    source = default_bridge_source()
    bridge_file = source / "lib" / "su_bridge.rb"
    return check(
        "bridge_source",
        bridge_file.exists(),
        {"path": str(source)},
        message=None if bridge_file.exists() else "Ruby bridge runtime is missing.",
    )


def console_script_check(command: str) -> dict[str, Any]:
    """Check whether a console script is on PATH."""
    path = shutil.which(command)
    return check(
        command,
        path is not None,
        {"path": path} if path else None,
        message=None if path else f"{command} is not available on PATH.",
    )


def bridge_socket_check(socket_path: str = DEFAULT_BRIDGE_SOCKET) -> dict[str, Any]:
    """Check whether the live bridge socket exists."""
    path = Path(socket_path)
    return check(
        "bridge_socket",
        path.exists(),
        {"path": str(path)},
        severity="warning",
        message=None if path.exists() else "SketchUp bridge socket is not available.",
    )


def sketchup_install_check(
    sketchup_version: str | None = None,
    plugins_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Check detected or requested SketchUp plugin installation paths."""
    detected_dirs = installed_sketchup_plugin_dirs()
    target_root = (
        Path(plugins_dir).expanduser().resolve()
        if plugins_dir
        else default_plugins_dir(sketchup_version).expanduser().resolve()
    )
    bridge_dir = target_root / "su_bridge"
    loader_file = target_root / LOADER_FILENAME
    ok = bridge_dir.is_dir() and loader_file.exists()
    return check(
        "sketchup_bridge_install",
        ok,
        {
            "plugins_dir": str(target_root),
            "bridge_dir": str(bridge_dir),
            "loader": str(loader_file),
            "detected_plugins_dirs": [str(path) for path in detected_dirs],
            "bridge_dir_exists": bridge_dir.is_dir(),
            "loader_exists": loader_file.exists(),
        },
        severity="warning",
        message=None if ok else "SketchUp bridge is not installed in the target Plugins directory.",
    )


def project_check(project_path: str | Path | None) -> dict[str, Any] | None:
    """Validate a project directory when one is provided."""
    if project_path is None:
        return None
    validation = validate_project(project_path)
    return check(
        "project_validation",
        validation["ok"],
        validation,
        message=None if validation["ok"] else "Project workspace validation failed.",
    )


def designer_profile_check() -> dict[str, Any]:
    """Check configured reusable designer profile rules."""
    path = designer_profile_path_from_env()
    if path is None:
        return check(
            "designer_profile",
            True,
            {"env": DESIGNER_PROFILE_ENV, "configured": False},
            severity="info",
        )

    profile, errors = load_designer_profile_rules(path)
    return check(
        "designer_profile",
        profile is not None and not errors,
        {
            "env": DESIGNER_PROFILE_ENV,
            "configured": True,
            "path": str(path),
        },
        severity="error",
        message="; ".join(errors) if errors else None,
    )


def run_doctor(
    project_path: str | Path | None = None,
    sketchup_version: str | None = None,
    plugins_dir: str | Path | None = None,
    socket_path: str = DEFAULT_BRIDGE_SOCKET,
) -> dict[str, Any]:
    """Run environment checks for the installed harness and optional project."""
    checks = [
        console_script_check("sketchup-agent"),
        console_script_check("sketchup-agent-mcp"),
        bridge_source_check(),
        designer_profile_check(),
        sketchup_install_check(sketchup_version=sketchup_version, plugins_dir=plugins_dir),
        bridge_socket_check(socket_path),
    ]
    project_validation = project_check(project_path)
    if project_validation is not None:
        checks.append(project_validation)

    blocking_failures = [
        item for item in checks if not item["ok"] and item.get("severity") == "error"
    ]
    return {
        "ok": len(blocking_failures) == 0,
        "checks": checks,
    }
