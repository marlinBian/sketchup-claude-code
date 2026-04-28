"""Tests for environment doctoring."""

import json

from mcp_server.cli import main
from mcp_server.doctor import run_doctor
from mcp_server.project_init import init_project


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

    assert result["ok"] is True
    assert project_check["ok"] is True
    assert bridge_install_check["ok"] is False
    assert bridge_install_check["severity"] == "warning"
    assert socket_check["ok"] is False
    assert socket_check["severity"] == "warning"


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
