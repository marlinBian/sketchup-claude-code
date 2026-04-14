"""Model and entity query tools."""

from typing import Any
from mcp_server.bridge.socket_bridge import SocketBridge
from mcp_server.protocol.jsonrpc import JsonRpcRequest


async def get_scene_info() -> dict[str, Any]:
    """Get current SketchUp scene information.

    Returns model bounding box, entity counts by type, and layer list.

    Returns:
        Dict with bounding_box, entity_counts, layers, and model_revision.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"query_{id(get_scene_info)}",
                "operation_type": "get_scene_info",
                "payload": {},
                "rollback_on_failure": False,
            }
        )

        response = bridge.send(request.to_dict())

        if "error" in response:
            raise RuntimeError(f"Query failed: {response['error']['message']}")

        return response.get("result", {})

    finally:
        bridge.disconnect()


async def query_entities(
    entity_type: str | None = None,
    layer: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Query entities by type or layer.

    Args:
        entity_type: Filter by type (e.g., "face", "edge", "group")
        layer: Filter by layer name
        limit: Max results (default 100)

    Returns:
        Dict with entity_ids list and spatial_delta.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"query_{id(query_entities)}",
                "operation_type": "query_entities",
                "payload": {
                    "entity_type": entity_type,
                    "layer": layer,
                    "limit": limit,
                },
                "rollback_on_failure": False,
            }
        )

        response = bridge.send(request.to_dict())

        if "error" in response:
            raise RuntimeError(f"Query failed: {response['error']['message']}")

        return response.get("result", {})

    finally:
        bridge.disconnect()


async def query_model_info() -> dict[str, Any]:
    """Return model metadata.

    Returns:
        Dict with model_units, model_bounds, and entity_counts.
    """
    return await get_scene_info()
