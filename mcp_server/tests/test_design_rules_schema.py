"""Tests for design_rules.json schema and helpers."""

import json
from pathlib import Path

from mcp_server.resources.design_rules_schema import (
    DESIGNER_PROFILE_ENV,
    create_default_design_rules,
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
