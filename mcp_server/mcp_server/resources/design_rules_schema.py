"""Design rules schema and validation helpers."""

import copy
import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from mcp_server.resources.project_files import design_rules_path

DESIGNER_PROFILE_ENV = "SKETCHUP_AGENT_DESIGN_RULES"

DESIGN_RULES_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Design Rules",
    "description": "Project-level constraints and preferences in millimeters.",
    "type": "object",
    "required": ["version", "units", "rule_sets"],
    "properties": {
        "version": {"type": "string"},
        "units": {
            "type": "string",
            "enum": ["mm"],
            "description": "All numeric spatial values are millimeters.",
        },
        "source": {
            "type": "string",
            "description": "Rule source identifier for validation reports.",
        },
        "rule_sets": {
            "type": "object",
            "minProperties": 1,
            "patternProperties": {
                "^[a-zA-Z0-9_]+$": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "clearances": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z0-9_]+$": {
                                    "type": "number",
                                    "minimum": 0,
                                },
                            },
                            "additionalProperties": False,
                        },
                        "fixture_dimensions": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z0-9_]+$": {
                                    "type": "object",
                                    "required": ["width", "depth", "height"],
                                    "properties": {
                                        "width": {"type": "number", "minimum": 0},
                                        "depth": {"type": "number", "minimum": 0},
                                        "height": {"type": "number", "minimum": 0},
                                    },
                                    "additionalProperties": False,
                                },
                            },
                            "additionalProperties": False,
                        },
                        "notes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "preferences": {"type": "object"},
    },
    "additionalProperties": False,
}


def create_default_design_rules() -> dict[str, Any]:
    """Create the built-in design rules template for a new project."""
    return {
        "version": "1.0",
        "units": "mm",
        "source": "built_in_default",
        "rule_sets": {
            "bathroom": {
                "description": "Seed bathroom clearances for the first vertical slice.",
                "clearances": {
                    "circulation_min_width": 700,
                    "door_swing_clearance": 700,
                    "toilet_front_clearance": 600,
                    "toilet_side_clearance": 250,
                    "vanity_front_clearance": 700,
                    "mirror_mount_center_height": 1500,
                },
                "fixture_dimensions": {
                    "toilet_floor_mounted_basic": {
                        "width": 380,
                        "depth": 700,
                        "height": 760,
                    },
                    "vanity_wall_600": {
                        "width": 600,
                        "depth": 460,
                        "height": 850,
                    },
                    "bathroom_door_700": {
                        "width": 700,
                        "depth": 40,
                        "height": 2100,
                    },
                },
                "notes": [
                    "Rules are conservative seed values, not jurisdictional code.",
                    "Project rules may override them when a designer has a preference.",
                ],
            },
        },
        "preferences": {},
    }


def designer_profile_path_from_env() -> Path | None:
    """Return the configured designer profile rules path, if any."""
    value = os.environ.get(DESIGNER_PROFILE_ENV)
    if not value:
        return None
    return Path(value).expanduser()


def merge_design_rules(*rule_layers: dict[str, Any] | None) -> dict[str, Any]:
    """Merge design rule layers from lowest to highest precedence."""
    merged = copy.deepcopy(create_default_design_rules())
    sources = [merged.get("source", "built_in_default")]

    for layer in rule_layers:
        if not layer:
            continue
        sources.append(str(layer.get("source", "unknown")))
        merged["version"] = layer.get("version", merged["version"])
        merged["units"] = layer.get("units", merged["units"])
        merged.setdefault("preferences", {}).update(layer.get("preferences", {}))

        for rule_set_name, rule_set in layer.get("rule_sets", {}).items():
            target_rule_set = merged.setdefault("rule_sets", {}).setdefault(
                rule_set_name,
                {},
            )
            if "description" in rule_set:
                target_rule_set["description"] = rule_set["description"]
            if "clearances" in rule_set:
                target_rule_set.setdefault("clearances", {}).update(
                    rule_set["clearances"]
                )
            if "fixture_dimensions" in rule_set:
                target_rule_set.setdefault("fixture_dimensions", {}).update(
                    copy.deepcopy(rule_set["fixture_dimensions"])
                )
            if "notes" in rule_set:
                existing_notes = target_rule_set.setdefault("notes", [])
                for note in rule_set["notes"]:
                    if note not in existing_notes:
                        existing_notes.append(note)

    merged["source"] = "+".join(sources)
    return merged


def load_designer_profile_rules(
    profile_path: str | Path | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Load configured designer profile rules, if a profile is configured."""
    path = (
        Path(profile_path).expanduser()
        if profile_path
        else designer_profile_path_from_env()
    )
    if path is None:
        return None, []
    if not path.exists():
        return None, [f"Designer profile not found: {path}"]
    return load_design_rules(path)


def effective_design_rules(
    project_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return built-in rules merged with designer profile and project rules."""
    errors: list[str] = []
    profile_rules, profile_errors = load_designer_profile_rules(profile_path)
    errors.extend(profile_errors)

    project_rules = None
    if project_path is not None:
        path = design_rules_path(project_path)
        if path.exists():
            project_rules, project_errors = load_design_rules(path)
            errors.extend(project_errors)

    if errors:
        return None, errors

    merged = merge_design_rules(profile_rules, project_rules)
    is_valid, validation_errors = validate_design_rules(merged)
    if not is_valid:
        return None, validation_errors
    return merged, []


def validate_design_rules(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate design rules data against the schema."""
    if data is None or not isinstance(data, dict):
        return False, ["Design rules must be a dictionary"]

    validator = Draft7Validator(DESIGN_RULES_SCHEMA)
    errors: list[str] = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors


def load_design_rules(path: str | Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load and validate a design_rules.json file."""
    file_path = Path(path)
    if not file_path.exists():
        return None, [f"File not found: {file_path}"]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as error:
        return None, [
            f"Invalid JSON: {error.msg} at line {error.lineno}, column {error.colno}"
        ]
    except OSError as error:
        return None, [f"IO error reading file: {error}"]

    is_valid, errors = validate_design_rules(data)
    if not is_valid:
        return None, errors

    return data, []


def save_design_rules(path: str | Path, data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Save design rules after schema validation."""
    is_valid, errors = validate_design_rules(data)
    if not is_valid:
        return False, errors

    file_path = Path(path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as error:
        return False, [f"IO error writing file: {error}"]

    return True, []
