"""Release smoke checks for SketchUp Agent Harness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from mcp_server.bridge_install import install_bridge, repo_root_from_package
from mcp_server.smoke import DEFAULT_SMOKE_PROJECT, check_result, run_smoke


MANIFEST_PATHS = (
    ".mcp.json",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    ".agents/plugins/marketplace.json",
)


def _repo_root(repo_root: str | Path | None = None) -> Path:
    """Return the repository root for source-checkout release checks."""
    return Path(repo_root).expanduser().resolve() if repo_root else repo_root_from_package()


def manifest_json_check(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Validate plugin and MCP manifest JSON files."""
    root = _repo_root(repo_root)
    manifest_results: list[dict[str, Any]] = []
    for relative_path in MANIFEST_PATHS:
        path = root / relative_path
        errors: list[str] = []
        parsed = False
        if not path.exists():
            errors.append(f"File not found: {path}")
        else:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                parsed = isinstance(data, dict)
                if not parsed:
                    errors.append("Manifest must be a JSON object.")
            except json.JSONDecodeError as error:
                errors.append(
                    f"Invalid JSON: {error.msg} at line {error.lineno}, column {error.colno}"
                )
        manifest_results.append(
            {
                "path": str(path),
                "ok": not errors and parsed,
                "errors": errors,
            }
        )

    return check_result(
        "manifest_json",
        all(item["ok"] for item in manifest_results),
        {"manifests": manifest_results},
        [
            error
            for item in manifest_results
            for error in item.get("errors", [])
        ],
    )


def startup_check(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Check the MCP startup script import path."""
    root = _repo_root(repo_root)
    command = [str(root / "mcp_server" / "start.sh"), "--startup-check"]
    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return check_result(
        "mcp_startup",
        result.returncode == 0,
        {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
        [] if result.returncode == 0 else [result.stderr or result.stdout],
    )


def bridge_install_dry_run_check(
    plugins_dir: str | Path = "/tmp/sah-release-plugins",
) -> dict[str, Any]:
    """Check bridge installer path without mutating SketchUp directories."""
    try:
        result = install_bridge(plugins_dir=plugins_dir, dry_run=True)
    except Exception as error:
        return check_result(
            "bridge_install_dry_run",
            False,
            {"plugins_dir": str(Path(plugins_dir).expanduser())},
            [str(error)],
        )

    return check_result(
        "bridge_install_dry_run",
        result.get("dry_run") is True and result.get("installed") is False,
        result,
    )


def product_smoke_check(
    project_path: str | Path = DEFAULT_SMOKE_PROJECT,
) -> dict[str, Any]:
    """Run the shared headless product smoke path."""
    result = run_smoke(project_path, overwrite=True)
    return check_result(
        "product_smoke",
        result["ok"],
        result,
        [
            error
            for check in result.get("checks", [])
            for error in check.get("errors", [])
        ],
    )


def run_release_check(
    project_path: str | Path = "/tmp/sah-release-check",
    plugins_dir: str | Path = "/tmp/sah-release-plugins",
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run deterministic release checks that do not require SketchUp UI."""
    root = _repo_root(repo_root)
    checks = [
        manifest_json_check(root),
        startup_check(root),
        product_smoke_check(project_path),
        bridge_install_dry_run_check(plugins_dir),
    ]
    return {
        "repo_root": str(root),
        "project_path": str(Path(project_path).expanduser().resolve()),
        "plugins_dir": str(Path(plugins_dir).expanduser().resolve()),
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }
