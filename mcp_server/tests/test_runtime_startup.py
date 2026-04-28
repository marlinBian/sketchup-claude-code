"""Runtime startup and MCP registration smoke tests."""

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_plugin_manifests_are_valid_json():
    for path in (
        REPO_ROOT / ".mcp.json",
        REPO_ROOT / ".claude-plugin" / "plugin.json",
        REPO_ROOT / ".claude-plugin" / "marketplace.json",
        REPO_ROOT / ".codex-plugin" / "plugin.json",
        REPO_ROOT / ".agents" / "plugins" / "marketplace.json",
    ):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)


def test_start_script_can_import_runtime_dependencies():
    result = subprocess.run(
        [str(REPO_ROOT / "mcp_server" / "start.sh"), "--startup-check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_main_module_registers_late_tools_before_run(monkeypatch):
    code = """
import asyncio
import json
import runpy
from mcp.server.fastmcp import FastMCP

def fake_run(self):
    async def collect_tool_names():
        return [tool.name for tool in await self.list_tools()]
    print(json.dumps(asyncio.run(collect_tool_names())))

FastMCP.run = fake_run
runpy.run_module("mcp_server.server", run_name="__main__")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT / "mcp_server",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    tools = json.loads(result.stdout.strip().splitlines()[-1])
    assert {
        "register_project_component",
        "rotate_entity",
        "scale_entity",
        "copy_entity",
    }.issubset(set(tools))
