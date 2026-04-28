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


@pytest.mark.asyncio
async def test_visual_feedback_can_be_listed_and_marked_applied(tmp_path):
    from mcp_server import server

    response = await server.record_visual_feedback(
        project_path=str(tmp_path),
        summary="The lighting should be warmer.",
        actions=[
            {
                "type": "lighting",
                "target": "ceiling_light_001",
                "intent": "Set a warmer color temperature.",
                "status": "proposed",
                "payload": {"temperature": 3000},
            }
        ],
    )
    review_id = json.loads(response.text)["visual_feedback"]["id"]

    list_response = await server.list_visual_feedback(project_path=str(tmp_path))
    list_data = json.loads(list_response.text)
    update_response = await server.update_visual_feedback_action_status(
        project_path=str(tmp_path),
        review_id=review_id,
        action_index=0,
        status="applied",
    )
    update_data = json.loads(update_response.text)
    manifest = json.loads((tmp_path / "snapshots" / "manifest.json").read_text())

    assert list_data["reviews"][0]["id"] == review_id
    assert update_data["status"] == "applied"
    assert update_data["action"]["status"] == "applied"
    assert manifest["reviews"][0]["actions"][0]["status"] == "applied"


@pytest.mark.asyncio
async def test_update_visual_feedback_action_status_rejects_unknown_status(tmp_path):
    from mcp_server import server

    response = await server.update_visual_feedback_action_status(
        project_path=str(tmp_path),
        review_id="missing",
        action_index=0,
        status="done",
    )

    assert response.text == (
        "Visual feedback failed: status must be one of proposed, accepted, "
        "rejected, applied."
    )
