"""Tests for project state MCP tools."""

import json

import pytest

from mcp_server.project_init import init_project
from mcp_server.resources.design_model_schema import load_design_model, save_design_model


@pytest.mark.asyncio
async def test_get_project_state_reads_design_model(tmp_path):
    from mcp_server.server import get_project_state

    init_project(tmp_path, project_name="State Test", template="bathroom")

    response = await get_project_state(str(tmp_path))
    data = json.loads(response.text)

    assert data["project_path"] == str(tmp_path.resolve())
    assert data["design_model_path"].endswith("design_model.json")
    assert data["project_files"]["assets_lock_path"].endswith("assets.lock.json")
    assert data["project_files"]["snapshot_manifest_path"].endswith(
        "snapshots/manifest.json"
    )
    assert data["design_model"]["project_name"] == "State Test"
    assert "toilet_001" in data["design_model"]["components"]
    assert data["design_rules"]["valid"] is True
    assert data["design_rules"]["effective_valid"] is True
    assert data["design_rules"]["effective_rules"]["units"] == "mm"
    assert data["assets_lock"]["valid"] is True
    assert data["assets_lock"]["asset_count"] == 5
    assert data["assets_lock"]["referenced_asset_count"] == 5
    assert data["assets_lock"]["cached_asset_count"] == 0
    assert data["visual_feedback"]["valid"] is True
    assert data["visual_feedback"]["snapshot_count"] == 0
    assert data["visual_feedback"]["pending_action_count"] == 0
    assert data["versions"]["count"] == 0
    assert data["execution"]["operation_count"] == 0
    assert data["execution"]["has_execution_feedback"] is False
    assert data["execution"]["sync_status"] == "not_executed"


@pytest.mark.asyncio
async def test_get_project_state_can_skip_optional_summaries(tmp_path):
    from mcp_server.server import get_project_state

    init_project(tmp_path, template="bathroom")

    response = await get_project_state(
        str(tmp_path),
        include_rules=False,
        include_assets=False,
        include_visual_feedback=False,
        include_versions=False,
        include_execution=False,
    )
    data = json.loads(response.text)

    assert "design_model" in data
    assert "design_rules" not in data
    assert "assets_lock" not in data
    assert "visual_feedback" not in data
    assert "versions" not in data
    assert "execution" not in data


@pytest.mark.asyncio
async def test_get_project_state_summarizes_execution_feedback(tmp_path):
    from mcp_server.server import get_project_state

    init_project(tmp_path, template="bathroom")
    design_model_path = tmp_path / "design_model.json"
    design_model, errors = load_design_model(str(design_model_path))
    assert errors == []
    assert design_model is not None
    design_model["spaces"]["bathroom_001"]["execution"] = {
        "walls": {
            "south": {
                "operation_id": "wall_bathroom_001_south",
                "entity_ids": ["su-wall"],
                "status": "success",
            },
        },
    }
    design_model["components"]["toilet_001"]["entity_id"] = "su-toilet"
    design_model["lighting"]["ceiling_light_001"]["entity_id"] = "su-light"
    design_model["execution"] = {
        "bridge_operations": {
            "wall_bathroom_001_south": {
                "operation_type": "create_wall",
                "entity_ids": ["su-wall"],
                "status": "success",
            },
            "place_toilet_001": {
                "operation_type": "place_component",
                "entity_ids": ["su-toilet"],
                "status": "success",
            },
        }
    }
    saved, save_errors = save_design_model(str(design_model_path), design_model)
    assert saved, save_errors

    response = await get_project_state(str(tmp_path))
    data = json.loads(response.text)

    assert data["execution"]["operation_count"] == 2
    assert data["execution"]["operation_type_counts"] == {
        "create_wall": 1,
        "place_component": 1,
    }
    assert data["execution"]["component_entity_count"] == 1
    assert data["execution"]["lighting_entity_count"] == 1
    assert data["execution"]["space_wall_entity_count"] == 1
    assert data["execution"]["space_walls_with_entity_ids"] == ["bathroom_001.south"]
    assert data["execution"]["components_with_entity_ids"] == ["toilet_001"]
    assert data["execution"]["lighting_with_entity_ids"] == ["ceiling_light_001"]
    assert data["execution"]["sync_status"] == "synced"


@pytest.mark.asyncio
async def test_get_project_state_summarizes_versions(tmp_path):
    from mcp_server.server import get_project_state, save_project_version

    init_project(tmp_path, template="bathroom")
    await save_project_version(project_path=str(tmp_path), version_tag="draft_1")

    response = await get_project_state(str(tmp_path))
    data = json.loads(response.text)

    assert data["versions"]["count"] == 1
    assert data["versions"]["versions"][0]["version"] == "draft_1"


@pytest.mark.asyncio
async def test_get_project_state_summarizes_effective_design_rules(tmp_path):
    from mcp_server import server
    from mcp_server.server import get_project_state

    init_project(tmp_path, template="bathroom")
    await server.set_design_preference(
        project_path=str(tmp_path),
        preference_name="lighting_temperature",
        value="3000K",
    )

    response = await get_project_state(str(tmp_path))
    data = json.loads(response.text)

    assert data["design_rules"]["source"] == "project_user_override"
    assert data["design_rules"]["effective_valid"] is True
    assert "project_user_override" in data["design_rules"]["effective_source"]
    assert data["design_rules"]["effective_preferences"] == {
        "lighting_temperature": "3000K"
    }
    assert data["design_rules"]["effective_rules"]["preferences"] == {
        "lighting_temperature": "3000K"
    }


@pytest.mark.asyncio
async def test_get_project_state_summarizes_visual_feedback(tmp_path):
    from mcp_server import server
    from mcp_server.server import get_project_state

    init_project(tmp_path, template="bathroom")
    response = await server.record_visual_feedback(
        project_path=str(tmp_path),
        summary="The vanity area needs a warmer material.",
        actions=[
            {
                "type": "material",
                "target": "vanity_001",
                "intent": "Use a warmer vanity material.",
                "status": "proposed",
                "payload": {"material": "warm oak"},
            },
            {
                "type": "style",
                "target": "project",
                "intent": "Use a softer style direction.",
                "status": "accepted",
                "payload": {"style": "soft minimal"},
            },
            {
                "type": "note",
                "target": "project",
                "intent": "Already discussed with the designer.",
                "status": "applied",
                "payload": {},
            },
        ],
    )
    await server.record_render_artifact(
        project_path=str(tmp_path),
        artifact_path=str(tmp_path / "snapshots" / "warm-render.png"),
        prompt="Render the bathroom with a warmer material direction.",
        renderer_tool="image_renderer",
        renderer_model="image-2",
        label="warm render",
    )
    review_id = json.loads(response.text)["visual_feedback"]["id"]

    state_response = await get_project_state(str(tmp_path))
    data = json.loads(state_response.text)

    visual_feedback = data["visual_feedback"]
    assert visual_feedback["valid"] is True
    assert visual_feedback["review_count"] == 1
    assert visual_feedback["render_count"] == 1
    assert visual_feedback["latest_render"]["id"] == "render_warm-render"
    assert visual_feedback["latest_render"]["renderer"]["model"] == "image-2"
    assert visual_feedback["action_count"] == 3
    assert visual_feedback["pending_action_count"] == 2
    assert visual_feedback["accepted_action_count"] == 1
    assert visual_feedback["applied_action_count"] == 1
    assert visual_feedback["pending_actions"] == [
        {
            "review_id": review_id,
            "action_index": 0,
            "type": "material",
            "target": "vanity_001",
            "intent": "Use a warmer vanity material.",
            "status": "proposed",
            "payload": {"material": "warm oak"},
            "rationale": None,
        },
        {
            "review_id": review_id,
            "action_index": 1,
            "type": "style",
            "target": "project",
            "intent": "Use a softer style direction.",
            "status": "accepted",
            "payload": {"style": "soft minimal"},
            "rationale": None,
        },
    ]


@pytest.mark.asyncio
async def test_get_project_state_reports_optional_file_errors(tmp_path):
    from mcp_server.server import get_project_state

    init_project(tmp_path, template="empty")
    (tmp_path / "assets.lock.json").unlink()
    (tmp_path / "snapshots" / "manifest.json").unlink()

    response = await get_project_state(str(tmp_path))
    data = json.loads(response.text)

    assert "components" in data["design_model"]
    assert data["assets_lock"]["exists"] is False
    assert data["assets_lock"]["valid"] is False
    assert "File not found" in data["assets_lock"]["errors"][0]
    assert data["visual_feedback"]["exists"] is False
    assert data["visual_feedback"]["valid"] is False
    assert "File not found" in data["visual_feedback"]["errors"][0]


@pytest.mark.asyncio
async def test_get_project_state_reports_missing_model(tmp_path):
    from mcp_server.server import get_project_state

    response = await get_project_state(str(tmp_path))

    assert response.text.startswith("Project state failed:")
    assert "File not found" in response.text


@pytest.mark.asyncio
async def test_list_project_components_includes_lighting_by_default(tmp_path):
    from mcp_server.server import list_project_components

    init_project(tmp_path, template="bathroom")

    response = await list_project_components(str(tmp_path))
    data = json.loads(response.text)

    ids = {component["id"] for component in data["components"]}
    kinds = {component["kind"] for component in data["components"]}

    assert data["count"] == 5
    assert "toilet_001" in ids
    assert "ceiling_light_001" in ids
    assert kinds == {"component", "lighting"}


@pytest.mark.asyncio
async def test_list_project_components_can_exclude_lighting(tmp_path):
    from mcp_server.server import list_project_components

    init_project(tmp_path, template="bathroom")

    response = await list_project_components(str(tmp_path), include_lighting=False)
    data = json.loads(response.text)

    ids = {component["id"] for component in data["components"]}

    assert data["count"] == 4
    assert "ceiling_light_001" not in ids


@pytest.mark.asyncio
async def test_validate_design_project_uses_cli_validation(tmp_path):
    from mcp_server.server import validate_design_project

    init_project(tmp_path, template="bathroom")

    response = await validate_design_project(str(tmp_path))
    data = json.loads(response.text)

    assert data["ok"] is True
    assert {check["name"] for check in data["checks"]} >= {
        "design_model",
        "design_rules",
        "assets_lock",
        "asset_refs_locked",
    }
