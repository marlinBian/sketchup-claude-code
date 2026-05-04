from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Include product runtime assets from both repo and sdist build roots."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        root = Path(self.root)

        bridge_source = root.parent / "su_bridge" / "lib"
        runtime_skills_source = root.parent / "skills"
        packaged_bridge = root / "mcp_server" / "packaged" / "su_bridge" / "lib"
        packaged_runtime_skills = root / "mcp_server" / "packaged" / "runtime_skills"

        if bridge_source.exists() and runtime_skills_source.exists():
            force_include = build_data.setdefault("force_include", {})
            force_include[str(bridge_source)] = "mcp_server/packaged/su_bridge/lib"
            force_include[str(runtime_skills_source)] = "mcp_server/packaged/runtime_skills"
            return

        if packaged_bridge.exists() and packaged_runtime_skills.exists():
            return

        searched = ", ".join(
            str(path)
            for path in (
                bridge_source,
                runtime_skills_source,
                packaged_bridge,
                packaged_runtime_skills,
            )
        )
        raise FileNotFoundError(f"Required build asset source not found. Searched: {searched}")
