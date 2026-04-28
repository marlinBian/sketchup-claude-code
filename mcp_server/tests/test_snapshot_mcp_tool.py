"""Tests for project snapshot MCP tool wrapper."""

import json

import pytest


class FakeBridge:
    """Capture the JSON-RPC request and return a successful capture."""

    def __init__(self):
        self.request = None
        self.connected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def send(self, request):
        self.request = request
        return {
            "result": {
                "capture_info": {
                    "output_path": request["params"]["payload"]["output_path"],
                    "width": request["params"]["payload"]["width"],
                    "height": request["params"]["payload"]["height"],
                    "view_preset": request["params"]["payload"]["view_preset"],
                }
            }
        }


@pytest.mark.asyncio
async def test_capture_project_snapshot_records_manifest(monkeypatch, tmp_path):
    from mcp_server import server

    bridge = FakeBridge()
    monkeypatch.setattr(server, "SocketBridge", lambda: bridge)

    response = await server.capture_project_snapshot(
        project_path=str(tmp_path),
        view_preset="top",
        label="review",
        width=1200,
        height=800,
        prompt="review this bathroom",
    )
    data = json.loads(response.text)
    manifest = json.loads((tmp_path / "snapshots" / "manifest.json").read_text())

    assert bridge.request["params"]["operation_type"] == "capture_design"
    assert data["snapshot"]["file"].startswith("snapshots/")
    assert data["snapshot"]["prompt"] == "review this bathroom"
    assert data["snapshot"]["capture"]["width"] == 1200
    assert manifest["snapshots"][0]["advisory"] is True


@pytest.mark.asyncio
async def test_record_visual_feedback_appends_structured_review(tmp_path):
    from mcp_server import server

    response = await server.record_visual_feedback(
        project_path=str(tmp_path),
        summary="The shower area feels visually crowded.",
        source_snapshot_id="review",
        source_snapshot_file="snapshots/review.png",
        prompt="make the bathroom feel lighter",
        renderer_tool="vision_review",
        renderer_model="manual",
        actions=[
            {
                "type": "material",
                "target": "wall_finish",
                "intent": "Use a lighter wall finish.",
                "status": "proposed",
                "payload": {"material": "warm_white_tile"},
                "rationale": "Reduce visual weight while preserving layout.",
            }
        ],
    )
    data = json.loads(response.text)
    manifest = json.loads((tmp_path / "snapshots" / "manifest.json").read_text())

    assert data["advisory"] is True
    assert data["visual_feedback"]["source_snapshot_id"] == "review"
    assert data["visual_feedback"]["actions"][0]["type"] == "material"
    assert manifest["reviews"][0]["summary"] == "The shower area feels visually crowded."
    assert manifest["snapshots"] == []
