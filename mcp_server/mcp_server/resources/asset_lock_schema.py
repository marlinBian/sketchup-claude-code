"""Project asset lock schema and helpers."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

ASSET_LOCK_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Project Asset Lock",
    "description": "Project-local record of semantic components used by a design.",
    "type": "object",
    "required": ["version", "cache", "assets"],
    "properties": {
        "$schema": {"type": "string"},
        "version": {"type": "string"},
        "cache": {
            "type": "object",
            "required": ["root", "mode"],
            "properties": {
                "root": {"type": "string"},
                "mode": {"type": "string", "enum": ["on_demand"]},
            },
            "additionalProperties": False,
        },
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "component_id",
                    "component_name",
                    "category",
                    "used_by",
                    "source",
                    "paths",
                    "cache",
                ],
                "properties": {
                    "component_id": {"type": "string"},
                    "component_name": {"type": "string"},
                    "category": {"type": "string"},
                    "subcategory": {"type": "string"},
                    "used_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "source": {
                        "type": "object",
                        "required": ["kind", "license"],
                        "properties": {
                            "kind": {"type": "string"},
                            "license": {"type": "string"},
                            "author": {"type": "string"},
                            "url": {"type": "string"},
                            "redistribution": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "paths": {
                        "type": "object",
                        "properties": {
                            "skp": {"type": "string"},
                            "thumbnail": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "cache": {
                        "type": "object",
                        "required": ["status", "path"],
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": ["referenced", "cached", "missing"],
                            },
                            "path": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "procedural_fallback": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


def create_empty_assets_lock(cache_root: str = "assets/components") -> dict[str, Any]:
    """Create an empty project asset lock."""
    return {
        "version": "1.0",
        "cache": {
            "root": cache_root,
            "mode": "on_demand",
        },
        "assets": [],
    }


def component_refs_from_design_model(design_model: dict[str, Any]) -> dict[str, list[str]]:
    """Return component registry refs and design IDs that use them."""
    refs: dict[str, list[str]] = {}

    for design_id, component in design_model.get("components", {}).items():
        component_ref = component.get("component_ref")
        if isinstance(component_ref, str) and component_ref:
            refs.setdefault(component_ref, []).append(str(design_id))

    for design_id, lighting in design_model.get("lighting", {}).items():
        component_ref = lighting.get("component_ref")
        if isinstance(component_ref, str) and component_ref:
            refs.setdefault(component_ref, []).append(str(design_id))

    return refs


def _component_index(component_library: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(component["id"]): component
        for component in component_library.get("components", [])
        if component.get("id")
    }


def _entry_for_missing_component(
    component_id: str,
    used_by: list[str],
    cache_root: str,
) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "component_name": component_id,
        "category": "other",
        "used_by": sorted(used_by),
        "source": {
            "kind": "unknown",
            "license": "unknown",
            "redistribution": "Component metadata was not found in the registry.",
        },
        "paths": {},
        "cache": {
            "status": "missing",
            "path": f"{cache_root}/{component_id}.skp",
        },
    }


def asset_lock_entry(
    component: dict[str, Any],
    used_by: list[str],
    cache_root: str = "assets/components",
    project_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create one asset lock entry from component manifest metadata."""
    license_info = component.get("license", {})
    assets = component.get("assets", {})
    cache_path = f"{cache_root}/{component['id']}.skp"
    cache_status = "referenced"
    if project_path is not None and (Path(project_path) / cache_path).exists():
        cache_status = "cached"

    paths: dict[str, str] = {}
    if assets.get("skp_path"):
        paths["skp"] = str(assets["skp_path"])
    if assets.get("thumbnail"):
        paths["thumbnail"] = str(assets["thumbnail"])

    entry: dict[str, Any] = {
        "component_id": str(component["id"]),
        "component_name": str(component.get("name", component["id"])),
        "category": str(component.get("category", "other")),
        "used_by": sorted(used_by),
        "source": {
            "kind": str(license_info.get("source", "unknown")),
            "license": str(license_info.get("type", "unknown")),
        },
        "paths": paths,
        "cache": {
            "status": cache_status,
            "path": cache_path,
        },
    }

    for source_key in ("author", "url", "redistribution"):
        if license_info.get(source_key):
            entry["source"][source_key] = str(license_info[source_key])

    if component.get("subcategory"):
        entry["subcategory"] = str(component["subcategory"])

    procedural_fallback = assets.get("procedural_fallback")
    if procedural_fallback:
        entry["procedural_fallback"] = str(procedural_fallback)

    return entry


def build_assets_lock(
    design_model: dict[str, Any],
    component_library: dict[str, Any],
    cache_root: str = "assets/components",
    project_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a project lock from design model component references."""
    lock = create_empty_assets_lock(cache_root=cache_root)
    components = _component_index(component_library)
    refs = component_refs_from_design_model(design_model)

    for component_id, used_by in sorted(refs.items()):
        component = components.get(component_id)
        if component is None:
            entry = _entry_for_missing_component(component_id, used_by, cache_root)
        else:
            entry = asset_lock_entry(
                component,
                used_by,
                cache_root=cache_root,
                project_path=project_path,
            )
        lock["assets"].append(entry)

    return lock


def validate_assets_lock(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a project asset lock document."""
    if data is None or not isinstance(data, dict):
        return False, ["Asset lock must be a dictionary"]

    validator = Draft7Validator(ASSET_LOCK_SCHEMA)
    errors: list[str] = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors


def load_assets_lock(path: str | Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load and validate an asset lock file."""
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

    is_valid, errors = validate_assets_lock(data)
    if not is_valid:
        return None, errors

    return data, []
