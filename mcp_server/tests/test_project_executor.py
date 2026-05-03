"""Tests for project truth to bridge execution planning."""

import json

import pytest

from mcp_server.project_init import init_project
from mcp_server.resources.design_model_schema import load_design_model, save_design_model
from mcp_server.tools.project_executor import (
    build_project_execution_plan,
    execute_project_execution_plan,
    resolve_project_skp_path,
)
from mcp_server.tools.import_pipeline import import_floorplan_to_model


def test_build_project_execution_plan_from_bathroom_project(tmp_path):
    init_project(tmp_path, template="bathroom")

    plan = build_project_execution_plan(tmp_path)
    operation_types = [operation["operation_type"] for operation in plan["bridge_operations"]]
    component_ids = [
        operation["payload"].get("component_id")
        for operation in plan["bridge_operations"]
        if operation["operation_type"] == "place_component"
    ]

    assert plan["operation_count"] == 10
    assert plan["skipped_instances"] == []
    assert operation_types[:4] == ["create_wall"] * 4
    assert plan["bridge_operations"][0]["payload"]["space_id"] == "bathroom_001"
    assert plan["bridge_operations"][0]["payload"]["wall_side"] == "south"
    assert "bathroom_door_700" in component_ids
    assert "toilet_floor_mounted_basic" in component_ids
    assert "vanity_wall_600" in component_ids
    assert "mirror_wall_500" in component_ids
    assert "ceiling_light_basic" in component_ids
    assert operation_types[-1] == "get_scene_info"


def test_build_project_execution_plan_reports_missing_component_ref(tmp_path):
    init_project(tmp_path, template="empty")
    design_model_path = tmp_path / "design_model.json"
    design_model, errors = load_design_model(str(design_model_path))
    assert errors == []
    assert design_model is not None
    design_model["components"]["missing_001"] = {
        "type": "fixture",
        "name": "Missing fixture",
        "component_ref": "missing_component",
        "position": [0, 0, 0],
    }
    saved, save_errors = save_design_model(str(design_model_path), design_model)
    assert saved, save_errors

    plan = build_project_execution_plan(tmp_path)

    assert plan["skipped_count"] == 1
    assert plan["skipped_instances"] == [
        {
            "kind": "component",
            "id": "missing_001",
            "reason": "component not found: missing_component",
        }
    ]


def test_build_project_execution_plan_from_imported_floorplan(tmp_path):
    init_project(tmp_path, template="empty")
    source = tmp_path / "floorplan.pdf"
    source.write_bytes(b"floorplan")
    import_floorplan_to_model(
        tmp_path,
        source_path=source,
        import_id="import_001",
        width=5000,
        depth=3000,
    )

    plan = build_project_execution_plan(tmp_path)
    operation_types = [operation["operation_type"] for operation in plan["bridge_operations"]]

    assert plan["skipped_count"] == 0
    assert plan["operation_count"] == 9
    assert operation_types.count("create_wall") == 6
    assert operation_types.count("create_box") == 2
    assert operation_types[-1] == "get_scene_info"
    assert plan["bridge_operations"][0]["payload"]["wall_id"] == "import_001_wall_east"
    south_segments = [
        operation["payload"]
        for operation in plan["bridge_operations"]
        if operation["payload"].get("wall_id") == "import_001_wall_south"
    ]
    assert [segment["wall_segment_id"] for segment in south_segments] == [
        "import_001_wall_south_solid_01",
        "import_001_wall_south_solid_02",
    ]
    assert south_segments[0]["end"] == [2050.0, 0.0, 0.0]
    assert south_segments[1]["start"] == [2950.0, 0.0, 0.0]
    assert south_segments[0]["excluded_opening_ids"] == ["import_001_door_001"]
    assert plan["bridge_operations"][6]["payload"]["opening_id"] == "import_001_door_001"


def test_resolve_project_skp_path_makes_project_relative_paths_absolute(tmp_path):
    resolved = resolve_project_skp_path("assets/components/custom.skp", tmp_path)

    assert resolved == str((tmp_path / "assets" / "components" / "custom.skp").resolve())


def test_execute_project_execution_plan_accepts_injected_executor(tmp_path):
    init_project(tmp_path, template="bathroom")

    def fake_execute(operations, stop_on_error=True):
        results = []
        for operation in operations:
            payload = operation.get("payload", {})
            results.append(
                {
                    "operation_id": operation["operation_id"],
                    "operation_type": operation["operation_type"],
                    "request": {"params": {"payload": payload}},
                    "response": {
                        "result": {
                            "status": "success",
                            "entity_ids": [f"su-{operation['operation_id']}"],
                            "spatial_delta": {},
                        },
                    },
                    "ok": True,
                }
            )
        return {
            "status": "success",
            "executed_count": len(operations),
            "requested_count": len(operations),
            "results": results,
        }

    result = execute_project_execution_plan(tmp_path, execute_fn=fake_execute)
    design_model = json.loads((tmp_path / "design_model.json").read_text(encoding="utf-8"))

    assert result["status"] == "success"
    assert result["execution_sync"]["saved"] is True
    assert result["execution_sync"]["updated_space_walls"] == [
        "bathroom_001.south",
        "bathroom_001.east",
        "bathroom_001.north",
        "bathroom_001.west",
    ]
    assert design_model["spaces"]["bathroom_001"]["execution"]["walls"]["south"][
        "entity_ids"
    ] == ["su-wall_bathroom_001_south"]
    assert design_model["components"]["toilet_001"]["entity_id"] == "su-place_toilet_001"
    assert design_model["metadata"]["execution_sync"]["status"] == "synced"
    assert design_model["metadata"]["execution_sync"]["operation_count"] == 10


def test_execute_project_execution_plan_syncs_imported_walls_and_openings(tmp_path):
    init_project(tmp_path, template="empty")
    source = tmp_path / "floorplan.pdf"
    source.write_bytes(b"floorplan")
    import_floorplan_to_model(tmp_path, source_path=source, import_id="import_001")

    def fake_execute(operations, stop_on_error=True):
        results = []
        for operation in operations:
            payload = operation.get("payload", {})
            results.append(
                {
                    "operation_id": operation["operation_id"],
                    "operation_type": operation["operation_type"],
                    "request": {"params": {"payload": payload}},
                    "response": {
                        "result": {
                            "status": "success",
                            "entity_ids": [f"su-{operation['operation_id']}"],
                            "spatial_delta": {},
                        },
                    },
                    "ok": True,
                }
            )
        return {
            "status": "success",
            "executed_count": len(operations),
            "requested_count": len(operations),
            "results": results,
        }

    result = execute_project_execution_plan(tmp_path, execute_fn=fake_execute)
    design_model = json.loads((tmp_path / "design_model.json").read_text(encoding="utf-8"))

    assert result["execution_sync"]["updated_walls"] == [
        "import_001_wall_east",
        "import_001_wall_north",
        "import_001_wall_south",
        "import_001_wall_west",
    ]
    assert result["execution_sync"]["updated_openings"] == [
        "import_001_door_001",
        "import_001_window_001",
    ]
    assert design_model["walls"]["import_001_wall_south"]["execution"]["entity_ids"] == [
        "su-wall_import_001_wall_south_solid_01",
        "su-wall_import_001_wall_south_solid_02",
    ]
    assert sorted(
        design_model["walls"]["import_001_wall_south"]["execution"]["segments"]
    ) == [
        "import_001_wall_south_solid_01",
        "import_001_wall_south_solid_02",
    ]
    assert design_model["walls"]["import_001_wall_south"]["execution"]["operation_ids"] == [
        "wall_import_001_wall_south_solid_01",
        "wall_import_001_wall_south_solid_02",
    ]
    assert design_model["openings"]["import_001_door_001"]["execution"]["entity_ids"] == [
        "su-opening_import_001_door_001"
    ]


def test_execute_project_execution_plan_can_clean_before_replay(tmp_path):
    init_project(tmp_path, template="bathroom")
    calls = []

    def fake_execute(operations, stop_on_error=True):
        calls.append([operation["operation_type"] for operation in operations])
        results = []
        for operation in operations:
            payload = operation.get("payload", {})
            results.append(
                {
                    "operation_id": operation["operation_id"],
                    "operation_type": operation["operation_type"],
                    "request": {"params": {"payload": payload}},
                    "response": {
                        "result": {
                            "status": "success",
                            "entity_ids": [f"su-{operation['operation_id']}"],
                            "spatial_delta": {},
                        },
                    },
                    "ok": True,
                }
            )
        return {
            "status": "success",
            "executed_count": len(operations),
            "requested_count": len(operations),
            "results": results,
        }

    result = execute_project_execution_plan(
        tmp_path,
        clean_before_execute=True,
        execute_fn=fake_execute,
    )

    assert result["status"] == "success"
    assert calls[0] == ["cleanup_model"]
    assert calls[1][0] == "create_wall"
    assert result["pre_execution_cleanup"]["status"] == "success"
    cleanup_payload = result["pre_execution_cleanup"]["results"][0]["request"]["params"][
        "payload"
    ]
    assert cleanup_payload["layer_names"] == [
        "Walls",
        "Doors",
        "Windows",
        "Fixtures",
        "Furniture",
        "Lighting",
        "Materials",
    ]
    assert cleanup_payload["all_entities"] is False


def test_execute_project_execution_plan_can_clean_all_before_replay(tmp_path):
    init_project(tmp_path, template="bathroom")
    cleanup_payloads = []

    def fake_execute(operations, stop_on_error=True):
        if operations[0]["operation_type"] == "cleanup_model":
            cleanup_payloads.append(operations[0]["payload"])
        results = []
        for operation in operations:
            payload = operation.get("payload", {})
            results.append(
                {
                    "operation_id": operation["operation_id"],
                    "operation_type": operation["operation_type"],
                    "request": {"params": {"payload": payload}},
                    "response": {
                        "result": {
                            "status": "success",
                            "entity_ids": [f"su-{operation['operation_id']}"],
                            "spatial_delta": {},
                        },
                    },
                    "ok": True,
                }
            )
        return {
            "status": "success",
            "executed_count": len(operations),
            "requested_count": len(operations),
            "results": results,
        }

    result = execute_project_execution_plan(
        tmp_path,
        clean_before_execute=True,
        clean_scope="all",
        execute_fn=fake_execute,
    )

    assert result["status"] == "success"
    assert cleanup_payloads == [
        {
            "layer_names": None,
            "tag": None,
            "all_entities": True,
        }
    ]


def test_execute_project_execution_plan_stops_when_cleanup_fails(tmp_path):
    init_project(tmp_path, template="bathroom")
    calls = []

    def fake_execute(operations, stop_on_error=True):
        calls.append([operation["operation_type"] for operation in operations])
        return {
            "status": "failed",
            "executed_count": 1,
            "requested_count": 1,
            "results": [
                {
                    "operation_id": operations[0]["operation_id"],
                    "operation_type": operations[0]["operation_type"],
                    "request": {"params": {"payload": operations[0].get("payload", {})}},
                    "response": {"error": {"message": "cleanup failed"}},
                    "ok": False,
                }
            ],
        }

    result = execute_project_execution_plan(
        tmp_path,
        clean_before_execute=True,
        execute_fn=fake_execute,
    )

    assert result["status"] == "cleanup_failed"
    assert calls == [["cleanup_model"]]
    assert "execution_report" not in result


@pytest.mark.asyncio
async def test_plan_project_execution_tool_returns_bridge_trace(tmp_path):
    from mcp_server.server import plan_project_execution

    init_project(tmp_path, template="bathroom")

    response = await plan_project_execution(str(tmp_path))
    data = json.loads(response.text)

    assert data["operation_count"] == 10
    assert data["skipped_count"] == 0
    assert data["bridge_operations"][0]["operation_type"] == "create_wall"


@pytest.mark.asyncio
async def test_execute_project_model_syncs_entity_ids_to_project(monkeypatch, tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="bathroom")

    def fake_execute(operations, stop_on_error=True):
        results = []
        for operation in operations:
            payload = operation.get("payload", {})
            results.append(
                {
                    "operation_id": operation["operation_id"],
                    "operation_type": operation["operation_type"],
                    "request": {"params": {"payload": payload}},
                    "response": {
                        "result": {
                            "status": "success",
                            "entity_ids": [f"su-{operation['operation_id']}"],
                            "spatial_delta": {},
                        },
                    },
                    "ok": True,
                }
            )
        return {
            "status": "success",
            "executed_count": len(operations),
            "requested_count": len(operations),
            "results": results,
        }

    monkeypatch.setattr(server, "execute_bridge_operations", fake_execute)

    response = await server.execute_project_model(str(tmp_path))
    data = json.loads(response.text)
    design_model = json.loads((tmp_path / "design_model.json").read_text(encoding="utf-8"))

    assert data["status"] == "success"
    assert data["execution_sync"]["saved"] is True
    assert data["execution_sync"]["updated_spaces"] == ["bathroom_001"]
    assert "toilet_001" in data["execution_sync"]["updated_components"]
    assert "ceiling_light_001" in data["execution_sync"]["updated_lighting"]
    assert design_model["components"]["toilet_001"]["entity_id"] == "su-place_toilet_001"
    assert design_model["lighting"]["ceiling_light_001"]["entity_id"] == (
        "su-place_ceiling_light_001"
    )
    assert design_model["spaces"]["bathroom_001"]["execution"]["walls"]["west"][
        "entity_ids"
    ] == ["su-wall_bathroom_001_west"]
    assert "wall_bathroom_001_south" in design_model["execution"]["bridge_operations"]
    assert design_model["metadata"]["execution_sync"]["status"] == "synced"


@pytest.mark.asyncio
async def test_execute_project_model_clean_before_execute(monkeypatch, tmp_path):
    from mcp_server import server

    init_project(tmp_path, template="bathroom")
    calls = []

    def fake_execute(operations, stop_on_error=True):
        calls.append([operation["operation_type"] for operation in operations])
        results = []
        for operation in operations:
            payload = operation.get("payload", {})
            results.append(
                {
                    "operation_id": operation["operation_id"],
                    "operation_type": operation["operation_type"],
                    "request": {"params": {"payload": payload}},
                    "response": {
                        "result": {
                            "status": "success",
                            "entity_ids": [f"su-{operation['operation_id']}"],
                            "spatial_delta": {},
                        },
                    },
                    "ok": True,
                }
            )
        return {
            "status": "success",
            "executed_count": len(operations),
            "requested_count": len(operations),
            "results": results,
        }

    monkeypatch.setattr(server, "execute_bridge_operations", fake_execute)

    response = await server.execute_project_model(
        str(tmp_path),
        clean_before_execute=True,
    )
    data = json.loads(response.text)

    assert data["status"] == "success"
    assert calls[0] == ["cleanup_model"]
    assert calls[1][0] == "create_wall"
    assert data["pre_execution_cleanup"]["status"] == "success"


@pytest.mark.asyncio
async def test_execute_project_model_refuses_skipped_instances_by_default(
    monkeypatch,
    tmp_path,
):
    from mcp_server import server

    init_project(tmp_path, template="empty")
    design_model_path = tmp_path / "design_model.json"
    design_model, errors = load_design_model(str(design_model_path))
    assert errors == []
    assert design_model is not None
    design_model["components"]["missing_001"] = {
        "type": "fixture",
        "name": "Missing fixture",
        "component_ref": "missing_component",
        "position": [0, 0, 0],
    }
    saved, save_errors = save_design_model(str(design_model_path), design_model)
    assert saved, save_errors

    called = False

    def fake_execute(operations, stop_on_error=True):
        nonlocal called
        called = True
        return {"status": "success", "executed_count": 0, "requested_count": 0, "results": []}

    monkeypatch.setattr(server, "execute_bridge_operations", fake_execute)

    response = await server.execute_project_model(str(tmp_path))
    data = json.loads(response.text)

    assert data["status"] == "not_executed"
    assert data["skipped_count"] == 1
    assert called is False


def test_cli_plan_execution_outputs_bridge_trace(tmp_path, capsys):
    from mcp_server.cli import main

    init_project(tmp_path, template="bathroom")

    exit_code = main(["plan-execution", str(tmp_path)])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["operation_count"] == 10
    assert data["skipped_count"] == 0


def test_cli_execute_project_outputs_json(monkeypatch, tmp_path, capsys):
    from mcp_server import cli

    init_project(tmp_path, template="bathroom")

    def fake_execute_project_execution_plan(project_path, **kwargs):
        return {
            "project_path": str(tmp_path.resolve()),
            "status": "success",
            "operation_count": 10,
            "skipped_count": 0,
        }

    monkeypatch.setattr(
        cli,
        "execute_project_execution_plan",
        fake_execute_project_execution_plan,
    )

    exit_code = cli.main(["execute-project", str(tmp_path)])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["status"] == "success"
