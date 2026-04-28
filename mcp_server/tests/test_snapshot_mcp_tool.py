"""Tests for project snapshot MCP tool wrapper."""

import json

import pytest

from mcp_server.project_init import init_project


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


@pytest.mark.asyncio
async def test_apply_visual_feedback_component_action_updates_project_truth(tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="empty")
    await server.add_component_instance(
        project_path=str(tmp_path),
        component_id="toilet_floor_mounted_basic",
        position_x=500,
        position_y=700,
        position_z=0,
        instance_id="fixture_001",
    )
    response = await server.record_visual_feedback(
        project_path=str(tmp_path),
        summary="The fixture should become a compact wall vanity.",
        actions=[
            {
                "type": "component",
                "target": "fixture_001",
                "intent": "Replace the fixture with a wall vanity.",
                "status": "accepted",
                "payload": {
                    "component_ref": "vanity_wall_600",
                    "position": [1200, 0, 0],
                    "rotation": 90,
                },
            }
        ],
    )
    review_id = json.loads(response.text)["visual_feedback"]["id"]

    apply_response = await server.apply_visual_feedback_action(
        project_path=str(tmp_path),
        review_id=review_id,
        action_index=0,
    )
    data = json.loads(apply_response.text)
    design_model = json.loads((tmp_path / "design_model.json").read_text())
    asset_lock = json.loads((tmp_path / "assets.lock.json").read_text())
    manifest = json.loads((tmp_path / "snapshots" / "manifest.json").read_text())

    assert data["status"] == "applied"
    assert design_model["components"]["fixture_001"]["component_ref"] == "vanity_wall_600"
    assert design_model["components"]["fixture_001"]["position"] == [1200.0, 0.0, 0.0]
    assert design_model["components"]["fixture_001"]["rotation"] == 90
    assert design_model["components"]["fixture_001"]["dimensions"]["width"] == 600
    assert asset_lock["assets"][0]["component_id"] == "vanity_wall_600"
    assert asset_lock["assets"][0]["used_by"] == ["fixture_001"]
    assert manifest["reviews"][0]["actions"][0]["status"] == "applied"


@pytest.mark.asyncio
async def test_apply_visual_feedback_style_action_updates_metadata(tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="empty")
    response = await server.record_visual_feedback(
        project_path=str(tmp_path),
        summary="The project should use a calmer visual language.",
        actions=[
            {
                "type": "style",
                "target": "project",
                "intent": "Use a Scandinavian style direction.",
                "status": "accepted",
                "payload": {"style": "scandinavian"},
            }
        ],
    )
    review_id = json.loads(response.text)["visual_feedback"]["id"]

    apply_response = await server.apply_visual_feedback_action(
        project_path=str(tmp_path),
        review_id=review_id,
        action_index=0,
    )
    data = json.loads(apply_response.text)
    design_model = json.loads((tmp_path / "design_model.json").read_text())

    assert data["applied"] == {"style": "scandinavian"}
    assert design_model["metadata"]["style"] == "scandinavian"
    assert design_model["metadata"]["execution_sync"]["status"] == "dirty"
    assert (
        design_model["metadata"]["execution_sync"]["reason"]
        == "visual_feedback_action_applied"
    )
    assert design_model["metadata"]["execution_sync"]["details"] == {
        "review_id": review_id,
        "action_index": 0,
        "type": "style",
        "target": "project",
    }
    assert data["assets_lock_path"] is None


@pytest.mark.asyncio
async def test_apply_visual_feedback_rule_action_updates_design_rules(tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="empty")
    response = await server.record_visual_feedback(
        project_path=str(tmp_path),
        summary="The vanity needs more front clearance.",
        actions=[
            {
                "type": "rule",
                "target": "bathroom.vanity_front_clearance",
                "intent": "Increase vanity front clearance.",
                "status": "accepted",
                "payload": {
                    "rule_kind": "clearance",
                    "rule_set": "bathroom",
                    "clearance_name": "vanity_front_clearance",
                    "value": 760,
                },
            }
        ],
    )
    review_id = json.loads(response.text)["visual_feedback"]["id"]

    apply_response = await server.apply_visual_feedback_action(
        project_path=str(tmp_path),
        review_id=review_id,
        action_index=0,
    )
    data = json.loads(apply_response.text)
    design_rules = json.loads((tmp_path / "design_rules.json").read_text())
    design_model = json.loads((tmp_path / "design_model.json").read_text())
    manifest = json.loads((tmp_path / "snapshots" / "manifest.json").read_text())

    assert data["status"] == "applied"
    assert data["applied"]["rule_kind"] == "clearance"
    assert data["design_rules_path"].endswith("design_rules.json")
    assert (
        design_rules["rule_sets"]["bathroom"]["clearances"][
            "vanity_front_clearance"
        ]
        == 760.0
    )
    assert design_model["metadata"]["visual_feedback"]["last_applied"]["type"] == "rule"
    assert manifest["reviews"][0]["actions"][0]["status"] == "applied"


@pytest.mark.asyncio
async def test_apply_visual_feedback_rejects_unsupported_action_type(tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="empty")
    response = await server.record_visual_feedback(
        project_path=str(tmp_path),
        summary="Move the wall from the image.",
        actions=[
            {
                "type": "geometry",
                "target": "wall_001",
                "intent": "Move the wall.",
                "status": "accepted",
                "payload": {"delta": [100, 0, 0]},
            }
        ],
    )
    review_id = json.loads(response.text)["visual_feedback"]["id"]

    apply_response = await server.apply_visual_feedback_action(
        project_path=str(tmp_path),
        review_id=review_id,
        action_index=0,
    )

    assert apply_response.text == (
        "Visual feedback apply failed: action type is not supported for "
        "automatic application: geometry"
    )
