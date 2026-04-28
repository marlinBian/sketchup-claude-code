"""Component library manifest schema and validation helpers."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

POINT3_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 3,
    "maxItems": 3,
}

DIMENSIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["width", "depth", "height"],
    "properties": {
        "width": {"type": "number", "minimum": 0},
        "depth": {"type": "number", "minimum": 0},
        "height": {"type": "number", "minimum": 0},
    },
    "additionalProperties": False,
}

COMPONENT_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Component Library Manifest",
    "description": "Semantic component registry for agent placement.",
    "type": "object",
    "required": ["version", "components"],
    "properties": {
        "$schema": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "name",
                    "category",
                    "dimensions",
                    "bounds",
                    "insertion_point",
                    "anchors",
                    "clearance",
                    "assets",
                    "license",
                    "aliases",
                ],
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-zA-Z0-9_]+$"},
                    "name": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "furniture",
                            "fixture",
                            "lighting",
                            "decor",
                            "opening",
                            "appliance",
                            "other",
                        ],
                    },
                    "subcategory": {"type": "string"},
                    "dimensions": DIMENSIONS_SCHEMA,
                    "bounds": {
                        "type": "object",
                        "required": ["min", "max"],
                        "properties": {
                            "min": POINT3_SCHEMA,
                            "max": POINT3_SCHEMA,
                        },
                        "additionalProperties": False,
                    },
                    "insertion_point": {
                        "type": "object",
                        "required": ["offset", "description"],
                        "properties": {
                            "offset": POINT3_SCHEMA,
                            "description": {"type": "string"},
                            "face_direction": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "anchors": {
                        "type": "object",
                        "minProperties": 1,
                        "patternProperties": {
                            "^[a-zA-Z0-9_]+$": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "clearance": {
                        "type": "object",
                        "patternProperties": {
                            "^[a-zA-Z0-9_]+$": {"type": "number", "minimum": 0},
                        },
                        "additionalProperties": False,
                    },
                    "assets": {
                        "type": "object",
                        "required": ["skp_path"],
                        "properties": {
                            "skp_path": {"type": "string"},
                            "thumbnail": {"type": "string"},
                            "procedural_fallback": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "license": {
                        "type": "object",
                        "required": ["type", "source"],
                        "properties": {
                            "type": {"type": "string"},
                            "source": {"type": "string"},
                            "author": {"type": "string"},
                            "url": {"type": "string"},
                            "redistribution": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "aliases": {
                        "type": "object",
                        "properties": {
                            "en": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "zh-CN": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "additionalProperties": False,
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "materials": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "additionalProperties": False,
            },
        },
        "placement_rules": {"type": "object"},
        "categories": {"type": "object"},
    },
    "additionalProperties": False,
}


def validate_component_library(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a component library manifest."""
    if data is None or not isinstance(data, dict):
        return False, ["Component library must be a dictionary"]

    validator = Draft7Validator(COMPONENT_MANIFEST_SCHEMA)
    errors: list[str] = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors


def create_empty_component_library(
    description: str = "Project-local semantic component library.",
) -> dict[str, Any]:
    """Create an empty component library manifest."""
    return {
        "version": "1.0",
        "description": description,
        "components": [],
    }


def load_component_library(path: str | Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load and validate a component library manifest."""
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

    is_valid, errors = validate_component_library(data)
    if not is_valid:
        return None, errors

    return data, []


def save_component_library(
    path: str | Path,
    data: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Save a component library manifest after validation."""
    is_valid, errors = validate_component_library(data)
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


def merge_component_libraries(*libraries: dict[str, Any] | None) -> dict[str, Any]:
    """Merge component libraries, with later libraries replacing duplicate IDs."""
    merged = {
        "version": "1.0",
        "description": "Effective component library.",
        "components": [],
    }
    index: dict[str, dict[str, Any]] = {}

    for library in libraries:
        if not library:
            continue
        for component in library.get("components", []):
            component_id = component.get("id")
            if not isinstance(component_id, str) or not component_id:
                continue
            index[component_id] = component

    merged["components"] = [index[key] for key in sorted(index)]
    return merged
