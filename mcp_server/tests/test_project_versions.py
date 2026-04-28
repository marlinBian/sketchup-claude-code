"""Tests for structured project version snapshots."""

import json

import pytest

from mcp_server.cli import main
from mcp_server.project_init import init_project
from mcp_server.project_versions import (
    list_project_versions,
    restore_project_version,
    save_project_version,
)


def test_save_project_version_copies_truth_files(tmp_path):
    init_project(tmp_path, template="bathroom")

    result = save_project_version(
        tmp_path,
        version_tag="draft_1",
        description="Initial bathroom draft",
    )
    version_path = tmp_path / "versions" / "draft_1"
    metadata = json.loads((version_path / "metadata.json").read_text(encoding="utf-8"))

    assert result["version"] == "draft_1"
    assert (version_path / "design_model.json").exists()
    assert (version_path / "design_rules.json").exists()
    assert (version_path / "assets.lock.json").exists()
    assert (version_path / "component_library.json").exists()
    assert (version_path / "snapshots" / "manifest.json").exists()
    assert metadata["description"] == "Initial bathroom draft"


def test_save_project_version_rejects_unsafe_tag(tmp_path):
    init_project(tmp_path, template="bathroom")

    try:
        save_project_version(tmp_path, version_tag="../bad")
    except ValueError as error:
        assert "Version tag" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_list_project_versions_reads_metadata(tmp_path):
    init_project(tmp_path, template="bathroom")
    save_project_version(tmp_path, version_tag="draft_1")

    result = list_project_versions(tmp_path)

    assert result["count"] == 1
    assert result["versions"][0]["version"] == "draft_1"


def test_restore_project_version_requires_explicit_overwrite(tmp_path):
    init_project(tmp_path, template="bathroom")
    save_project_version(tmp_path, version_tag="draft_1")

    try:
        restore_project_version(tmp_path, version_tag="draft_1")
    except ValueError as error:
        assert "overwrite_current=True" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_restore_project_version_replaces_current_truth(tmp_path):
    init_project(tmp_path, project_name="Original", template="bathroom")
    save_project_version(tmp_path, version_tag="draft_1")
    design_model_path = tmp_path / "design_model.json"
    design_model = json.loads(design_model_path.read_text(encoding="utf-8"))
    design_model["project_name"] = "Changed"
    design_model_path.write_text(json.dumps(design_model), encoding="utf-8")

    result = restore_project_version(
        tmp_path,
        version_tag="draft_1",
        overwrite_current=True,
    )
    restored = json.loads(design_model_path.read_text(encoding="utf-8"))

    assert "design_model.json" in result["restored_files"]
    assert restored["project_name"] == "Original"


@pytest.mark.asyncio
async def test_project_version_mcp_tools(tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="bathroom")

    save_response = await server.save_project_version(
        project_path=str(tmp_path),
        version_tag="draft_1",
    )
    restore_guard = await server.restore_project_version(
        project_path=str(tmp_path),
        version_tag="draft_1",
    )
    list_response = await server.list_project_versions(project_path=str(tmp_path))
    save_data = json.loads(save_response.text)
    list_data = json.loads(list_response.text)

    assert save_data["version"] == "draft_1"
    assert "overwrite_current=True" in restore_guard.text
    assert list_data["count"] == 1


def test_cli_project_version_commands(tmp_path, capsys):
    init_project(tmp_path, template="bathroom")

    save_exit = main(["save-version", str(tmp_path), "draft_1"])
    save_output = capsys.readouterr()
    save_data = json.loads(save_output.out)
    list_exit = main(["list-versions", str(tmp_path)])
    list_output = capsys.readouterr()
    list_data = json.loads(list_output.out)
    restore_exit = main(["restore-version", str(tmp_path), "draft_1", "--force"])
    restore_output = capsys.readouterr()
    restore_data = json.loads(restore_output.out)

    assert save_exit == 0
    assert save_data["version"] == "draft_1"
    assert list_exit == 0
    assert list_data["versions"][0]["version"] == "draft_1"
    assert restore_exit == 0
    assert "design_model.json" in restore_data["restored_files"]
