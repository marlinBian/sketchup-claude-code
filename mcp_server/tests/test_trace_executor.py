"""Tests for bridge trace execution."""

from mcp_server.tools.trace_executor import (
    bridge_request_for_operation,
    execute_bridge_operations,
    sync_execution_report_to_design_model,
)


class FakeBridge:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.disconnected = False

    def send(self, request):
        self.requests.append(request)
        return self.responses.pop(0)

    def disconnect(self):
        self.disconnected = True


def test_bridge_request_for_operation_uses_json_rpc_contract():
    request = bridge_request_for_operation(
        {
            "operation_id": "place_toilet",
            "operation_type": "place_component",
            "payload": {"component_id": "toilet_floor_mounted_basic"},
            "rollback_on_failure": True,
        }
    )

    assert request["jsonrpc"] == "2.0"
    assert request["method"] == "execute_operation"
    assert request["params"]["operation_type"] == "place_component"


def test_execute_bridge_operations_sends_operations_in_order():
    bridge = FakeBridge(
        [
            {"result": {"entity_ids": ["1"]}},
            {"result": {"entity_ids": ["2"]}},
        ]
    )
    operations = [
        {
            "operation_id": "wall_south",
            "operation_type": "create_wall",
            "payload": {"start": [0, 0, 0]},
        },
        {
            "operation_id": "place_toilet",
            "operation_type": "place_component",
            "payload": {"component_id": "toilet_floor_mounted_basic"},
        },
    ]

    report = execute_bridge_operations(operations, bridge=bridge)

    assert report["status"] == "success"
    assert report["executed_count"] == 2
    assert bridge.requests[0]["params"]["operation_type"] == "create_wall"
    assert bridge.requests[1]["params"]["operation_type"] == "place_component"
    assert bridge.disconnected is False


def test_execute_bridge_operations_stops_on_error_by_default():
    bridge = FakeBridge(
        [
            {"error": {"code": -32001, "message": "invalid"}},
            {"result": {"entity_ids": ["2"]}},
        ]
    )
    operations = [
        {"operation_id": "bad", "operation_type": "create_wall", "payload": {}},
        {"operation_id": "skip", "operation_type": "create_wall", "payload": {}},
    ]

    report = execute_bridge_operations(operations, bridge=bridge)

    assert report["status"] == "failed"
    assert report["executed_count"] == 1
    assert len(bridge.requests) == 1


def test_sync_execution_report_to_design_model_records_entity_ids():
    design_model = {
        "components": {
            "toilet_001": {"type": "toilet", "name": "Toilet", "position": [0, 0, 0]},
        },
        "lighting": {
            "ceiling_light_001": {
                "type": "recessed_light",
                "position": [0, 0, 2400],
            },
        },
    }
    execution_report = {
        "results": [
            {
                "operation_id": "place_toilet_001",
                "operation_type": "place_component",
                "request": {
                    "params": {
                        "payload": {"instance_id": "toilet_001"},
                    },
                },
                "response": {
                    "result": {
                        "status": "success",
                        "entity_ids": ["su-toilet"],
                        "spatial_delta": {"bounding_box": {"min": [0, 0, 0]}},
                    },
                },
                "ok": True,
            },
            {
                "operation_id": "place_ceiling_light_001",
                "operation_type": "place_component",
                "request": {
                    "params": {
                        "payload": {"instance_id": "ceiling_light_001"},
                    },
                },
                "response": {
                    "result": {
                        "status": "success",
                        "entity_ids": ["su-light"],
                        "spatial_delta": {},
                    },
                },
                "ok": True,
            },
        ],
    }

    sync = sync_execution_report_to_design_model(design_model, execution_report)

    assert sync["updated_components"] == ["toilet_001"]
    assert sync["updated_lighting"] == ["ceiling_light_001"]
    assert design_model["components"]["toilet_001"]["entity_id"] == "su-toilet"
    assert design_model["lighting"]["ceiling_light_001"]["entity_id"] == "su-light"
    assert "place_toilet_001" in design_model["execution"]["bridge_operations"]
