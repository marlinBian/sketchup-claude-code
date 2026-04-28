"""Design Model Schema and Validation."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft7Validator


# JSON Schema for Design Model
DESIGN_MODEL_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Design Model",
    "description": "Schema for SketchUp Agent Harness Design Model",
    "type": "object",
    "required": ["version", "project_name", "components"],
    "properties": {
        "version": {
            "type": "string",
            "description": "Design model schema version",
        },
        "project_name": {
            "type": "string",
            "description": "Name of the design project",
        },
        "created_at": {
            "type": "string",
            "format": "date-time",
            "description": "ISO8601 timestamp of creation",
        },
        "updated_at": {
            "type": "string",
            "format": "date-time",
            "description": "ISO8601 timestamp of last update",
        },
        "metadata": {
            "type": "object",
            "properties": {
                "style": {
                    "type": "string",
                    "description": "Design style (e.g., scandinavian, modern_industrial)",
                },
                "ceiling_height": {
                    "type": "number",
                    "description": "Ceiling height in mm",
                    "minimum": 0,
                },
                "units": {
                    "type": "string",
                    "enum": ["mm"],
                    "description": "Fixed value: mm",
                },
            },
        },
        "spaces": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_]+$": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "living_room",
                                "bedroom",
                                "kitchen",
                                "bathroom",
                                "dining_room",
                                "office",
                                "storage",
                                "hallway",
                                "balcony",
                                "garden",
                                "other",
                            ],
                        },
                        "bounds": {
                            "type": "object",
                            "properties": {
                                "min": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                },
                                "max": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                },
                            },
                            "required": ["min", "max"],
                        },
                        "center": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                    },
                    "required": ["type", "bounds"],
                },
            },
        },
        "components": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_]+$": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Component type (sofa, table, chair, ...)",
                        },
                        "name": {
                            "type": "string",
                            "description": "Human-readable name",
                        },
                        "component_ref": {
                            "type": "string",
                            "description": "Component manifest ID used to create this instance",
                        },
                        "position": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 3,
                            "maxItems": 3,
                            "description": "[x, y, z] coordinates in mm",
                        },
                        "dimensions": {
                            "type": "object",
                            "properties": {
                                "width": {"type": "number", "minimum": 0},
                                "depth": {"type": "number", "minimum": 0},
                                "height": {"type": "number", "minimum": 0},
                            },
                        },
                        "bounds": {
                            "type": "object",
                            "properties": {
                                "min": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                },
                                "max": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                },
                            },
                            "required": ["min", "max"],
                        },
                        "anchors": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z0-9_]+$": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                },
                            },
                        },
                        "clearance": {
                            "type": "object",
                            "patternProperties": {
                                "^[a-zA-Z0-9_]+$": {
                                    "type": "number",
                                    "minimum": 0,
                                },
                            },
                        },
                        "rotation": {
                            "type": "number",
                            "description": "Rotation angle in degrees",
                        },
                        "layer": {
                            "type": "string",
                            "enum": [
                                "Walls",
                                "Floors",
                                "Furniture",
                                "Fixtures",
                                "Lighting",
                                "Windows",
                                "Doors",
                                "Stairs",
                                "Ceiling",
                                "Other",
                            ],
                        },
                        "skp_path": {
                            "type": "string",
                            "description": "Optional path to .skp file",
                        },
                        "semantic_anchor": {
                            "type": "string",
                            "description": "Semantic anchor point name",
                        },
                        "relative_to": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "Parent component ID or null",
                        },
                        "created_at": {
                            "type": "string",
                            "format": "date-time",
                        },
                        "entity_id": {
                            "type": "string",
                            "description": "SketchUp entity ID after bridge execution",
                        },
                        "source": {
                            "type": "object",
                            "description": "Provenance for generated or imported instances",
                        },
                    },
                    "required": ["type", "name", "position"],
                },
            },
        },
        "lighting": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_]+$": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "chandelier",
                                "floor_lamp",
                                "spotlight",
                                "recessed_light",
                                "wall_sconce",
                                "desk_lamp",
                                "pendant_light",
                                "track_lighting",
                                "other",
                            ],
                        },
                        "position": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                        "relative_to": {
                            "type": "object",
                            "properties": {
                                "anchor": {"type": "string"},
                                "relationship": {
                                    "type": "string",
                                    "enum": [
                                        "above",
                                        "below",
                                        "left",
                                        "right",
                                        "front",
                                        "behind",
                                        "centered_on",
                                    ],
                                },
                                "height_offset": {"type": "number"},
                            },
                            "required": ["anchor", "relationship"],
                        },
                    },
                    "required": ["type", "position"],
                },
            },
        },
        "semantic_anchors": {
            "type": "object",
            "description": "Named anchor points for semantic positioning",
            "patternProperties": {
                "^[a-zA-Z0-9_]+$": {
                    "type": "object",
                    "patternProperties": {
                        "^[a-zA-Z0-9_]+$": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                    },
                },
            },
        },
        "layers": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_]+$": {
                    "type": "object",
                    "properties": {
                        "color": {
                            "type": "string",
                            "pattern": "^#[0-9A-Fa-f]{6}$",
                        },
                    },
                },
            },
        },
    },
}


def create_empty_template(project_name: str = "untitled") -> Dict[str, Any]:
    """Create an empty Design Model template.

    Args:
        project_name: Name for the new project

    Returns:
        Empty Design Model dictionary
    """
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "version": "1.0",
        "project_name": project_name,
        "created_at": now,
        "updated_at": now,
        "metadata": {
            "style": "",
            "ceiling_height": 2400,
            "units": "mm",
        },
        "spaces": {},
        "components": {},
        "lighting": {},
        "semantic_anchors": {},
        "layers": {},
    }


def validate_design_model(data: dict) -> Tuple[bool, List[str]]:
    """Validate design model data against schema.

    Args:
        data: Design model dictionary to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors: List[str] = []

    if data is None or not isinstance(data, dict):
        return False, ["Design model must be a dictionary"]

    validator = Draft7Validator(DESIGN_MODEL_SCHEMA)

    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors


def load_design_model(path: str) -> Tuple[Optional[dict], List[str]]:
    """Load and validate design model from file.

    Args:
        path: Path to design_model.json file

    Returns:
        Tuple of (design_model_data, error_messages)
        If file cannot be read or parsed, returns (None, errors)
    """
    errors: List[str] = []
    data: Optional[dict] = None

    file_path = Path(path)

    # Check file exists
    if not file_path.exists():
        return None, [f"File not found: {path}"]

    # Check file is readable
    if not file_path.is_file():
        return None, [f"Path is not a file: {path}"]

    # Try to read and parse JSON
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return None, [f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}"]
    except IOError as e:
        return None, [f"IO error reading file: {e}"]

    # Validate against schema
    if data is not None:
        is_valid, validation_errors = validate_design_model(data)
        if not is_valid:
            return None, validation_errors

    return data, []


def save_design_model(path: str, data: dict) -> Tuple[bool, List[str]]:
    """Save design model to file after validation.

    Args:
        path: Path to save design_model.json
        data: Design model dictionary to save

    Returns:
        Tuple of (success, error_messages)
    """
    errors: List[str] = []

    # Validate first
    is_valid, validation_errors = validate_design_model(data)
    if not is_valid:
        return False, validation_errors

    # Update the updated_at timestamp
    data["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    file_path = Path(path)

    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True, []
    except IOError as e:
        return False, [f"IO error writing file: {e}"]
