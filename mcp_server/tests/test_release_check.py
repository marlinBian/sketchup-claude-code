"""Tests for release smoke checks."""

import json

from mcp_server.release_check import (
    bridge_install_dry_run_check,
    manifest_json_check,
    run_release_check,
)


def test_manifest_json_check_accepts_repo_manifests():
    result = manifest_json_check()

    assert result["ok"] is True
    assert len(result["details"]["manifests"]) == 5


def test_bridge_install_dry_run_check_does_not_install(tmp_path):
    result = bridge_install_dry_run_check(tmp_path / "Plugins")

    assert result["ok"] is True
    assert result["details"]["dry_run"] is True
    assert result["details"]["installed"] is False
    assert not (tmp_path / "Plugins" / "su_bridge").exists()


def test_run_release_check_uses_shared_smoke_paths(tmp_path):
    result = run_release_check(
        project_path=tmp_path / "release-project",
        plugins_dir=tmp_path / "Plugins",
    )

    check_names = {check["name"] for check in result["checks"]}
    assert result["ok"] is True
    assert check_names == {
        "manifest_json",
        "mcp_startup",
        "product_smoke",
        "bridge_install_dry_run",
    }
    assert (tmp_path / "release-project" / "design_model.json").exists()
    assert not (tmp_path / "Plugins" / "su_bridge").exists()


def test_cli_release_check_outputs_json(tmp_path, capsys):
    from mcp_server.cli import main

    exit_code = main(
        [
            "release-check",
            "--project-path",
            str(tmp_path / "release-project"),
            "--plugins-dir",
            str(tmp_path / "Plugins"),
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["ok"] is True
    assert {check["name"] for check in data["checks"]} >= {"product_smoke"}
