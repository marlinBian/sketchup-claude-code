"""Release smoke checks for SketchUp Agent Harness."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
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
MAX_COMMAND_OUTPUT_CHARS = 4000


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
    result = _run_command(command, cwd=root, timeout=60)
    return check_result(
        "mcp_startup",
        result["ok"],
        result,
        [] if result["ok"] else [result["stderr"] or result["stdout"]],
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


def _run_command(
    command: list[str],
    cwd: str | Path | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    """Run one release-check subprocess and return a compact result."""
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    stdout = _compact_output(result.stdout)
    stderr = _compact_output(result.stderr)
    return {
        "command": command,
        "cwd": str(cwd) if cwd else None,
        "returncode": result.returncode,
        "stdout": stdout["output"],
        "stderr": stderr["output"],
        "stdout_truncated": stdout["truncated"],
        "stderr_truncated": stderr["truncated"],
        "ok": result.returncode == 0,
    }


def _compact_output(output: str) -> dict[str, Any]:
    """Keep release-check command output readable in JSON reports."""
    if len(output) <= MAX_COMMAND_OUTPUT_CHARS:
        return {"output": output, "truncated": False}
    omitted = len(output) - MAX_COMMAND_OUTPUT_CHARS
    head_chars = MAX_COMMAND_OUTPUT_CHARS // 3
    tail_chars = MAX_COMMAND_OUTPUT_CHARS - head_chars
    compacted = (
        output[:head_chars]
        + f"\n... truncated {omitted} characters ...\n"
        + output[-tail_chars:]
    )
    return {"output": compacted, "truncated": True}


def wheel_install_check(
    repo_root: str | Path | None = None,
    dist_dir: str | Path = "/tmp/sah-release-dist",
    venv_dir: str | Path = "/tmp/sah-release-wheel-venv",
    project_path: str | Path = "/tmp/sah-release-wheel-project",
    plugins_dir: str | Path = "/tmp/sah-release-wheel-plugins",
    profile_path: str | Path = "/tmp/sah-release-designer-profile.json",
) -> dict[str, Any]:
    """Build the wheel and verify installed-package project and bridge paths."""
    root = _repo_root(repo_root)
    package_root = root / "mcp_server"
    dist = Path(dist_dir).expanduser().resolve()
    venv = Path(venv_dir).expanduser().resolve()
    project = Path(project_path).expanduser().resolve()
    plugins = Path(plugins_dir).expanduser().resolve()
    profile = Path(profile_path).expanduser().resolve()
    commands: list[dict[str, Any]] = []
    errors: list[str] = []

    if shutil.which("uv") is None:
        return check_result(
            "wheel_install",
            False,
            {"error": "uv is not available on PATH."},
            ["uv is not available on PATH."],
        )

    if venv.exists():
        shutil.rmtree(venv)

    build = _run_command(
        [
            "uv",
            "build",
            "--wheel",
            "--out-dir",
            str(dist),
            "--clear",
            str(package_root),
        ],
        cwd=root,
        timeout=240,
    )
    commands.append(build)
    if not build["ok"]:
        errors.append(build["stderr"] or build["stdout"])

    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        errors.append(f"No wheel produced in {dist}.")
    wheel_path = wheels[-1] if wheels else None

    if not errors:
        create_venv = _run_command(
            [sys.executable, "-m", "venv", str(venv)],
            cwd=root,
        )
        commands.append(create_venv)
        if not create_venv["ok"]:
            errors.append(create_venv["stderr"] or create_venv["stdout"])

    pip = venv / "bin" / "pip"
    agent = venv / "bin" / "sketchup-agent"
    if not errors and wheel_path is not None:
        install = _run_command(
            [str(pip), "install", str(wheel_path)],
            cwd=root,
            timeout=240,
        )
        commands.append(install)
        if not install["ok"]:
            errors.append(install["stderr"] or install["stdout"])

    installed_commands = [
        [
            str(agent),
            "profile-init",
            "--path",
            str(profile),
            "--force",
        ],
        [
            str(agent),
            "profile-status",
            "--path",
            str(profile),
        ],
        [
            str(agent),
            "install-bridge",
            "--plugins-dir",
            str(plugins),
            "--dry-run",
        ],
        [
            str(agent),
            "install-bridge",
            "--plugins-dir",
            str(plugins),
            "--force",
        ],
        [
            str(agent),
            "init",
            str(project),
            "--template",
            "bathroom",
            "--force",
        ],
        [str(agent), "validate", str(project)],
        [
            str(agent),
            "install-skills",
            str(project),
            "--target",
            "all",
            "--dry-run",
        ],
    ]
    if not errors:
        for command in installed_commands:
            command_result = _run_command(command, cwd=root, timeout=180)
            commands.append(command_result)
            if not command_result["ok"]:
                errors.append(command_result["stderr"] or command_result["stdout"])
                break

    expected_files = [
        profile,
        plugins / "su_bridge" / "lib" / "su_bridge.rb",
        plugins / "su_bridge.rb",
        project / ".agents" / "skills" / "bathroom_planning" / "SKILL.md",
        project / ".claude" / "skills" / "bathroom_planning" / "SKILL.md",
    ]
    if not errors:
        missing_files = [str(path) for path in expected_files if not path.exists()]
        if missing_files:
            errors.append(f"Missing installed files: {missing_files}")

    return check_result(
        "wheel_install",
        not errors,
        {
            "dist_dir": str(dist),
            "venv_dir": str(venv),
            "project_path": str(project),
            "plugins_dir": str(plugins),
            "profile_path": str(profile),
            "wheel": str(wheel_path) if wheel_path else None,
            "commands": commands,
        },
        errors,
    )


def run_release_check(
    project_path: str | Path = "/tmp/sah-release-check",
    plugins_dir: str | Path = "/tmp/sah-release-plugins",
    repo_root: str | Path | None = None,
    include_wheel: bool = False,
    wheel_dist_dir: str | Path = "/tmp/sah-release-dist",
    wheel_venv_dir: str | Path = "/tmp/sah-release-wheel-venv",
    wheel_project_path: str | Path = "/tmp/sah-release-wheel-project",
    wheel_plugins_dir: str | Path = "/tmp/sah-release-wheel-plugins",
) -> dict[str, Any]:
    """Run deterministic release checks that do not require SketchUp UI."""
    root = _repo_root(repo_root)
    checks = [
        manifest_json_check(root),
        startup_check(root),
        product_smoke_check(project_path),
        bridge_install_dry_run_check(plugins_dir),
    ]
    if include_wheel:
        checks.append(
            wheel_install_check(
                repo_root=root,
                dist_dir=wheel_dist_dir,
                venv_dir=wheel_venv_dir,
                project_path=wheel_project_path,
                plugins_dir=wheel_plugins_dir,
            )
        )
    return {
        "repo_root": str(root),
        "project_path": str(Path(project_path).expanduser().resolve()),
        "plugins_dir": str(Path(plugins_dir).expanduser().resolve()),
        "include_wheel": include_wheel,
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }
