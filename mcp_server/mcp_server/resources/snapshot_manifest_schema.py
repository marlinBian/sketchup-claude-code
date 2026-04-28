"""Snapshot manifest schema and provenance helpers."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from mcp_server.resources.project_files import (
    DESIGN_MODEL_FILENAME,
    snapshot_manifest_path,
    snapshots_path,
)

SNAPSHOT_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Snapshot Manifest",
    "description": "Project-local provenance record for visual review artifacts.",
    "type": "object",
    "required": ["version", "snapshots"],
    "properties": {
        "$schema": {"type": "string"},
        "version": {"type": "string"},
        "snapshots": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "file",
                    "created_at",
                    "source_model",
                    "advisory",
                    "capture",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "file": {"type": "string"},
                    "created_at": {"type": "string"},
                    "source_model": {"type": "string"},
                    "advisory": {"type": "boolean"},
                    "prompt": {"type": "string"},
                    "capture": {
                        "type": "object",
                        "required": ["tool", "width", "height"],
                        "properties": {
                            "tool": {"type": "string"},
                            "view_preset": {"type": ["string", "null"]},
                            "width": {"type": "integer", "minimum": 1},
                            "height": {"type": "integer", "minimum": 1},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        },
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "created_at",
                    "source_model",
                    "advisory",
                    "summary",
                    "actions",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "created_at": {"type": "string"},
                    "source_model": {"type": "string"},
                    "advisory": {"type": "boolean"},
                    "source_snapshot_id": {"type": "string"},
                    "source_snapshot_file": {"type": "string"},
                    "prompt": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "renderer": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string"},
                            "model": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "summary": {"type": "string"},
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type", "target", "intent", "status"],
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "component",
                                        "geometry",
                                        "lighting",
                                        "material",
                                        "rule",
                                        "style",
                                        "camera",
                                        "note",
                                    ],
                                },
                                "target": {"type": "string"},
                                "intent": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": [
                                        "proposed",
                                        "accepted",
                                        "rejected",
                                        "applied",
                                    ],
                                },
                                "payload": {"type": "object"},
                                "rationale": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    },
                },
                "additionalProperties": False,
            },
        },
        "renders": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "file",
                    "created_at",
                    "source_model",
                    "advisory",
                    "prompt",
                    "renderer",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "file": {"type": "string"},
                    "created_at": {"type": "string"},
                    "source_model": {"type": "string"},
                    "advisory": {"type": "boolean"},
                    "source_snapshot_id": {"type": "string"},
                    "source_snapshot_file": {"type": "string"},
                    "prompt": {"type": "string"},
                    "renderer": {
                        "type": "object",
                        "required": ["tool"],
                        "properties": {
                            "tool": {"type": "string"},
                            "model": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "dimensions": {
                        "type": "object",
                        "required": ["width", "height"],
                        "properties": {
                            "width": {"type": "integer", "minimum": 1},
                            "height": {"type": "integer", "minimum": 1},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


def utc_now() -> str:
    """Return an ISO8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_filename_timestamp() -> str:
    """Return a compact UTC timestamp for snapshot filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_empty_snapshot_manifest() -> dict[str, Any]:
    """Create an empty snapshot manifest."""
    return {
        "version": "1.0",
        "snapshots": [],
        "reviews": [],
        "renders": [],
    }


def slugify_snapshot_label(value: str | None, fallback: str = "snapshot") -> str:
    """Return a filesystem-safe snapshot label."""
    if not value:
        return fallback
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug or fallback


def snapshot_output_path(
    project_path: str | Path,
    view_preset: str | None = None,
    label: str | None = None,
    timestamp: str | None = None,
) -> Path:
    """Return a deterministic project snapshot path."""
    created = timestamp or utc_filename_timestamp()
    name = slugify_snapshot_label(label or view_preset)
    return snapshots_path(project_path) / f"{created}_{name}.png"


def snapshot_entry(
    project_path: str | Path,
    output_path: str | Path,
    view_preset: str | None,
    width: int,
    height: int,
    prompt: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create one snapshot manifest entry."""
    root = Path(project_path)
    output = Path(output_path)
    timestamp = created_at or utc_now()
    try:
        relative_file = output.relative_to(root)
    except ValueError:
        relative_file = output

    entry: dict[str, Any] = {
        "id": output.stem,
        "file": str(relative_file),
        "created_at": timestamp,
        "source_model": DESIGN_MODEL_FILENAME,
        "advisory": True,
        "capture": {
            "tool": "capture_design",
            "view_preset": view_preset,
            "width": width,
            "height": height,
        },
    }
    if prompt:
        entry["prompt"] = prompt
    return entry


def visual_feedback_entry(
    summary: str,
    actions: list[dict[str, Any]],
    source_snapshot_id: str | None = None,
    source_snapshot_file: str | None = None,
    prompt: str | None = None,
    reviewer: str = "agent",
    renderer_tool: str | None = None,
    renderer_model: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create one advisory visual feedback action plan entry."""
    timestamp = created_at or utc_now()
    entry: dict[str, Any] = {
        "id": f"visual_review_{slugify_snapshot_label(timestamp)}",
        "created_at": timestamp,
        "source_model": DESIGN_MODEL_FILENAME,
        "advisory": True,
        "reviewer": reviewer,
        "summary": summary,
        "actions": actions,
    }
    if source_snapshot_id:
        entry["source_snapshot_id"] = source_snapshot_id
    if source_snapshot_file:
        entry["source_snapshot_file"] = source_snapshot_file
    if prompt:
        entry["prompt"] = prompt
    if renderer_tool or renderer_model:
        entry["renderer"] = {}
        if renderer_tool:
            entry["renderer"]["tool"] = renderer_tool
        if renderer_model:
            entry["renderer"]["model"] = renderer_model
    return entry


def render_artifact_entry(
    project_path: str | Path,
    artifact_path: str | Path,
    prompt: str,
    renderer_tool: str,
    renderer_model: str | None = None,
    source_snapshot_id: str | None = None,
    source_snapshot_file: str | None = None,
    width: int | None = None,
    height: int | None = None,
    label: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create one advisory generated/rendered visual artifact entry."""
    timestamp = created_at or utc_now()
    root = Path(project_path)
    artifact = Path(artifact_path)
    try:
        file_value = str(artifact.relative_to(root))
    except ValueError:
        file_value = str(artifact_path)

    if bool(width) != bool(height):
        raise ValueError("render artifact width and height must be provided together.")

    entry: dict[str, Any] = {
        "id": f"render_{slugify_snapshot_label(label or artifact.stem or timestamp)}",
        "file": file_value,
        "created_at": timestamp,
        "source_model": DESIGN_MODEL_FILENAME,
        "advisory": True,
        "prompt": prompt,
        "renderer": {
            "tool": renderer_tool,
        },
    }
    if renderer_model:
        entry["renderer"]["model"] = renderer_model
    if source_snapshot_id:
        entry["source_snapshot_id"] = source_snapshot_id
    if source_snapshot_file:
        entry["source_snapshot_file"] = source_snapshot_file
    if width is not None and height is not None:
        entry["dimensions"] = {"width": int(width), "height": int(height)}
    return entry


def validate_snapshot_manifest(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a snapshot manifest."""
    if data is None or not isinstance(data, dict):
        return False, ["Snapshot manifest must be a dictionary"]

    validator = Draft7Validator(SNAPSHOT_MANIFEST_SCHEMA)
    errors: list[str] = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors


def load_snapshot_manifest(path: str | Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load and validate a snapshot manifest."""
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

    is_valid, errors = validate_snapshot_manifest(data)
    if not is_valid:
        return None, errors

    return data, []


def append_snapshot_entry(
    project_path: str | Path,
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Append a snapshot entry to the project manifest."""
    manifest_path = snapshot_manifest_path(project_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if manifest_path.exists():
        manifest, errors = load_snapshot_manifest(manifest_path)
        if errors:
            raise ValueError("; ".join(errors))
        assert manifest is not None
    else:
        manifest = create_empty_snapshot_manifest()

    manifest["snapshots"].append(entry)
    is_valid, errors = validate_snapshot_manifest(manifest)
    if not is_valid:
        raise ValueError("; ".join(errors))

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def append_visual_feedback_entry(
    project_path: str | Path,
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Append a visual feedback action plan entry to the project manifest."""
    manifest_path = snapshot_manifest_path(project_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if manifest_path.exists():
        manifest, errors = load_snapshot_manifest(manifest_path)
        if errors:
            raise ValueError("; ".join(errors))
        assert manifest is not None
        manifest.setdefault("reviews", [])
    else:
        manifest = create_empty_snapshot_manifest()

    manifest["reviews"].append(entry)
    is_valid, errors = validate_snapshot_manifest(manifest)
    if not is_valid:
        raise ValueError("; ".join(errors))

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def append_render_artifact_entry(
    project_path: str | Path,
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Append a generated/rendered visual artifact to the project manifest."""
    manifest_path = snapshot_manifest_path(project_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if manifest_path.exists():
        manifest, errors = load_snapshot_manifest(manifest_path)
        if errors:
            raise ValueError("; ".join(errors))
        assert manifest is not None
        manifest.setdefault("renders", [])
    else:
        manifest = create_empty_snapshot_manifest()

    manifest["renders"].append(entry)
    is_valid, errors = validate_snapshot_manifest(manifest)
    if not is_valid:
        raise ValueError("; ".join(errors))

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
