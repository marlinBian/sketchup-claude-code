"""Tests for designer project initialization."""

import json

from mcp_server.cli import main
from mcp_server.project_init import init_project
from mcp_server.resources.design_rules_schema import (
    DESIGNER_PROFILE_ENV,
    create_default_design_rules,
    save_design_rules,
)


def test_init_project_empty_template_creates_workspace_files(tmp_path):
    result = init_project(tmp_path / "my-design", project_name="My Design")
    project_path = tmp_path / "my-design"

    assert result["template"] == "empty"
    assert (project_path / "design_model.json").exists()
    assert (project_path / "design_rules.json").exists()
    assert (project_path / "assets.lock.json").exists()
    assert (project_path / "assets" / "components").is_dir()
    assert (project_path / ".mcp.json").exists()
    assert (project_path / "AGENTS.md").exists()
    assert (project_path / "CLAUDE.md").exists()
    assert (project_path / ".agents" / "skills" / "bathroom_planning" / "SKILL.md").exists()
    assert (project_path / ".claude" / "skills" / "bathroom_planning" / "SKILL.md").exists()
    assert (project_path / "snapshots").is_dir()
    assert (project_path / "snapshots" / "manifest.json").exists()

    design_model = json.loads((project_path / "design_model.json").read_text())
    assets_lock = json.loads((project_path / "assets.lock.json").read_text())
    snapshot_manifest = json.loads(
        (project_path / "snapshots" / "manifest.json").read_text()
    )
    mcp_config = json.loads((project_path / ".mcp.json").read_text())
    assert design_model["project_name"] == "My Design"
    assert assets_lock["cache"]["root"] == "assets/components"
    assert assets_lock["assets"] == []
    assert snapshot_manifest["snapshots"] == []
    assert mcp_config["mcpServers"]["sketchup-mcp"]["command"] == "sketchup-agent-mcp"
    assert "design_model.json" in (project_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "design_rules.json" in (project_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "codex_runtime_skills" in result["files"]
    assert "claude_runtime_skills" in result["files"]
    assert result["runtime_skills"]["installed"] is True


def test_init_project_bathroom_template_creates_seed_bathroom(tmp_path):
    result = init_project(tmp_path / "bathroom", template="bathroom")
    project_path = tmp_path / "bathroom"

    design_model = json.loads((project_path / "design_model.json").read_text())
    assets_lock = json.loads((project_path / "assets.lock.json").read_text())
    locked_ids = {asset["component_id"] for asset in assets_lock["assets"]}

    assert result["template"] == "bathroom"
    assert design_model["spaces"]["bathroom_001"]["type"] == "bathroom"
    assert "toilet_001" in design_model["components"]
    assert "toilet_floor_mounted_basic" in locked_ids
    assert "vanity_wall_600" in locked_ids
    assert "ceiling_light_basic" in locked_ids
    assert (project_path / "assets" / "components").is_dir()
    assert (project_path / "snapshots" / "manifest.json").exists()
    assert (project_path / "AGENTS.md").exists()
    assert (project_path / "CLAUDE.md").exists()
    assert (project_path / ".agents" / "skills" / "designer_workflow" / "SKILL.md").exists()
    assert (project_path / ".claude" / "skills" / "designer_workflow" / "SKILL.md").exists()


def test_init_project_applies_configured_designer_profile(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile_rules.json"
    profile = create_default_design_rules()
    profile["source"] = "designer_profile"
    profile["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = 750
    save_design_rules(profile_path, profile)
    monkeypatch.setenv(DESIGNER_PROFILE_ENV, str(profile_path))

    init_project(tmp_path / "profiled", template="bathroom")
    rules = json.loads((tmp_path / "profiled" / "design_rules.json").read_text())

    assert rules["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] == 750


def test_init_project_refuses_to_overwrite_existing_files(tmp_path):
    project_path = tmp_path / "existing"
    init_project(project_path)

    try:
        init_project(project_path)
    except FileExistsError as error:
        assert "design_model.json" in str(error)
    else:
        raise AssertionError("Expected FileExistsError")


def test_init_project_force_overwrites_existing_files(tmp_path):
    project_path = tmp_path / "existing"
    init_project(project_path, project_name="Original")

    result = init_project(project_path, project_name="Updated", overwrite=True)
    design_model = json.loads((project_path / "design_model.json").read_text())

    assert result["project_name"] == "Updated"
    assert design_model["project_name"] == "Updated"


def test_cli_init_outputs_json(tmp_path, capsys):
    exit_code = main(["init", str(tmp_path / "cli-project"), "--template", "bathroom"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["template"] == "bathroom"
    assert (tmp_path / "cli-project" / "design_model.json").exists()


def test_cli_validate_outputs_json(tmp_path, capsys):
    project_path = tmp_path / "cli-project"
    init_project(project_path, template="bathroom")

    exit_code = main(["validate", str(project_path)])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["ok"] is True


def test_cli_smoke_outputs_json(tmp_path, capsys):
    exit_code = main(["smoke", str(tmp_path / "smoke"), "--force"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["ok"] is True
    assert data["headless_plan"]["valid"] is True
