"""Local smoke checks for SketchUp Agent Harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_server.project_init import (
    PROJECT_CLAUDE_GUIDANCE_FILENAME,
    PROJECT_CODEX_GUIDANCE_FILENAME,
    init_project,
)
from mcp_server.resources.asset_lock_schema import load_assets_lock
from mcp_server.resources.design_model_schema import load_design_model, save_design_model
from mcp_server.resources.design_rules_schema import load_design_rules
from mcp_server.resources.project_files import (
    assets_cache_path,
    assets_lock_path,
    design_rules_path,
    find_design_model_path,
    snapshot_manifest_path,
    snapshots_path,
)
from mcp_server.resources.snapshot_manifest_schema import load_snapshot_manifest
from mcp_server.tools.bathroom_planner import plan_bathroom_project
from mcp_server.tools.trace_executor import (
    execute_bridge_operations,
    sync_execution_report_to_design_model,
)

DEFAULT_SMOKE_PROJECT = "/tmp/sketchup-agent-smoke"
DEFAULT_BRIDGE_SOCKET = "/tmp/su_bridge.sock"


def check_result(
    name: str,
    ok: bool,
    details: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """Return one smoke check result."""
    result: dict[str, Any] = {
        "name": name,
        "ok": ok,
    }
    if details:
        result["details"] = details
    if errors:
        result["errors"] = errors
    return result


def component_refs_from_model(design_model: dict[str, Any]) -> set[str]:
    """Return component refs used by components and lighting."""
    refs: set[str] = set()
    for component in design_model.get("components", {}).values():
        component_ref = component.get("component_ref")
        if isinstance(component_ref, str) and component_ref:
            refs.add(component_ref)
    for lighting in design_model.get("lighting", {}).values():
        component_ref = lighting.get("component_ref")
        if isinstance(component_ref, str) and component_ref:
            refs.add(component_ref)
    return refs


def validate_project(project_path: str | Path) -> dict[str, Any]:
    """Validate the generated project files used by local smoke checks."""
    root = Path(project_path).expanduser().resolve()
    checks: list[dict[str, Any]] = []

    design_model_file = find_design_model_path(root)
    design_model, design_model_errors = load_design_model(str(design_model_file))
    checks.append(
        check_result(
            "design_model",
            design_model is not None,
            {"path": str(design_model_file)},
            design_model_errors,
        )
    )

    rules_file = design_rules_path(root)
    design_rules, design_rules_errors = load_design_rules(rules_file)
    checks.append(
        check_result(
            "design_rules",
            design_rules is not None,
            {"path": str(rules_file)},
            design_rules_errors,
        )
    )

    lock_file = assets_lock_path(root)
    assets_lock, lock_errors = load_assets_lock(lock_file)
    checks.append(
        check_result(
            "assets_lock",
            assets_lock is not None,
            {"path": str(lock_file)},
            lock_errors,
        )
    )

    cache_dir = assets_cache_path(root)
    checks.append(
        check_result(
            "assets_cache",
            cache_dir.is_dir(),
            {"path": str(cache_dir)},
            [] if cache_dir.is_dir() else ["Asset cache directory is missing."],
        )
    )

    snapshot_dir = snapshots_path(root)
    manifest_file = snapshot_manifest_path(root)
    snapshot_manifest, manifest_errors = load_snapshot_manifest(manifest_file)
    checks.append(
        check_result(
            "snapshot_manifest",
            snapshot_dir.is_dir() and snapshot_manifest is not None,
            {"path": str(manifest_file)},
            manifest_errors if snapshot_dir.is_dir() else ["Snapshots directory is missing."],
        )
    )

    for filename, check_name in (
        (PROJECT_CODEX_GUIDANCE_FILENAME, "codex_guidance"),
        (PROJECT_CLAUDE_GUIDANCE_FILENAME, "claude_guidance"),
    ):
        guidance_file = root / filename
        checks.append(
            check_result(
                check_name,
                guidance_file.exists(),
                {"path": str(guidance_file)},
                [] if guidance_file.exists() else [f"{filename} is missing."],
            )
        )

    if design_model is not None and assets_lock is not None:
        refs = component_refs_from_model(design_model)
        locked_refs = {
            asset["component_id"]
            for asset in assets_lock.get("assets", [])
            if isinstance(asset.get("component_id"), str)
        }
        missing_refs = sorted(refs - locked_refs)
        checks.append(
            check_result(
                "asset_refs_locked",
                len(missing_refs) == 0,
                {"component_refs": sorted(refs), "locked_refs": sorted(locked_refs)},
                [f"Missing asset lock entries: {missing_refs}"] if missing_refs else [],
            )
        )

    return {
        "project_path": str(root),
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }


def bridge_socket_check(socket_path: str = DEFAULT_BRIDGE_SOCKET) -> dict[str, Any]:
    """Check whether the SketchUp bridge socket exists."""
    path = Path(socket_path)
    return check_result(
        "bridge_socket",
        path.exists(),
        {"path": str(path)},
        [] if path.exists() else ["SketchUp bridge socket is not available."],
    )


def run_smoke(
    project_path: str | Path = DEFAULT_SMOKE_PROJECT,
    template: str = "bathroom",
    overwrite: bool = False,
    with_bridge: bool = False,
    socket_path: str = DEFAULT_BRIDGE_SOCKET,
) -> dict[str, Any]:
    """Run a deterministic local smoke check."""
    root = Path(project_path).expanduser().resolve()
    result: dict[str, Any] = {
        "project_path": str(root),
        "template": template,
        "with_bridge": with_bridge,
        "checks": [],
    }

    try:
        init_result = init_project(root, template=template, overwrite=overwrite)
        result["init"] = init_result
        result["checks"].append(check_result("init_project", True))
    except Exception as error:
        result["checks"].append(check_result("init_project", False, errors=[str(error)]))
        result["ok"] = False
        return result

    project_validation = validate_project(root)
    result["project_validation"] = project_validation
    result["checks"].append(
        check_result(
            "project_validation",
            project_validation["ok"],
            {"checked": len(project_validation["checks"])},
        )
    )

    plan = plan_bathroom_project(project_name=root.name)
    plan_ok = bool(plan["validation_report"]["valid"]) and len(plan["bridge_operations"]) > 0
    result["headless_plan"] = {
        "valid": plan["validation_report"]["valid"],
        "bridge_operation_count": len(plan["bridge_operations"]),
    }
    result["checks"].append(check_result("headless_bathroom_plan", plan_ok))

    if with_bridge:
        socket_check = bridge_socket_check(socket_path)
        result["checks"].append(socket_check)
        if socket_check["ok"]:
            try:
                execution_report = execute_bridge_operations(plan["bridge_operations"])
                result["bridge_execution"] = execution_report
                result["checks"].append(
                    check_result(
                        "bridge_execution",
                        execution_report.get("status") == "success",
                        {
                            "status": execution_report.get("status"),
                            "executed_count": execution_report.get("executed_count"),
                        },
                    )
                )
                if execution_report.get("status") == "success":
                    sync_report = sync_execution_report_to_design_model(
                        plan["design_model"],
                        execution_report,
                    )
                    design_model_file = find_design_model_path(root)
                    saved, save_errors = save_design_model(
                        str(design_model_file),
                        plan["design_model"],
                    )
                    sync_report["saved"] = saved
                    sync_report["errors"] = save_errors
                    result["execution_sync"] = sync_report
                    result["checks"].append(
                        check_result(
                            "execution_sync",
                            saved,
                            {
                                "recorded_operations": len(
                                    sync_report["recorded_operations"]
                                ),
                                "updated_components": len(
                                    sync_report["updated_components"]
                                ),
                                "updated_lighting": len(sync_report["updated_lighting"]),
                            },
                            save_errors,
                        )
                    )
            except Exception as error:
                result["checks"].append(
                    check_result("bridge_execution", False, errors=[str(error)])
                )

    result["ok"] = all(check["ok"] for check in result["checks"])
    return result
