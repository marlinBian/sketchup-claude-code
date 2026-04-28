"""Environment doctoring for SketchUp Agent Harness."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from mcp_server.bridge_install import (
    LOADER_FILENAME,
    default_bridge_source,
    default_plugins_dir,
    installed_sketchup_app_versions,
    installed_sketchup_plugin_dirs,
)
from mcp_server.bridge.socket_bridge import BridgeConfig, SocketBridge
from mcp_server.protocol.jsonrpc import JsonRpcRequest
from mcp_server.resources.design_rules_schema import (
    DESIGNER_PROFILE_ENV,
    designer_profile_path_from_env,
    load_designer_profile_rules,
)
from mcp_server.runtime_skills import runtime_skill_status
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


def bridge_runtime_capability_check(
    socket_path: str = DEFAULT_BRIDGE_SOCKET,
) -> dict[str, Any]:
    """Check whether the live bridge supports required non-mutating operations."""
    path = Path(socket_path)
    if not path.exists():
        return check(
            "bridge_runtime_capabilities",
            True,
            {"path": str(path), "skipped": True},
            severity="info",
            message="Skipped because the SketchUp bridge socket is not available.",
        )

    required_operations = {
        "get_scene_info": {},
        "get_selection_info": {"limit": 0},
    }
    operation_results: dict[str, dict[str, Any]] = {}
    bridge = SocketBridge(
        BridgeConfig(
            socket_path=str(path),
            connect_timeout=1.0,
            recv_timeout=5.0,
            max_retries=1,
        )
    )

    try:
        info_request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "doctor_get_bridge_info",
                "operation_type": "get_bridge_info",
                "payload": {},
                "rollback_on_failure": False,
            },
        )
        info_response = bridge.send(info_request.to_dict())
        bridge_info = info_response.get("result", {}).get("bridge_info")
        if isinstance(bridge_info, dict):
            supported = set(bridge_info.get("supported_operations", []))
            operation_results = {
                operation_type: {
                    "ok": operation_type in supported,
                    "error": (
                        None
                        if operation_type in supported
                        else "Missing from get_bridge_info supported_operations"
                    ),
                }
                for operation_type in required_operations
            }
            ok = all(result["ok"] for result in operation_results.values())
            return check(
                "bridge_runtime_capabilities",
                ok,
                {
                    "path": str(path),
                    "bridge_info": bridge_info,
                    "required_operations": operation_results,
                },
                severity="warning",
                message=(
                    None
                    if ok
                    else (
                        "Live SketchUp bridge is missing required operation support. "
                        "Restart SketchUp after install-bridge, or reload the bridge."
                    )
                ),
            )

        for operation_type, payload in required_operations.items():
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": f"doctor_{operation_type}",
                    "operation_type": operation_type,
                    "payload": payload,
                    "rollback_on_failure": False,
                },
            )
            response = bridge.send(request.to_dict())
            error = response.get("error")
            operation_results[operation_type] = {
                "ok": error is None,
                "error": error.get("message") if isinstance(error, dict) else None,
            }
    except Exception as error:
        return check(
            "bridge_runtime_capabilities",
            False,
            {"path": str(path), "error": str(error)},
            severity="warning",
            message="Could not query the live SketchUp bridge runtime.",
        )
    finally:
        bridge.disconnect()

    ok = all(result["ok"] for result in operation_results.values())
    return check(
        "bridge_runtime_capabilities",
        ok,
        {
            "path": str(path),
            "required_operations": operation_results,
        },
        severity="warning",
        message=(
            None
            if ok
            else (
                "Live SketchUp bridge is missing required operation support. "
                "Restart SketchUp after install-bridge, or reload the bridge."
            )
        ),
    )


def sketchup_install_check(
    sketchup_version: str | None = None,
    plugins_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Check detected or requested SketchUp plugin installation paths."""
    detected_dirs = installed_sketchup_plugin_dirs()
    installed_app_versions = installed_sketchup_app_versions()
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
            "installed_app_versions": installed_app_versions,
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


def runtime_skills_check(project_path: str | Path | None) -> dict[str, Any] | None:
    """Check project-local Claude and Codex runtime skill installs."""
    if project_path is None:
        return None
    try:
        status = runtime_skill_status(project_path)
    except Exception as error:
        return check(
            "runtime_skills",
            False,
            {"project_path": str(Path(project_path).expanduser().resolve())},
            severity="warning",
            message=f"Could not inspect runtime skills: {error}",
        )

    return check(
        "runtime_skills",
        status["ok"],
        status,
        severity="warning",
        message=(
            None
            if status["ok"]
            else "Project runtime skills differ from the current harness. Run "
            "`sketchup-agent install-skills <project-path> --target all --force`."
        ),
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
        bridge_runtime_capability_check(socket_path),
    ]
    project_validation = project_check(project_path)
    if project_validation is not None:
        checks.append(project_validation)
    runtime_validation = runtime_skills_check(project_path)
    if runtime_validation is not None:
        checks.append(runtime_validation)

    blocking_failures = [
        item for item in checks if not item["ok"] and item.get("severity") == "error"
    ]
    return {
        "ok": len(blocking_failures) == 0,
        "checks": checks,
    }
