"""Tests for command dispatcher JSON-RPC handling."""

import pytest
import json
from mcp_server.protocol.jsonrpc import JsonRpcRequest


class TestJsonRpcRequest:
    """Test JSON-RPC request creation and serialization."""

    def test_create_face_request(self):
        """Test create_face request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_001",
                "operation_type": "create_face",
                "payload": {
                    "vertices": [[0, 0, 0], [1000, 0, 0], [1000, 500, 0]],
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "execute_operation"
        assert data["params"]["operation_type"] == "create_face"
        assert len(data["params"]["payload"]["vertices"]) == 3

    def test_create_wall_request(self):
        """Test create_wall request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_002",
                "operation_type": "create_wall",
                "payload": {
                    "start": [0, 0, 0],
                    "end": [3000, 0, 0],
                    "height": 2400,
                    "thickness": 200,
                    "alignment": "center",
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "create_wall"
        assert data["params"]["payload"]["height"] == 2400

    def test_move_entity_request(self):
        """Test move_entity request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_003",
                "operation_type": "move_entity",
                "payload": {
                    "entity_ids": ["ent_001", "ent_002"],
                    "delta": [1000, 0, 0],
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "move_entity"
        assert data["params"]["payload"]["delta"] == [1000, 0, 0]

    def test_rotate_entity_request(self):
        """Test rotate_entity request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_004",
                "operation_type": "rotate_entity",
                "payload": {
                    "entity_ids": ["ent_001"],
                    "center": [1000, 1000, 0],
                    "axis": "z",
                    "angle": 90,
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "rotate_entity"
        assert data["params"]["payload"]["axis"] == "z"
        assert data["params"]["payload"]["angle"] == 90

    def test_scale_entity_request(self):
        """Test scale_entity request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_005",
                "operation_type": "scale_entity",
                "payload": {
                    "entity_ids": ["ent_001"],
                    "center": [1000, 1000, 0],
                    "scale": 2.0,
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "scale_entity"
        assert data["params"]["payload"]["scale"] == 2.0

    def test_copy_entity_request(self):
        """Test copy_entity request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_006",
                "operation_type": "copy_entity",
                "payload": {
                    "entity_ids": ["ent_001"],
                    "delta": [2000, 0, 0],
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "copy_entity"
        assert data["params"]["payload"]["delta"] == [2000, 0, 0]

    def test_create_door_request(self):
        """Test create_door request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_007",
                "operation_type": "create_door",
                "payload": {
                    "wall_id": "ent_wall_001",
                    "position": [1500, 0],
                    "width": 900,
                    "height": 2100,
                    "swing_direction": "left",
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "create_door"
        assert data["params"]["payload"]["width"] == 900
        assert data["params"]["payload"]["swing_direction"] == "left"

    def test_create_window_request(self):
        """Test create_window request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_008",
                "operation_type": "create_window",
                "payload": {
                    "wall_id": "ent_wall_001",
                    "position": [2000, 0],
                    "width": 1200,
                    "height": 1000,
                    "sill_height": 900,
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "create_window"
        assert data["params"]["payload"]["sill_height"] == 900

    def test_create_stairs_request(self):
        """Test create_stairs request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_009",
                "operation_type": "create_stairs",
                "payload": {
                    "start": [0, 0, 0],
                    "end": [0, 2000, 2400],
                    "width": 1000,
                    "num_steps": 12,
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "create_stairs"
        assert data["params"]["payload"]["num_steps"] == 12

    def test_query_entities_request(self):
        """Test query_entities request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_010",
                "operation_type": "query_entities",
                "payload": {
                    "entity_type": "face",
                    "layer": "Walls",
                    "limit": 50,
                },
                "rollback_on_failure": False,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "query_entities"
        assert data["params"]["payload"]["entity_type"] == "face"

    def test_apply_style_request(self):
        """Test apply_style request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_011",
                "operation_type": "apply_style",
                "payload": {
                    "style_name": "scandinavian",
                    "entity_ids": None,
                },
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "apply_style"
        assert data["params"]["payload"]["style_name"] == "scandinavian"

    def test_export_gltf_request(self):
        """Test export_gltf request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_012",
                "operation_type": "export_gltf",
                "payload": {
                    "output_path": "/tmp/model.gltf",
                    "include_textures": True,
                },
                "rollback_on_failure": False,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "export_gltf"
        assert data["params"]["payload"]["output_path"] == "/tmp/model.gltf"

    def test_export_ifc_request(self):
        """Test export_ifc request format."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "test_013",
                "operation_type": "export_ifc",
                "payload": {
                    "output_path": "/tmp/model.ifc",
                },
                "rollback_on_failure": False,
            }
        )
        data = request.to_dict()

        assert data["params"]["operation_type"] == "export_ifc"
        assert data["params"]["payload"]["output_path"] == "/tmp/model.ifc"


class TestOperationTypes:
    """Test that all operation types are properly formatted."""

    SUPPORTED_OPERATIONS = [
        "create_face",
        "create_box",
        "create_wall",
        "create_group",
        "create_door",
        "create_window",
        "create_stairs",
        "delete_entity",
        "set_material",
        "apply_material",
        "apply_style",
        "query_entities",
        "query_model_info",
        "get_scene_info",
        "place_component",
        "place_lighting",
        "set_camera_view",
        "capture_design",
        "cleanup_model",
        "move_entity",
        "rotate_entity",
        "scale_entity",
        "copy_entity",
        "export_gltf",
        "export_ifc",
    ]

    @pytest.mark.parametrize("operation_type", SUPPORTED_OPERATIONS)
    def test_operation_request_format(self, operation_type):
        """Test that each operation type creates a valid request."""
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"test_{operation_type}",
                "operation_type": operation_type,
                "payload": {},
                "rollback_on_failure": True,
            }
        )
        data = request.to_dict()

        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "execute_operation"
        assert data["params"]["operation_type"] == operation_type
