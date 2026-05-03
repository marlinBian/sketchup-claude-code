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
        "spaces": {
            "bathroom_001": {
                "type": "bathroom",
                "bounds": {"min": [0, 0, 0], "max": [2000, 1800, 2400]},
            },
        },
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
                "operation_id": "wall_bathroom_001_south",
                "operation_type": "create_wall",
                "request": {
                    "params": {
                        "payload": {
                            "space_id": "bathroom_001",
                            "wall_side": "south",
                        },
                    },
                },
                "response": {
                    "result": {
                        "status": "success",
                        "entity_ids": ["su-wall-south"],
                        "spatial_delta": {"bounding_box": {"min": [0, 0, 0]}},
                    },
                },
                "ok": True,
            },
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

    assert sync["updated_spaces"] == ["bathroom_001"]
    assert sync["updated_space_walls"] == ["bathroom_001.south"]
    assert sync["updated_components"] == ["toilet_001"]
    assert sync["updated_lighting"] == ["ceiling_light_001"]
    assert design_model["spaces"]["bathroom_001"]["execution"]["walls"]["south"][
        "entity_ids"
    ] == ["su-wall-south"]
    assert design_model["components"]["toilet_001"]["entity_id"] == "su-toilet"
    assert design_model["lighting"]["ceiling_light_001"]["entity_id"] == "su-light"
    assert "place_toilet_001" in design_model["execution"]["bridge_operations"]


def test_sync_execution_report_aggregates_split_wall_segments():
    design_model = {
        "walls": {
            "east_wall": {
                "path": [[5000, 0, 0], [5000, 3000, 0]],
                "height": 2800,
                "thickness": 120,
            },
        },
    }
    execution_report = {
        "results": [
            {
                "operation_id": "wall_east_wall_solid_01",
                "operation_type": "create_wall",
                "request": {
                    "params": {
                        "payload": {
                            "wall_id": "east_wall",
                            "wall_segment_id": "east_wall_solid_01",
                        },
                    },
                },
                "response": {
                    "result": {
                        "status": "success",
                        "entity_ids": ["su-wall-1"],
                        "spatial_delta": {
                            "bounding_box": {
                                "min": [5000, 0, 0],
                                "max": [5120, 900, 2800],
                            },
                            "volume_mm3": 302400000,
                        },
                    },
                },
                "ok": True,
            },
            {
                "operation_id": "wall_east_wall_solid_02",
                "operation_type": "create_wall",
                "request": {
                    "params": {
                        "payload": {
                            "wall_id": "east_wall",
                            "wall_segment_id": "east_wall_solid_02",
                        },
                    },
                },
                "response": {
                    "result": {
                        "status": "success",
                        "entity_ids": ["su-wall-2"],
                        "spatial_delta": {
                            "bounding_box": {
                                "min": [5000, 2100, 0],
                                "max": [5120, 3000, 2800],
                            },
                            "volume_mm3": 302400000,
                        },
                    },
                },
                "ok": True,
            },
        ],
    }

    sync = sync_execution_report_to_design_model(design_model, execution_report)

    assert sync["updated_walls"] == ["east_wall"]
    execution = design_model["walls"]["east_wall"]["execution"]
    assert execution["operation_ids"] == [
        "wall_east_wall_solid_01",
        "wall_east_wall_solid_02",
    ]
    assert execution["entity_ids"] == ["su-wall-1", "su-wall-2"]
    assert sorted(execution["segments"]) == [
        "east_wall_solid_01",
        "east_wall_solid_02",
    ]
    assert execution["spatial_delta"]["bounding_box"] == {
        "min": [5000, 0, 0],
        "max": [5120, 3000, 2800],
    }
    assert execution["spatial_delta"]["volume_mm3"] == 604800000


def test_sync_execution_report_records_hosted_opening_results():
    design_model = {
        "execution": {
            "bridge_operations": {
                "opening_east_window": {
                    "operation_type": "create_box",
                    "entity_ids": ["stale-window-box"],
                },
                "wall_east_wall_solid_01": {
                    "operation_type": "create_wall",
                    "entity_ids": ["stale-wall-1"],
                },
                "wall_east_wall_solid_02": {
                    "operation_type": "create_wall",
                    "entity_ids": ["stale-wall-2"],
                },
            },
        },
        "walls": {
            "east_wall": {
                "path": [[5000, 0, 0], [5000, 3000, 0]],
                "height": 2800,
                "thickness": 120,
                "execution": {
                    "operation_ids": [
                        "wall_east_wall_solid_01",
                        "wall_east_wall_solid_02",
                    ],
                    "entity_ids": ["stale-wall-1", "stale-wall-2"],
                    "segments": {
                        "east_wall_solid_01": {
                            "operation_id": "wall_east_wall_solid_01",
                            "entity_ids": ["stale-wall-1"],
                            "status": "success",
                        },
                        "east_wall_solid_02": {
                            "operation_id": "wall_east_wall_solid_02",
                            "entity_ids": ["stale-wall-2"],
                            "status": "success",
                        },
                    },
                },
            },
        },
        "openings": {
            "east_window": {
                "type": "window",
                "host_wall": "east_wall",
                "offset": 900,
                "width": 1200,
                "height": 1200,
                "execution": {
                    "operation_id": "opening_east_window",
                    "entity_ids": ["stale-window-box"],
                    "status": "success",
                },
            },
        },
    }
    execution_report = {
        "results": [
            {
                "operation_id": "wall_east_wall_with_openings",
                "operation_type": "create_wall_with_openings",
                "request": {
                    "params": {
                        "payload": {
                            "wall_id": "east_wall",
                            "wall_segment_id": "east_wall",
                            "openings": [{"opening_id": "east_window"}],
                        },
                    },
                },
                "response": {
                    "result": {
                        "status": "success",
                        "entity_ids": ["su-wall-1", "su-wall-2"],
                        "spatial_delta": {},
                        "opening_results": [
                            {
                                "opening_id": "east_window",
                                "entity_ids": ["su-window-marker"],
                                "spatial_delta": {
                                    "bounding_box": {
                                        "min": [5000, 900, 900],
                                        "max": [5120, 2100, 2100],
                                    },
                                },
                                "status": "success",
                            },
                        ],
                    },
                },
                "ok": True,
            },
        ],
    }

    sync = sync_execution_report_to_design_model(design_model, execution_report)

    assert sync["updated_walls"] == ["east_wall"]
    assert sync["updated_openings"] == ["east_window"]
    assert sync["removed_operations"] == [
        "opening_east_window",
        "wall_east_wall_solid_01",
        "wall_east_wall_solid_02",
    ]
    assert sync["cleared_walls"] == ["east_wall"]
    assert sync["cleared_openings"] == ["east_window"]
    assert design_model["walls"]["east_wall"]["execution"]["entity_ids"] == [
        "su-wall-1",
        "su-wall-2",
    ]
    assert design_model["walls"]["east_wall"]["execution"]["operation_ids"] == [
        "wall_east_wall_with_openings"
    ]
    assert sorted(design_model["walls"]["east_wall"]["execution"]["segments"]) == [
        "east_wall"
    ]
    assert design_model["openings"]["east_window"]["execution"]["entity_ids"] == [
        "su-window-marker"
    ]
    assert set(design_model["execution"]["bridge_operations"]) == {
        "wall_east_wall_with_openings"
    }
    assert (
        design_model["execution"]["bridge_operations"][
            "wall_east_wall_with_openings"
        ]["opening_results"][0]["opening_id"]
        == "east_window"
    )
