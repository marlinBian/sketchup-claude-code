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
    installed_sketchup_app_versions,
    installed_sketchup_plugin_dirs,
    launch_bridge,
    packaged_bridge_source,
    prepare_launch_model,
    quarantine_entries,
    sketchup_app_path,
    sketchup_preferences_dir,
    sketchup_template_path,
    sketchup_version_from_app_path,
    sketchup_version_from_name,
    suppress_update_check,
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


def test_sketchup_version_from_name_extracts_year():
    assert sketchup_version_from_name("SketchUp 2024") == "2024"
    assert sketchup_version_from_name("SketchUp 2025.app") == "2025"
    assert sketchup_version_from_name("SketchUp") is None


def test_installed_sketchup_app_versions_detects_app_layouts(tmp_path):
    applications_dir = tmp_path / "Applications"
    (applications_dir / "SketchUp 2024" / "SketchUp.app").mkdir(parents=True)
    (applications_dir / "SketchUp 2025.app").mkdir(parents=True)
    (applications_dir / "SketchUp Viewer.app").mkdir(parents=True)

    assert installed_sketchup_app_versions(applications_dir) == ["2025", "2024"]


def test_sketchup_app_path_returns_newest_or_requested_app(tmp_path):
    applications_dir = tmp_path / "Applications"
    nested = applications_dir / "SketchUp 2024" / "SketchUp.app"
    direct = applications_dir / "SketchUp 2025.app"
    nested.mkdir(parents=True)
    direct.mkdir(parents=True)

    assert sketchup_app_path(applications_dir=applications_dir) == direct
    assert sketchup_app_path("2024", applications_dir=applications_dir) == nested
    assert sketchup_app_path("2023", applications_dir=applications_dir) is None


def test_sketchup_version_from_app_path_infers_nested_version():
    assert (
        sketchup_version_from_app_path("/Applications/SketchUp 2024/SketchUp.app")
        == "2024"
    )
    assert sketchup_version_from_app_path("/Applications/SketchUp.app") is None


def test_default_plugins_dir_prefers_installed_app_over_stale_plugin_dir(tmp_path):
    applications_dir = tmp_path / "Applications"
    (applications_dir / "SketchUp 2024" / "SketchUp.app").mkdir(parents=True)
    stale_plugins_dir = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2026"
        / "SketchUp"
        / "Plugins"
    )
    stale_plugins_dir.mkdir(parents=True)

    path = default_plugins_dir(home=tmp_path, applications_dir=applications_dir)

    assert path == (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2024"
        / "SketchUp"
        / "Plugins"
    )


def test_default_plugins_dir_falls_back_to_canonical_2024_path(tmp_path):
    path = default_plugins_dir(home=tmp_path, applications_dir=tmp_path / "missing")

    assert path == (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2024"
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


def test_installed_sketchup_plugin_dirs_prefers_installed_app_version(tmp_path):
    applications_dir = tmp_path / "Applications"
    (applications_dir / "SketchUp 2024" / "SketchUp.app").mkdir(parents=True)
    stale_newer = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2026"
        / "SketchUp"
        / "Plugins"
    )
    installed_app_plugins = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2024"
        / "SketchUp"
        / "Plugins"
    )
    stale_newer.mkdir(parents=True)
    installed_app_plugins.mkdir(parents=True)

    assert installed_sketchup_plugin_dirs(
        tmp_path,
        applications_dir=applications_dir,
    ) == [installed_app_plugins, stale_newer]


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


def test_sketchup_template_path_prefers_english_simple_template(tmp_path):
    app = tmp_path / "SketchUp 2024" / "SketchUp.app"
    preferred = app / "Contents" / "Resources" / "en-US" / "Templates" / "Temp01b - Simple.skp"
    fallback = app / "Contents" / "Resources" / "zh-cn" / "Templates" / "Temp01b - Simple.skp"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("fallback", encoding="utf-8")
    preferred.parent.mkdir(parents=True)
    preferred.write_text("preferred", encoding="utf-8")

    assert sketchup_template_path(app) == preferred


def test_prepare_launch_model_copies_bundled_template(tmp_path):
    app = tmp_path / "SketchUp 2024" / "SketchUp.app"
    template = app / "Contents" / "Resources" / "en" / "Templates" / "Temp01b - Simple.skp"
    template.parent.mkdir(parents=True)
    template.write_text("template", encoding="utf-8")

    result = prepare_launch_model(app)

    assert result["copied_template"] is True
    assert result["template_source"] == str(template)
    assert Path(result["model_path"]).read_text(encoding="utf-8") == "template"


def test_prepare_launch_model_uses_unique_template_copy(tmp_path):
    app = tmp_path / "SketchUp 2024" / "SketchUp.app"
    template = app / "Contents" / "Resources" / "en" / "Templates" / "Temp01b - Simple.skp"
    template.parent.mkdir(parents=True)
    template.write_text("template", encoding="utf-8")

    first = prepare_launch_model(app)
    second = prepare_launch_model(app)

    assert first["model_path"] != second["model_path"]
    assert Path(first["model_path"]).read_text(encoding="utf-8") == "template"
    assert Path(second["model_path"]).read_text(encoding="utf-8") == "template"


def test_prepare_launch_model_uses_explicit_model(tmp_path):
    app = tmp_path / "SketchUp 2024" / "SketchUp.app"
    model = tmp_path / "model.skp"
    model.write_text("model", encoding="utf-8")

    result = prepare_launch_model(app, model)

    assert result["copied_template"] is False
    assert result["template_source"] is None
    assert result["model_path"] == str(model.resolve())


def test_quarantine_entries_returns_empty_when_xattr_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("mcp_server.bridge_install.shutil.which", lambda command: None)

    assert quarantine_entries(tmp_path) == []


def test_sketchup_preferences_dir_uses_requested_version(tmp_path):
    assert sketchup_preferences_dir("2025", home=tmp_path) == (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2025"
        / "SketchUp"
    )


def test_suppress_update_check_updates_existing_preferences(tmp_path):
    preferences_dir = sketchup_preferences_dir("2024", home=tmp_path)
    preferences_dir.mkdir(parents=True)
    private_path = preferences_dir / "PrivatePreferences.json"
    shared_path = preferences_dir / "SharedPreferences.json"
    private_path.write_text(
        json.dumps(
            {
                "This Computer Only": {
                    "AutoUpdate": {"RemindOn": "2026-04-29T00:00:00"},
                    "Common": {"SuppressVersionWarning": False},
                    "Preferences": {"LastUpdateCheck": 0.0},
                }
            }
        ),
        encoding="utf-8",
    )
    shared_path.write_text(
        json.dumps(
            {
                "Shared for All Computers": {
                    "Preferences": {"CheckForUpdates": True}
                }
            }
        ),
        encoding="utf-8",
    )

    result = suppress_update_check("2024", home=tmp_path)
    private_data = json.loads(private_path.read_text(encoding="utf-8"))
    shared_data = json.loads(shared_path.read_text(encoding="utf-8"))

    assert result["updated"] is True
    assert private_data["This Computer Only"]["AutoUpdate"]["RemindOn"] == (
        "2099-01-01T00:00:00"
    )
    assert private_data["This Computer Only"]["Common"]["SuppressVersionWarning"] is True
    assert shared_data["Shared for All Computers"]["Preferences"]["CheckForUpdates"] is False


def test_launch_bridge_opens_model_and_waits_for_socket(monkeypatch, tmp_path):
    app = tmp_path / "Applications" / "SketchUp 2024" / "SketchUp.app"
    template = app / "Contents" / "Resources" / "en" / "Templates" / "Temp01b - Simple.skp"
    template.parent.mkdir(parents=True)
    template.write_text("template", encoding="utf-8")
    socket_path = tmp_path / "su_bridge.sock"
    calls = []

    def fake_run(command, check=False, capture_output=True, text=True):
        calls.append(command)
        socket_path.write_text("", encoding="utf-8")

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("mcp_server.bridge_install.subprocess.run", fake_run)
    monkeypatch.setattr("mcp_server.bridge_install.quarantine_entries", lambda path: [])
    preferences_dir = (
        tmp_path
        / "Library"
        / "Application Support"
        / "SketchUp 2024"
        / "SketchUp"
    )
    monkeypatch.setattr(
        "mcp_server.bridge_install.suppress_update_check",
        lambda version: {
            "preferences_dir": str(preferences_dir),
            "updated": True,
            "files": [],
        },
    )

    result = launch_bridge(
        sketchup_version="2024",
        app_path=app,
        socket_path=socket_path,
        timeout=1,
        suppress_app_update_check=True,
    )

    assert result["socket_ready"] is True
    assert result["copied_template"] is True
    assert result["sketchup_version"] == "2024"
    assert result["update_check_suppressed"]["preferences_dir"].endswith(
        "SketchUp 2024/SketchUp"
    )
    assert calls[-1][:3] == ["open", "-a", str(app.resolve())]


def test_launch_bridge_reports_timeout_blockers(monkeypatch, tmp_path):
    app = tmp_path / "Applications" / "SketchUp 2024" / "SketchUp.app"
    template = app / "Contents" / "Resources" / "en" / "Templates" / "Temp01b - Simple.skp"
    template.parent.mkdir(parents=True)
    template.write_text("template", encoding="utf-8")
    socket_path = tmp_path / "missing.sock"

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        "mcp_server.bridge_install.subprocess.run",
        lambda *args, **kwargs: Result(),
    )
    monkeypatch.setattr("mcp_server.bridge_install.quarantine_entries", lambda path: [])

    result = launch_bridge(
        app_path=app,
        socket_path=socket_path,
        timeout=0,
    )

    assert result["socket_ready"] is False
    assert result["sketchup_version"] == "2024"
    assert any("welcome screen" in blocker for blocker in result["possible_blockers"])


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


def test_cli_launch_bridge_outputs_json(monkeypatch, capsys):
    def fake_launch_bridge(**kwargs):
        assert kwargs["sketchup_version"] == "2024"
        assert kwargs["clear_app_quarantine"] is True
        assert kwargs["suppress_app_update_check"] is True
        return {
            "socket_ready": True,
            "socket_path": kwargs["socket_path"],
            "app_path": "/Applications/SketchUp 2024/SketchUp.app",
        }

    monkeypatch.setattr("mcp_server.cli.launch_bridge", fake_launch_bridge)

    exit_code = main(
        [
            "launch-bridge",
            "--sketchup-version",
            "2024",
            "--socket-path",
            "/tmp/test.sock",
            "--clear-quarantine",
            "--suppress-update-check",
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["socket_ready"] is True
    assert data["socket_path"] == "/tmp/test.sock"


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
