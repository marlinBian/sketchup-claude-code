"""Tests for design_rules.json schema and helpers."""

import json
from pathlib import Path

from mcp_server.resources.design_rules_schema import (
    DESIGNER_PROFILE_ENV,
    create_designer_profile,
    create_default_design_rules,
    default_designer_profile_path,
    designer_profile_status,
    effective_design_rules,
    load_design_rules,
    merge_design_rules,
    save_design_rules,
    validate_design_rules,
)


def test_default_design_rules_are_valid():
    rules = create_default_design_rules()

    is_valid, errors = validate_design_rules(rules)

    assert is_valid is True
    assert errors == []
    assert rules["units"] == "mm"
    assert "bathroom" in rules["rule_sets"]


def test_bathroom_fixture_is_valid():
    fixture_path = Path(__file__).parent / "fixtures" / "bathroom" / "design_rules.json"

    data, errors = load_design_rules(fixture_path)

    assert errors == []
    assert data is not None
    assert data["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] == 600


def test_invalid_units_fail_validation():
    rules = create_default_design_rules()
    rules["units"] = "inches"

    is_valid, errors = validate_design_rules(rules)

    assert is_valid is False
    assert any("units" in error for error in errors)


def test_negative_clearance_fails_validation():
    rules = create_default_design_rules()
    rules["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = -1

    is_valid, errors = validate_design_rules(rules)

    assert is_valid is False
    assert any("toilet_front_clearance" in error for error in errors)


def test_load_invalid_json_reports_parse_error(tmp_path):
    path = tmp_path / "design_rules.json"
    path.write_text("{ invalid json }", encoding="utf-8")

    data, errors = load_design_rules(path)

    assert data is None
    assert len(errors) == 1
    assert "Invalid JSON" in errors[0]


def test_save_design_rules_creates_parent_directories(tmp_path):
    path = tmp_path / "project" / "design_rules.json"
    rules = create_default_design_rules()

    success, errors = save_design_rules(path, rules)

    assert success is True
    assert errors == []
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["units"] == "mm"


def test_default_designer_profile_path_uses_home(tmp_path):
    assert default_designer_profile_path(home=tmp_path) == (
        tmp_path / ".sketchup-agent-harness" / "design_rules.json"
    )


def test_create_designer_profile_writes_valid_profile(tmp_path):
    profile_path = tmp_path / "profile" / "design_rules.json"

    result = create_designer_profile(profile_path)
    data, errors = load_design_rules(profile_path)

    assert errors == []
    assert data is not None
    assert result["created"] is True
    assert result["path"] == str(profile_path)
    assert result["shell_export"] == f"export {DESIGNER_PROFILE_ENV}={profile_path}"
    assert data["source"] == "designer_profile"


def test_create_designer_profile_requires_force_for_existing_profile(tmp_path):
    profile_path = tmp_path / "design_rules.json"
    create_designer_profile(profile_path)

    try:
        create_designer_profile(profile_path)
    except FileExistsError as error:
        assert "Designer profile already exists" in str(error)
    else:
        raise AssertionError("Expected FileExistsError")


def test_designer_profile_status_uses_env(monkeypatch, tmp_path):
    profile_path = tmp_path / "design_rules.json"
    create_designer_profile(profile_path)
    monkeypatch.setenv(DESIGNER_PROFILE_ENV, str(profile_path))

    status = designer_profile_status()

    assert status["configured"] is True
    assert status["exists"] is True
    assert status["valid"] is True
    assert status["source"] == "designer_profile"


def test_cli_designer_profile_commands(tmp_path, capsys):
    from mcp_server.cli import main

    profile_path = tmp_path / "profile_rules.json"

    init_code = main(["profile-init", "--path", str(profile_path)])
    init_output = json.loads(capsys.readouterr().out)
    status_code = main(["profile-status", "--path", str(profile_path)])
    status_output = json.loads(capsys.readouterr().out)

    assert init_code == 0
    assert init_output["path"] == str(profile_path)
    assert status_code == 0
    assert status_output["exists"] is True
    assert status_output["valid"] is True


def test_merge_design_rules_applies_profile_then_project_overrides():
    profile = create_default_design_rules()
    profile["source"] = "designer_profile"
    profile["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = 750
    profile["preferences"]["lighting_temperature"] = "3000K"
    project = create_default_design_rules()
    project["source"] = "project"
    project["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = 900

    rules = merge_design_rules(profile, project)

    assert rules["source"] == "built_in_default+designer_profile+project"
    assert rules["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] == 900
    assert rules["preferences"]["lighting_temperature"] == "3000K"


def test_effective_design_rules_uses_configured_designer_profile(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile_rules.json"
    profile = create_default_design_rules()
    profile["source"] = "designer_profile"
    profile["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = 750
    save_design_rules(profile_path, profile)
    monkeypatch.setenv(DESIGNER_PROFILE_ENV, str(profile_path))

    rules, errors = effective_design_rules()

    assert errors == []
    assert rules is not None
    assert rules["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] == 750


def test_effective_design_rules_project_overrides_profile(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile_rules.json"
    profile = create_default_design_rules()
    profile["source"] = "designer_profile"
    profile["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = 750
    save_design_rules(profile_path, profile)
    monkeypatch.setenv(DESIGNER_PROFILE_ENV, str(profile_path))
    project_path = tmp_path / "project"
    project = create_default_design_rules()
    project["source"] = "project"
    project["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] = 900
    save_design_rules(project_path / "design_rules.json", project)

    rules, errors = effective_design_rules(project_path)

    assert errors == []
    assert rules is not None
    assert rules["rule_sets"]["bathroom"]["clearances"]["toilet_front_clearance"] == 900


def test_effective_design_rules_reports_missing_configured_profile(monkeypatch, tmp_path):
    monkeypatch.setenv(DESIGNER_PROFILE_ENV, str(tmp_path / "missing.json"))

    rules, errors = effective_design_rules()

    assert rules is None
    assert errors
    assert "Designer profile not found" in errors[0]
