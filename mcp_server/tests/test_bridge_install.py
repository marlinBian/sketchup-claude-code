"""Tests for SketchUp Ruby bridge installation helpers."""

import json

from mcp_server.bridge_install import (
    default_plugins_dir,
    install_bridge,
    installed_sketchup_plugin_dirs,
)
from mcp_server.cli import main


def make_bridge_source(tmp_path):
    source = tmp_path / "source" / "su_bridge"
    (source / "lib").mkdir(parents=True)
    (source / "lib" / "su_bridge.rb").write_text("# bridge\n", encoding="utf-8")
    (source / "vendor").mkdir()
    (source / "vendor" / "bundle.txt").write_text("ignore\n", encoding="utf-8")
    return source


def test_default_plugins_dir_uses_requested_sketchup_version(tmp_path):
    path = default_plugins_dir(sketchup_version="2025", home=tmp_path)

    assert path == (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp"
        / "SketchUp 2025"
        / "SketchUp"
        / "Plugins"
    )


def test_installed_sketchup_plugin_dirs_detects_existing_dirs(tmp_path):
    older = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp"
        / "SketchUp 2023"
        / "SketchUp"
        / "Plugins"
    )
    newer = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp"
        / "SketchUp 2025"
        / "SketchUp"
        / "Plugins"
    )
    older.mkdir(parents=True)
    newer.mkdir(parents=True)

    assert installed_sketchup_plugin_dirs(tmp_path) == [newer, older]


def test_install_bridge_copies_source_and_ignores_vendor(tmp_path):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "Plugins"

    result = install_bridge(
        plugins_dir=plugins_dir,
        source_dir=source,
    )

    assert result["installed"] is True
    assert (plugins_dir / "su_bridge" / "lib" / "su_bridge.rb").exists()
    assert not (plugins_dir / "su_bridge" / "vendor").exists()
    assert "SuBridge.start" in result["load_command"]


def test_install_bridge_dry_run_does_not_copy(tmp_path):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "Plugins"

    result = install_bridge(
        plugins_dir=plugins_dir,
        source_dir=source,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["installed"] is False
    assert not (plugins_dir / "su_bridge").exists()


def test_install_bridge_requires_force_for_existing_target(tmp_path):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "Plugins"
    install_bridge(plugins_dir=plugins_dir, source_dir=source)

    try:
        install_bridge(plugins_dir=plugins_dir, source_dir=source)
    except FileExistsError as error:
        assert "--force" in str(error)
    else:
        raise AssertionError("Expected FileExistsError")


def test_cli_install_bridge_outputs_json(tmp_path, capsys):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "Plugins"

    exit_code = main(
        [
            "install-bridge",
            "--plugins-dir",
            str(plugins_dir),
            "--source-dir",
            str(source),
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["installed"] is True
    assert (plugins_dir / "su_bridge" / "lib" / "su_bridge.rb").exists()
