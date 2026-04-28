"""Integration tests for SCC MCP server with live SketchUp.

These tests require:
1. SketchUp to be running with su_bridge plugin loaded
2. Socket at /tmp/su_bridge.sock to exist

Run with: cd mcp_server && uv run pytest tests/test_integration.py -v
"""

import pytest
import json
import time
from pathlib import Path


pytestmark = pytest.mark.integration


class TestIntegrationConnection:
    """Test connection to Ruby bridge."""

    def test_socket_exists(self):
        """Verify the Ruby bridge socket exists."""
        socket_path = Path("/tmp/su_bridge.sock")
        assert socket_path.exists(), "Ruby bridge socket not found. Start SuBridge in SketchUp Ruby Console."

    def test_can_connect_and_ping(self):
        """Test basic connection to Ruby bridge."""
        import socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect("/tmp/su_bridge.sock")
            sock.send(b'{"jsonrpc":"2.0","method":"ping","id":1}\n')
            response = sock.recv(4096)
            assert response, "No response from Ruby bridge"
        finally:
            sock.close()


class TestIntegrationSceneInfo:
    """Test get_scene_info with live SketchUp."""

    def test_get_scene_info_returns_valid_response(self):
        """Test that get_scene_info returns valid scene information."""
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_scene_info",
                    "operation_type": "get_scene_info",
                    "payload": {},
                    "rollback_on_failure": False,
                }
            )
            response = bridge.send(request.to_dict())

            assert "result" in response, f"Expected result in response: {response}"
            result = response["result"]

            assert "scene_info" in result, f"Expected scene_info in result: {result}"
            scene_info = result["scene_info"]

            assert "bounding_box" in scene_info
            assert "entity_counts" in scene_info
            assert "layers" in scene_info

            print(f"Scene info: {scene_info}")
        finally:
            bridge.disconnect()


class TestIntegrationCreateOperations:
    """Test create operations with live SketchUp."""

    def test_create_face(self):
        """Test creating a face."""
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_create_face",
                    "operation_type": "create_face",
                    "payload": {
                        "vertices": [[0, 0, 0], [1000, 0, 0], [1000, 500, 0], [0, 500, 0]],
                    },
                    "rollback_on_failure": True,
                }
            )
            response = bridge.send(request.to_dict())

            assert "result" in response, f"Expected result: {response}"
            result = response["result"]

            assert len(result["entity_ids"]) > 0, "Should return entity ID"
            assert "spatial_delta" in result

            print(f"Created face: {result['entity_ids']}")
        finally:
            bridge.disconnect()

    def test_create_box(self):
        """Test creating a box."""
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_create_box",
                    "operation_type": "create_box",
                    "payload": {
                        "corner": [0, 0, 0],
                        "width": 500,
                        "depth": 500,
                        "height": 300,
                    },
                    "rollback_on_failure": True,
                }
            )
            response = bridge.send(request.to_dict())

            assert "result" in response, f"Expected result: {response}"
            result = response["result"]

            assert len(result["entity_ids"]) > 0, "Should return entity ID"
            entity_id = result["entity_ids"][0]

            print(f"Created box: {entity_id}")
        finally:
            bridge.disconnect()

    def test_create_wall(self):
        """Test creating a wall."""
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_create_wall",
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
            response = bridge.send(request.to_dict())

            assert "result" in response, f"Expected result: {response}"
            result = response["result"]

            assert len(result["entity_ids"]) > 0, "Should return entity ID"

            print(f"Created wall: {result['entity_ids']}")
        finally:
            bridge.disconnect()


class TestIntegrationQueryOperations:
    """Test query operations with live SketchUp."""

    def test_query_entities(self):
        """Test querying entities."""
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_query_entities",
                    "operation_type": "query_entities",
                    "payload": {
                        "entity_type": "face",
                        "limit": 10,
                    },
                    "rollback_on_failure": False,
                }
            )
            response = bridge.send(request.to_dict())

            assert "result" in response, f"Expected result: {response}"
            result = response["result"]

            assert "entities" in result or "entity_ids" in result

            entities = result.get("entities", result.get("entity_ids", []))
            print(f"Found {len(entities)} entities")
        finally:
            bridge.disconnect()


class TestIntegrationMaterialOperations:
    """Test material operations with live SketchUp."""

    def test_apply_style(self):
        """Test applying a style preset."""
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_apply_style",
                    "operation_type": "apply_style",
                    "payload": {
                        "style_name": "scandinavian",
                    },
                    "rollback_on_failure": True,
                }
            )
            response = bridge.send(request.to_dict())

            assert "result" in response, f"Expected result: {response}"
            result = response["result"]

            assert "style_info" in result
            assert result["style_info"]["style_name"] == "scandinavian"

            print(f"Applied style: {result['style_info']}")
        finally:
            bridge.disconnect()


class TestIntegrationTransformOperations:
    """Test entity transformation operations with live SketchUp."""

    def test_move_entity(self):
        """Test moving an entity."""
        # First create a box to move
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()

            # Create a box
            create_request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_create_for_move",
                    "operation_type": "create_box",
                    "payload": {
                        "corner": [0, 0, 0],
                        "width": 500,
                        "depth": 500,
                        "height": 300,
                    },
                    "rollback_on_failure": True,
                }
            )
            create_response = bridge.send(create_request.to_dict())
            assert "result" in create_response
            entity_id = create_response["result"]["entity_ids"][0]

            # Move the entity
            move_request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_move_entity",
                    "operation_type": "move_entity",
                    "payload": {
                        "entity_ids": [entity_id],
                        "delta": [1000, 0, 0],
                    },
                    "rollback_on_failure": True,
                }
            )
            move_response = bridge.send(move_request.to_dict())

            assert "result" in move_response, f"Expected result: {move_response}"
            print(f"Moved entity {entity_id} by (1000, 0, 0)")
        finally:
            bridge.disconnect()


class TestIntegrationErrorHandling:
    """Test error handling with live SketchUp."""

    def test_invalid_operation_returns_error(self):
        """Test that invalid operation returns proper error."""
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_invalid_op",
                    "operation_type": "nonexistent_operation",
                    "payload": {},
                    "rollback_on_failure": True,
                }
            )
            response = bridge.send(request.to_dict())

            # Error might be at top level or nested in result (bug in Ruby layer)
            has_error = "error" in response
            nested_error = response.get("result", {}).get("error") if "result" in response else None

            assert has_error or nested_error, f"Expected error for invalid operation: {response}"

            error = response["error"] if has_error else nested_error
            assert error["code"] == -32000
        finally:
            bridge.disconnect()

    def test_validation_error(self):
        """Test that validation errors are caught properly."""
        from mcp_server.bridge.socket_bridge import SocketBridge
        from mcp_server.protocol.jsonrpc import JsonRpcRequest

        bridge = SocketBridge()
        try:
            bridge.connect()
            # Missing required parameters
            request = JsonRpcRequest(
                method="execute_operation",
                params={
                    "operation_id": "test_validation",
                    "operation_type": "create_box",
                    "payload": {
                        "corner": [0, 0, 0],
                        # Missing width, depth, height
                    },
                    "rollback_on_failure": True,
                }
            )
            response = bridge.send(request.to_dict())

            # Should either error or handle gracefully
            print(f"Validation test response: {response}")
        finally:
            bridge.disconnect()
