"""Export tools for glTF and IFC."""

from typing import Any
from mcp_server.bridge.socket_bridge import SocketBridge
from mcp_server.protocol.jsonrpc import JsonRpcRequest


async def export_gltf(output_path: str, include_textures: bool = True) -> dict[str, Any]:
    """Export model to glTF format.

    Args:
        output_path: Destination file path
        include_textures: Whether to embed textures

    Returns:
        Dict with export status, file path, and model_revision.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"export_gltf_{id(export_gltf)}",
                "operation_type": "export_gltf",
                "payload": {
                    "output_path": output_path,
                    "include_textures": include_textures,
                },
                "rollback_on_failure": False,
            }
        )

        response = bridge.send(request.to_dict())

        if "error" in response:
            raise RuntimeError(f"Export failed: {response['error']['message']}")

        return response.get("result", {})

    finally:
        bridge.disconnect()


async def export_ifc(output_path: str) -> dict[str, Any]:
    """Export model to IFC format.

    Args:
        output_path: Destination file path

    Returns:
        Dict with export status, file path, and model_revision.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"export_ifc_{id(export_ifc)}",
                "operation_type": "export_ifc",
                "payload": {
                    "output_path": output_path,
                },
                "rollback_on_failure": False,
            }
        )

        response = bridge.send(request.to_dict())

        if "error" in response:
            raise RuntimeError(f"Export failed: {response['error']['message']}")

        return response.get("result", {})

    finally:
        bridge.disconnect()
