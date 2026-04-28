"""Tests for environment doctoring."""

import json

from mcp_server.cli import main
from mcp_server.doctor import bridge_runtime_capability_check, run_doctor, sketchup_app_check
from mcp_server.project_init import init_project
from mcp_server.resources.design_rules_schema import (
    DESIGNER_PROFILE_ENV,
    create_default_design_rules,
    save_design_rules,
)


def test_doctor_reports_project_validation(tmp_path):
    project_path = tmp_path / "bathroom"
    init_project(project_path, template="bathroom")

    result = run_doctor(
        project_path=project_path,
        plugins_dir=tmp_path / "missing-plugins",
        socket_path=str(tmp_path / "missing.sock"),
    )

    project_check = next(check for check in result["checks"] if check["name"] == "project_validation")
    bridge_install_check = next(
        check for check in result["checks"] if check["name"] == "sketchup_bridge_install"
    )
    socket_check = next(check for check in result["checks"] if check["name"] == "bridge_socket")
    skills_check = next(check for check in result["checks"] if check["name"] == "runtime_skills")

    assert result["ok"] is True
    assert project_check["ok"] is True
    assert skills_check["ok"] is True
    assert bridge_install_check["ok"] is False
    assert bridge_install_check["severity"] == "warning"
    assert socket_check["ok"] is False
    assert socket_check["severity"] == "warning"


def test_doctor_warns_on_modified_runtime_skills(tmp_path):
    project_path = tmp_path / "bathroom"
    init_project(project_path, template="bathroom")
    skill_file = project_path / ".agents" / "skills" / "designer_workflow" / "SKILL.md"
    skill_file.write_text("# Local Edit\n", encoding="utf-8")

    result = run_doctor(
        project_path=project_path,
        plugins_dir=tmp_path / "missing-plugins",
        socket_path=str(tmp_path / "missing.sock"),
    )
    skills_check = next(check for check in result["checks"] if check["name"] == "runtime_skills")

    assert result["ok"] is True
    assert skills_check["ok"] is False
    assert skills_check["severity"] == "warning"
    assert skills_check["details"]["checks"]["codex"]["modified_files"] == [
        "designer_workflow/SKILL.md"
    ]
    assert "install-skills" in skills_check["message"]


def test_doctor_reports_configured_designer_profile(monkeypatch, tmp_path):
    profile_path = tmp_path / "profile_rules.json"
    save_design_rules(profile_path, create_default_design_rules())
    monkeypatch.setenv(DESIGNER_PROFILE_ENV, str(profile_path))

    result = run_doctor(
        plugins_dir=tmp_path / "missing-plugins",
        socket_path=str(tmp_path / "missing.sock"),
    )
    profile_check = next(check for check in result["checks"] if check["name"] == "designer_profile")

    assert result["ok"] is True
    assert profile_check["ok"] is True
    assert profile_check["details"]["configured"] is True
    assert profile_check["details"]["path"] == str(profile_path)


def test_doctor_fails_on_missing_configured_designer_profile(monkeypatch, tmp_path):
    monkeypatch.setenv(DESIGNER_PROFILE_ENV, str(tmp_path / "missing.json"))

    result = run_doctor(
        plugins_dir=tmp_path / "missing-plugins",
        socket_path=str(tmp_path / "missing.sock"),
    )
    profile_check = next(check for check in result["checks"] if check["name"] == "designer_profile")

    assert result["ok"] is False
    assert profile_check["ok"] is False
    assert profile_check["severity"] == "error"
    assert "Designer profile not found" in profile_check["message"]


def test_doctor_fails_on_invalid_project(tmp_path):
    project_path = tmp_path / "bad-project"
    project_path.mkdir()

    result = run_doctor(
        project_path=project_path,
        plugins_dir=tmp_path / "missing-plugins",
        socket_path=str(tmp_path / "missing.sock"),
    )

    project_check = next(check for check in result["checks"] if check["name"] == "project_validation")

    assert result["ok"] is False
    assert project_check["ok"] is False
    assert project_check["severity"] == "error"


def test_sketchup_app_check_warns_on_quarantined_app(monkeypatch, tmp_path):
    app = tmp_path / "Applications" / "SketchUp 2024" / "SketchUp.app"
    template = app / "Contents" / "Resources" / "en" / "Templates" / "Temp01b - Simple.skp"
    template.parent.mkdir(parents=True)
    template.write_text("template", encoding="utf-8")
    monkeypatch.setattr("mcp_server.doctor.sketchup_app_path", lambda version: app)
    monkeypatch.setattr(
        "mcp_server.doctor.quarantine_entries",
        lambda path: [f"{path}: com.apple.quarantine: test"],
    )

    result = sketchup_app_check("2024")

    assert result["ok"] is False
    assert result["severity"] == "warning"
    assert result["details"]["quarantine_present"] is True
    assert "launch-bridge --clear-quarantine" in result["message"]


def test_bridge_runtime_capability_check_skips_missing_socket(tmp_path):
    result = bridge_runtime_capability_check(socket_path=str(tmp_path / "missing.sock"))

    assert result["ok"] is True
    assert result["severity"] == "info"
    assert result["details"]["skipped"] is True


def test_bridge_runtime_capability_check_reports_supported_operations(
    monkeypatch,
    tmp_path,
):
    socket_path = tmp_path / "su_bridge.sock"
    socket_path.write_text("", encoding="utf-8")

    class FakeBridge:
        def __init__(self, config):
            self.config = config

        def send(self, data):
            operation_type = data["params"]["operation_type"]
            assert operation_type == "get_bridge_info"
            return {
                "result": {
                    "bridge_info": {
                        "version": "0.1.0",
                        "supported_operations": [
                            "get_bridge_info",
                            "get_scene_info",
                            "get_selection_info",
                        ],
                    }
                }
            }

        def disconnect(self):
            pass

    monkeypatch.setattr("mcp_server.doctor.SocketBridge", FakeBridge)

    result = bridge_runtime_capability_check(socket_path=str(socket_path))

    assert result["ok"] is True
    assert result["details"]["bridge_info"]["version"] == "0.1.0"
    assert result["details"]["required_operations"]["get_scene_info"]["ok"] is True
    assert result["details"]["required_operations"]["get_selection_info"]["ok"] is True


def test_bridge_runtime_capability_check_reports_missing_advertised_operation(
    monkeypatch,
    tmp_path,
):
    socket_path = tmp_path / "su_bridge.sock"
    socket_path.write_text("", encoding="utf-8")

    class FakeBridge:
        def __init__(self, config):
            self.config = config

        def send(self, data):
            operation_type = data["params"]["operation_type"]
            assert operation_type == "get_bridge_info"
            return {
                "result": {
                    "bridge_info": {
                        "version": "0.1.0",
                        "supported_operations": ["get_bridge_info", "get_scene_info"],
                    }
                }
            }

        def disconnect(self):
            pass

    monkeypatch.setattr("mcp_server.doctor.SocketBridge", FakeBridge)

    result = bridge_runtime_capability_check(socket_path=str(socket_path))

    assert result["ok"] is False
    assert "Restart SketchUp" in result["message"]
    assert result["details"]["bridge_info"]["version"] == "0.1.0"
    assert result["details"]["required_operations"]["get_scene_info"]["ok"] is True
    assert result["details"]["required_operations"]["get_selection_info"]["ok"] is False


def test_bridge_runtime_capability_check_reports_stale_bridge(
    monkeypatch,
    tmp_path,
):
    socket_path = tmp_path / "su_bridge.sock"
    socket_path.write_text("", encoding="utf-8")

    class FakeBridge:
        def __init__(self, config):
            self.config = config

        def send(self, data):
            operation_type = data["params"]["operation_type"]
            if operation_type == "get_bridge_info":
                return {
                    "error": {
                        "code": -32000,
                        "message": "Unknown operation_type: get_bridge_info",
                    }
                }
            if operation_type == "get_selection_info":
                return {
                    "error": {
                        "code": -32000,
                        "message": "Unknown operation_type: get_selection_info",
                    }
                }
            return {"result": {"scene_info": {}}}

        def disconnect(self):
            pass

    monkeypatch.setattr("mcp_server.doctor.SocketBridge", FakeBridge)

    result = bridge_runtime_capability_check(socket_path=str(socket_path))

    assert result["ok"] is False
    assert result["severity"] == "warning"
    assert "Restart SketchUp" in result["message"]
    assert (
        result["details"]["required_operations"]["get_selection_info"]["error"]
        == "Unknown operation_type: get_selection_info"
    )


def test_cli_doctor_outputs_json(tmp_path, capsys):
    project_path = tmp_path / "bathroom"
    init_project(project_path, template="bathroom")

    exit_code = main(
        [
            "doctor",
            str(project_path),
            "--plugins-dir",
            str(tmp_path / "missing-plugins"),
            "--socket-path",
            str(tmp_path / "missing.sock"),
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["ok"] is True
    assert any(check["name"] == "project_validation" for check in data["checks"])
