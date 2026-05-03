"""Tests for import manifest schema and persistence."""

import json

from mcp_server.resources.import_manifest_schema import (
    create_import_manifest,
    load_import_manifest,
    save_import_manifest,
    validate_import_manifest,
)


def source_info():
    """Return a minimal source info fixture."""
    return {
        "original_path": "/tmp/floorplan.pdf",
        "stored_path": "imports/import_001/source/floorplan.pdf",
        "filename": "floorplan.pdf",
        "extension": ".pdf",
        "source_type": "pdf",
        "sha256": "abc123",
        "size_bytes": 12,
    }


def test_create_import_manifest_is_valid():
    manifest = create_import_manifest(
        import_id="import_001",
        source=source_info(),
        label="Floor plan",
    )

    valid, errors = validate_import_manifest(manifest)

    assert valid is True
    assert errors == []
    assert manifest["status"] == "registered"
    assert manifest["quality_flags"] == ["scale_missing"]


def test_import_manifest_validation_rejects_missing_source():
    manifest = create_import_manifest(import_id="import_001", source=source_info())
    del manifest["source"]["sha256"]

    valid, errors = validate_import_manifest(manifest)

    assert valid is False
    assert any("sha256" in error for error in errors)


def test_save_and_load_import_manifest(tmp_path):
    manifest = create_import_manifest(import_id="import_001", source=source_info())
    path = tmp_path / "imports" / "import_001" / "manifest.json"

    saved, save_errors = save_import_manifest(path, manifest)
    loaded, load_errors = load_import_manifest(path)

    assert saved is True
    assert save_errors == []
    assert load_errors == []
    assert loaded["import_id"] == "import_001"
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "registered"
