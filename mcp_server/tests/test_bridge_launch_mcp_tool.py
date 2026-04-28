"""Tests for agent-facing SketchUp bridge launch tools."""

import json

import mcp_server.server as server


async def test_launch_sketchup_bridge_returns_structured_result(monkeypatch):
    def fake_launch_bridge(**kwargs):
        assert kwargs["sketchup_version"] == "2024"
        assert kwargs["socket_path"] == "/tmp/test-su.sock"
        assert kwargs["clear_app_quarantine"] is True
        assert kwargs["suppress_app_update_check"] is True
        return {
            "app_path": "/Applications/SketchUp 2024/SketchUp.app",
            "sketchup_version": "2024",
            "socket_path": kwargs["socket_path"],
            "socket_ready": True,
            "possible_blockers": [],
        }

    monkeypatch.setattr(server, "launch_bridge", fake_launch_bridge)

    response = await server.launch_sketchup_bridge(
        sketchup_version="2024",
        socket_path="/tmp/test-su.sock",
        clear_quarantine=True,
        suppress_update_check=True,
    )
    data = json.loads(response.text)

    assert data["socket_ready"] is True
    assert data["sketchup_version"] == "2024"


async def test_launch_sketchup_bridge_reports_launch_errors(monkeypatch):
    def fake_launch_bridge(**kwargs):
        raise FileNotFoundError("SketchUp app was not found.")

    monkeypatch.setattr(server, "launch_bridge", fake_launch_bridge)

    response = await server.launch_sketchup_bridge(sketchup_version="2030")

    assert response.text == (
        "SketchUp bridge launch failed: SketchUp app was not found."
    )
