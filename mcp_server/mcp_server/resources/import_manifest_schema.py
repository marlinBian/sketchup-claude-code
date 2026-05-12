"""Import manifest schema and project-local import provenance helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator


IMPORT_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Import Manifest",
    "description": "Project-local provenance record for imported source material.",
    "type": "object",
    "required": [
        "version",
        "import_id",
        "created_at",
        "updated_at",
        "status",
        "source",
        "scale",
        "processing_steps",
        "quality_flags",
    ],
    "properties": {
        "$schema": {"type": "string"},
        "version": {"type": "string"},
        "import_id": {"type": "string", "pattern": "^[a-zA-Z0-9_]+$"},
        "label": {"type": "string"},
        "created_at": {"type": "string"},
        "updated_at": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["registered", "imported", "repaired", "failed"],
        },
        "source": {
            "type": "object",
            "required": [
                "original_path",
                "stored_path",
                "filename",
                "extension",
                "source_type",
                "sha256",
                "size_bytes",
            ],
            "properties": {
                "original_path": {"type": "string"},
                "stored_path": {"type": "string"},
                "filename": {"type": "string"},
                "extension": {"type": "string"},
                "source_type": {
                    "type": "string",
                    "enum": [
                        "dwg",
                        "dxf",
                        "pdf",
                        "image",
                        "sketchup",
                        "chat_image_attachment",
                        "unknown",
                    ],
                },
                "file_backed": {"type": "boolean"},
                "sha256": {"type": "string"},
                "size_bytes": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": True,
        },
        "scale": {
            "type": "object",
            "required": ["units", "source", "confidence"],
            "properties": {
                "units": {"type": "string", "enum": ["mm"]},
                "source": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "width": {"type": "number", "minimum": 0},
                "depth": {"type": "number", "minimum": 0},
                "scale_factor": {"type": "number", "minimum": 0},
                "history": {"type": "array", "items": {"type": "object"}},
            },
            "additionalProperties": True,
        },
        "generated_model": {
            "type": "object",
            "properties": {
                "design_model": {"type": "string"},
                "space_ids": {"type": "array", "items": {"type": "string"}},
                "wall_ids": {"type": "array", "items": {"type": "string"}},
                "opening_ids": {"type": "array", "items": {"type": "string"}},
                "changed_model_ids": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": True,
        },
        "processing_steps": {"type": "array", "items": {"type": "object"}},
        "quality_flags": {"type": "array", "items": {"type": "string"}},
        "repair_history": {"type": "array", "items": {"type": "object"}},
        "timing": {
            "type": "object",
            "required": [
                "schema_version",
                "trace_type",
                "scope",
                "started_at",
                "ended_at",
                "total_ms",
                "phases",
                "budget",
            ],
            "properties": {
                "schema_version": {"type": "string"},
                "trace_type": {"type": "string"},
                "scope": {"type": "string"},
                "started_at": {"type": "string"},
                "ended_at": {"type": "string"},
                "total_ms": {"type": "number", "minimum": 0},
                "classification_totals_ms": {
                    "type": "object",
                    "additionalProperties": {"type": "number", "minimum": 0},
                },
                "phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "name",
                            "classification",
                            "status",
                            "duration_ms",
                        ],
                        "properties": {
                            "name": {"type": "string"},
                            "label": {"type": "string"},
                            "classification": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["success", "skipped", "failed"],
                            },
                            "duration_ms": {"type": "number", "minimum": 0},
                            "budget_ms": {"type": "number", "minimum": 0},
                            "within_budget": {"type": "boolean"},
                            "skip_reason": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                },
                "slowest_phase": {"type": ["object", "null"]},
                "budget": {
                    "type": "object",
                    "required": ["total_budget_ms", "within_budget"],
                    "properties": {
                        "total_budget_ms": {"type": "number", "minimum": 0},
                        "within_budget": {"type": "boolean"},
                        "total_within_budget": {"type": "boolean"},
                        "over_budget_phases": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "additionalProperties": True,
                },
                "diagnostics": {"type": "object"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


def utc_now() -> str:
    """Return an ISO8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_import_manifest(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate an import manifest against the project contract."""
    validator = Draft7Validator(IMPORT_MANIFEST_SCHEMA)
    errors: list[str] = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")
    return len(errors) == 0, errors


def create_import_manifest(
    *,
    import_id: str,
    source: dict[str, Any],
    label: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a registered import manifest."""
    timestamp = created_at or utc_now()
    manifest: dict[str, Any] = {
        "version": "1.0",
        "import_id": import_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "status": "registered",
        "source": source,
        "scale": {
            "units": "mm",
            "source": "unspecified",
            "confidence": 0,
        },
        "processing_steps": [
            {
                "step": "register_source",
                "status": "success",
                "created_at": timestamp,
            }
        ],
        "quality_flags": ["scale_missing"],
    }
    if label:
        manifest["label"] = label
    return manifest


def load_import_manifest(path: str | Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load and validate one import manifest."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        return None, [f"File not found: {manifest_path}"]
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return None, [
            f"Invalid JSON: {error.msg} at line {error.lineno}, column {error.colno}"
        ]
    is_valid, errors = validate_import_manifest(data)
    if not is_valid:
        return None, errors
    return data, []


def save_import_manifest(path: str | Path, data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate and save one import manifest."""
    data["updated_at"] = utc_now()
    is_valid, errors = validate_import_manifest(data)
    if not is_valid:
        return False, errors
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True, []
