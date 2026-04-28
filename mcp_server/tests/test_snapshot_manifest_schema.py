"""Tests for snapshot manifest provenance helpers."""

import json

from mcp_server.resources.snapshot_manifest_schema import (
    append_render_artifact_entry,
    append_snapshot_entry,
    append_visual_feedback_entry,
    create_empty_snapshot_manifest,
    load_snapshot_manifest,
    render_artifact_entry,
    snapshot_entry,
    snapshot_output_path,
    validate_snapshot_manifest,
    visual_feedback_entry,
)


def test_empty_snapshot_manifest_is_valid():
    manifest = create_empty_snapshot_manifest()

    is_valid, errors = validate_snapshot_manifest(manifest)

    assert is_valid is True
    assert errors == []
    assert manifest["snapshots"] == []
    assert manifest["reviews"] == []
    assert manifest["renders"] == []


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
    assert loaded["reviews"] == []


def test_visual_feedback_entry_is_valid():
    entry = visual_feedback_entry(
        summary="The vanity looks too heavy for the small bathroom.",
        actions=[
            {
                "type": "component",
                "target": "vanity_001",
                "intent": "Replace with a narrower wall-mounted vanity.",
                "status": "proposed",
                "payload": {"component_ref": "vanity_wall_500"},
                "rationale": "Improve perceived circulation width.",
            }
        ],
        source_snapshot_id="top",
        source_snapshot_file="snapshots/top.png",
        prompt="make this feel lighter",
        renderer_tool="vision_review",
        renderer_model="manual",
        created_at="2026-04-28T01:02:03+00:00",
    )
    manifest = create_empty_snapshot_manifest()
    manifest["reviews"].append(entry)

    is_valid, errors = validate_snapshot_manifest(manifest)

    assert is_valid is True
    assert errors == []
    assert entry["advisory"] is True
    assert entry["actions"][0]["status"] == "proposed"
    assert entry["renderer"]["tool"] == "vision_review"


def test_append_visual_feedback_entry_creates_manifest(tmp_path):
    entry = visual_feedback_entry(
        summary="No visual change needed.",
        actions=[
            {
                "type": "note",
                "target": "project",
                "intent": "Keep the current composition.",
                "status": "proposed",
            }
        ],
        created_at="2026-04-28T01:02:03+00:00",
    )

    manifest = append_visual_feedback_entry(tmp_path, entry)
    loaded, errors = load_snapshot_manifest(tmp_path / "snapshots" / "manifest.json")

    assert errors == []
    assert loaded is not None
    assert manifest["reviews"][0]["summary"] == "No visual change needed."
    assert loaded["reviews"][0]["actions"][0]["type"] == "note"


def test_render_artifact_entry_is_valid(tmp_path):
    entry = render_artifact_entry(
        project_path=tmp_path,
        artifact_path=tmp_path / "snapshots" / "render.png",
        prompt="Render this bathroom in a warm minimal style.",
        renderer_tool="image_renderer",
        renderer_model="image-2",
        source_snapshot_id="top",
        source_snapshot_file="snapshots/top.png",
        width=1024,
        height=768,
        label="warm render",
        created_at="2026-04-28T01:02:03+00:00",
    )
    manifest = create_empty_snapshot_manifest()
    manifest["renders"].append(entry)

    is_valid, errors = validate_snapshot_manifest(manifest)

    assert is_valid is True
    assert errors == []
    assert entry["id"] == "render_warm-render"
    assert entry["file"] == "snapshots/render.png"
    assert entry["advisory"] is True
    assert entry["renderer"] == {"tool": "image_renderer", "model": "image-2"}
    assert entry["dimensions"] == {"width": 1024, "height": 768}


def test_append_render_artifact_entry_creates_manifest(tmp_path):
    entry = render_artifact_entry(
        project_path=tmp_path,
        artifact_path="https://example.com/render.png",
        prompt="Render the current model.",
        renderer_tool="external_renderer",
        created_at="2026-04-28T01:02:03+00:00",
    )

    manifest = append_render_artifact_entry(tmp_path, entry)
    loaded, errors = load_snapshot_manifest(tmp_path / "snapshots" / "manifest.json")

    assert errors == []
    assert loaded is not None
    assert manifest["renders"][0]["file"] == "https://example.com/render.png"
    assert loaded["renders"][0]["renderer"]["tool"] == "external_renderer"


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
