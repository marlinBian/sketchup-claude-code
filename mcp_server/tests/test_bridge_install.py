"""Tests for SketchUp Ruby bridge installation helpers."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from mcp_server.bridge_install import (
    bridge_loader_content,
    default_plugins_dir,
    install_bridge,
    installed_sketchup_plugin_dirs,
    packaged_bridge_source,
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
        / "SketchUp 2025"
        / "SketchUp"
        / "Plugins"
    )


def test_packaged_bridge_source_points_to_installed_runtime():
    source = packaged_bridge_source()

    assert source.name == "su_bridge"
    assert source.parent.name == "packaged"


def test_installed_sketchup_plugin_dirs_detects_existing_dirs(tmp_path):
    older = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2023"
        / "SketchUp"
        / "Plugins"
    )
    newer = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2025"
        / "SketchUp"
        / "Plugins"
    )
    older.mkdir(parents=True)
    newer.mkdir(parents=True)

    assert installed_sketchup_plugin_dirs(tmp_path) == [newer, older]


def test_installed_sketchup_plugin_dirs_detects_legacy_layout(tmp_path):
    plugins_dir = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp"
        / "SketchUp 2024"
        / "SketchUp"
        / "Plugins"
    )
    plugins_dir.mkdir(parents=True)

    assert installed_sketchup_plugin_dirs(tmp_path) == [plugins_dir]


def test_install_bridge_copies_source_and_ignores_vendor(tmp_path):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "Plugins"

    result = install_bridge(
        plugins_dir=plugins_dir,
        source_dir=source,
    )

    assert result["installed"] is True
    assert result["loader_preference"]["exists"] is False
    assert (plugins_dir / "su_bridge" / "lib" / "su_bridge.rb").exists()
    assert (plugins_dir / "su_bridge.rb").exists()
    assert not (plugins_dir / "su_bridge" / "vendor").exists()
    assert result["load_command"] == f"load '{plugins_dir / 'su_bridge.rb'}'"
    assert "SuBridge.start" in (plugins_dir / "su_bridge.rb").read_text(encoding="utf-8")


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
    assert result["loader_preference"] is None
    assert result["target_exists"] is False
    assert result["loader_exists"] is False
    assert not (plugins_dir / "su_bridge").exists()
    assert not (plugins_dir / "su_bridge.rb").exists()


def test_install_bridge_dry_run_allows_existing_target(tmp_path):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "Plugins"
    install_bridge(plugins_dir=plugins_dir, source_dir=source)

    result = install_bridge(
        plugins_dir=plugins_dir,
        source_dir=source,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["installed"] is False
    assert result["target_exists"] is True
    assert result["loader_exists"] is True


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


def test_install_bridge_requires_force_for_existing_loader(tmp_path):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "Plugins"
    plugins_dir.mkdir()
    (plugins_dir / "su_bridge.rb").write_text("# old loader\n", encoding="utf-8")

    try:
        install_bridge(plugins_dir=plugins_dir, source_dir=source)
    except FileExistsError as error:
        assert "--force" in str(error)
    else:
        raise AssertionError("Expected FileExistsError")


def test_install_bridge_force_backs_up_existing_target(tmp_path):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "Plugins"
    install_bridge(plugins_dir=plugins_dir, source_dir=source)
    (plugins_dir / "su_bridge" / "old.txt").write_text("old\n", encoding="utf-8")
    (plugins_dir / "su_bridge.rb").write_text("# old loader\n", encoding="utf-8")

    result = install_bridge(
        plugins_dir=plugins_dir,
        source_dir=source,
        force=True,
    )
    backup_path = result["backup_path"]
    loader_backup_path = result["loader_backup_path"]

    assert result["installed"] is True
    assert backup_path is not None
    assert loader_backup_path is not None
    assert (plugins_dir / "su_bridge" / "lib" / "su_bridge.rb").exists()
    assert (plugins_dir / "su_bridge.rb").exists()
    assert (plugins_dir / "su_bridge").exists()
    assert (plugins_dir / Path(backup_path).name / "old.txt").exists()
    assert (plugins_dir / Path(loader_backup_path).name).read_text(encoding="utf-8") == "# old loader\n"


def test_install_bridge_enables_loader_preference_when_present(tmp_path):
    source = make_bridge_source(tmp_path)
    plugins_dir = tmp_path / "SketchUp 2024" / "SketchUp" / "Plugins"
    plugins_dir.mkdir(parents=True)
    preferences_path = plugins_dir.parent / "PrivatePreferences.json"
    preferences_path.write_text(
        json.dumps({"This Computer Only": {"Extensions": {}}}),
        encoding="utf-8",
    )

    result = install_bridge(
        plugins_dir=plugins_dir,
        source_dir=source,
    )
    preferences = json.loads(preferences_path.read_text(encoding="utf-8"))

    assert result["loader_preference"]["enabled"] is True
    assert result["loader_preference"]["updated"] is True
    assert preferences["This Computer Only"]["Extensions"]["su_bridge.rb"] == 1


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
    assert (plugins_dir / "su_bridge.rb").exists()


def test_bridge_loader_content_loads_installed_bridge():
    content = bridge_loader_content()

    assert 'File.expand_path("su_bridge/lib/su_bridge.rb", __dir__)' in content
    assert "SketchupExtension.new" in content
    assert "Sketchup.register_extension" in content
    assert "require bridge_path" in content
    assert "SuBridge.start" in content


def test_wheel_contains_packaged_bridge_runtime(tmp_path):
    if shutil.which("uv") is None:
        return

    project_root = Path(__file__).resolve().parents[1]
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [
            "uv",
            "build",
            "--wheel",
            "--out-dir",
            str(dist_dir),
            str(project_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(dist_dir.glob("*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

    assert "mcp_server/packaged/su_bridge/lib/su_bridge.rb" in names
    assert "mcp_server/packaged/su_bridge/lib/su_bridge/command_dispatcher.rb" in names
    assert not any("/vendor/" in name for name in names)
    assert not any("mcp_server/packaged/su_bridge/spec/" in name for name in names)
