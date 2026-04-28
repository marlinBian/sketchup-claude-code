"""Tests for snapshot manifest provenance helpers."""

import json

from mcp_server.resources.snapshot_manifest_schema import (
    append_snapshot_entry,
    create_empty_snapshot_manifest,
    load_snapshot_manifest,
    snapshot_entry,
    snapshot_output_path,
    validate_snapshot_manifest,
)


def test_empty_snapshot_manifest_is_valid():
    manifest = create_empty_snapshot_manifest()

    is_valid, errors = validate_snapshot_manifest(manifest)

    assert is_valid is True
    assert errors == []
    assert manifest["snapshots"] == []


def test_snapshot_output_path_uses_project_snapshots_dir(tmp_path):
    output_path = snapshot_output_path(
        tmp_path,
        view_preset="top",
        timestamp="20260428T010203Z",
    )

    assert output_path == tmp_path / "snapshots" / "20260428T010203Z_top.png"


def test_snapshot_entry_is_valid(tmp_path):
    entry = snapshot_entry(
        project_path=tmp_path,
        output_path=tmp_path / "snapshots" / "top.png",
        view_preset="top",
        width=1200,
        height=800,
        prompt="review the bathroom layout",
        created_at="2026-04-28T01:02:03+00:00",
    )
    manifest = create_empty_snapshot_manifest()
    manifest["snapshots"].append(entry)

    is_valid, errors = validate_snapshot_manifest(manifest)

    assert is_valid is True
    assert errors == []
    assert entry["file"] == "snapshots/top.png"
    assert entry["advisory"] is True
    assert entry["capture"]["tool"] == "capture_design"


def test_append_snapshot_entry_creates_manifest(tmp_path):
    entry = snapshot_entry(
        project_path=tmp_path,
        output_path=tmp_path / "snapshots" / "top.png",
        view_preset="top",
        width=1200,
        height=800,
        created_at="2026-04-28T01:02:03+00:00",
    )

    manifest = append_snapshot_entry(tmp_path, entry)
    loaded, errors = load_snapshot_manifest(tmp_path / "snapshots" / "manifest.json")

    assert manifest["snapshots"][0]["id"] == "top"
    assert errors == []
    assert loaded is not None
    assert loaded["snapshots"][0]["file"] == "snapshots/top.png"


def test_invalid_manifest_missing_capture_fails_validation():
    manifest = create_empty_snapshot_manifest()
    manifest["snapshots"].append(
        {
            "id": "bad",
            "file": "snapshots/bad.png",
            "created_at": "2026-04-28T01:02:03+00:00",
            "source_model": "design_model.json",
            "advisory": True,
        }
    )

    is_valid, errors = validate_snapshot_manifest(manifest)

    assert is_valid is False
    assert any("capture" in error for error in errors)


def test_load_snapshot_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(create_empty_snapshot_manifest(), indent=2) + "\n",
        encoding="utf-8",
    )

    data, errors = load_snapshot_manifest(manifest_path)

    assert errors == []
    assert data is not None
    assert data["version"] == "1.0"
