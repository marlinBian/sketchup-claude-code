"""Tests for local smoke checks."""

import json

from mcp_server.project_init import init_project
from mcp_server import smoke as smoke_module
from mcp_server.smoke import (
    bridge_socket_check,
    component_refs_from_model,
    run_smoke,
    validate_project,
)


def test_validate_project_accepts_initialized_bathroom(tmp_path):
    project_path = tmp_path / "bathroom"
    init_project(project_path, template="bathroom")

    result = validate_project(project_path)

    assert result["ok"] is True
    assert {check["name"] for check in result["checks"]} >= {
        "design_model",
        "design_rules",
        "assets_lock",
        "component_library",
        "assets_cache",
        "snapshot_manifest",
        "codex_guidance",
        "claude_guidance",
        "codex_runtime_skills",
        "claude_runtime_skills",
        "asset_refs_locked",
    }


def test_validate_project_detects_missing_asset_lock_ref(tmp_path):
    project_path = tmp_path / "bathroom"
    init_project(project_path, template="bathroom")
    lock_path = project_path / "assets.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["assets"] = [
        asset
        for asset in lock["assets"]
        if asset["component_id"] != "toilet_floor_mounted_basic"
    ]
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

    result = validate_project(project_path)

    assert result["ok"] is False
    asset_ref_check = next(
        check for check in result["checks"] if check["name"] == "asset_refs_locked"
    )
    assert asset_ref_check["ok"] is False
    assert "toilet_floor_mounted_basic" in asset_ref_check["errors"][0]


def test_run_headless_smoke(tmp_path):
    result = run_smoke(tmp_path / "smoke", overwrite=True)

    assert result["ok"] is True
    assert result["headless_plan"]["valid"] is True
    assert result["headless_plan"]["bridge_operation_count"] > 0


def test_run_live_smoke_syncs_execution_results(monkeypatch, tmp_path):
    def fake_execute(operations):
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

    monkeypatch.setattr(smoke_module, "execute_bridge_operations", fake_execute)
    socket_path = tmp_path / "su_bridge.sock"
    socket_path.touch()
    project_path = tmp_path / "smoke"

    result = run_smoke(
        project_path,
        overwrite=True,
        with_bridge=True,
        socket_path=str(socket_path),
    )
    design_model = json.loads((project_path / "design_model.json").read_text())

    assert result["ok"] is True
    assert result["execution_sync"]["saved"] is True
    assert "toilet_001" in result["execution_sync"]["updated_components"]
    assert "ceiling_light_001" in result["execution_sync"]["updated_lighting"]
    assert design_model["components"]["toilet_001"]["entity_id"] == "su-place_toilet_001"
    assert design_model["lighting"]["ceiling_light_001"]["entity_id"] == (
        "su-place_ceiling_light_001"
    )
    assert "place_toilet_001" in design_model["execution"]["bridge_operations"]


def test_run_smoke_without_force_refuses_existing_project(tmp_path):
    project_path = tmp_path / "smoke"
    run_smoke(project_path, overwrite=True)

    result = run_smoke(project_path, overwrite=False)

    assert result["ok"] is False
    init_check = next(check for check in result["checks"] if check["name"] == "init_project")
    assert init_check["ok"] is False
    assert "Refusing to overwrite" in init_check["errors"][0]


def test_component_refs_from_model_includes_lighting():
    model = {
        "components": {
            "toilet_001": {"component_ref": "toilet_floor_mounted_basic"},
        },
        "lighting": {
            "ceiling_light_001": {"component_ref": "ceiling_light_basic"},
        },
    }

    assert component_refs_from_model(model) == {
        "toilet_floor_mounted_basic",
        "ceiling_light_basic",
    }


def test_bridge_socket_check_reports_missing_socket(tmp_path):
    result = bridge_socket_check(str(tmp_path / "missing.sock"))

    assert result["ok"] is False
    assert "not available" in result["errors"][0]
