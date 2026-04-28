"""Tests for project report generation."""

import json
import re

import pytest

from mcp_server.project_init import init_project
from mcp_server.tools.report_tools import generate_project_report


def test_generate_project_report_writes_english_markdown(tmp_path):
    init_project(tmp_path, template="bathroom")

    result = generate_project_report(tmp_path)
    report = (tmp_path / "reports" / "design_report.md").read_text(encoding="utf-8")

    assert result["component_count"] == 4
    assert result["asset_count"] == 5
    assert "# " in report
    assert "Project Summary" in report
    assert "Effective Design Rules" in report
    assert not re.search(r"[\u4e00-\u9fff]", report)


@pytest.mark.asyncio
async def test_generate_project_report_mcp_tool(tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="bathroom")

    response = await server.generate_project_report(str(tmp_path))
    data = json.loads(response.text)

    assert data["report_path"].endswith("reports/design_report.md")
    assert data["component_count"] == 4


@pytest.mark.asyncio
async def test_generate_report_compat_tool_returns_json(tmp_path):
    from mcp_server import server

    project_dir = tmp_path / "designs"
    project_name = "bathroom"
    init_project(project_dir / project_name, template="bathroom")

    response = await server.generate_report(
        project_name=project_name,
        project_dir=str(project_dir),
    )
    data = json.loads(response.text)

    assert data["project_path"].endswith("designs/bathroom")
    assert data["report_path"].endswith("reports/design_report.md")
