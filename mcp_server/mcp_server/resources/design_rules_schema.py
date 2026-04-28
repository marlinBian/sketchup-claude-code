"""Design rules schema and validation helpers."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

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
