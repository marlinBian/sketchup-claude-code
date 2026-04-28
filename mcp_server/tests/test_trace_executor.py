"""Tests for bridge trace execution."""

from mcp_server.tools.trace_executor import (
    bridge_request_for_operation,
    execute_bridge_operations,
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
