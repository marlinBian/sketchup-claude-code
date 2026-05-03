"""Export tools for glTF and IFC."""

from typing import Any
from mcp_server.bridge.socket_bridge import SocketBridge
from mcp_server.protocol.jsonrpc import JsonRpcRequest


CLEAN_SCENE_AUDIT_LAYER = "Layer0"
CLEAN_SCENE_AUDIT_LIMIT = 1000


def _scene_audit_request(stage: str) -> dict[str, Any]:
    return JsonRpcRequest(
        method="execute_operation",
        params={
            "operation_id": f"save_model_clean_scene_audit_{stage}",
            "operation_type": "query_entities",
            "payload": {
                "entity_type": None,
                "layer": CLEAN_SCENE_AUDIT_LAYER,
                "limit": CLEAN_SCENE_AUDIT_LIMIT,
            },
            "rollback_on_failure": False,
        },
    ).to_dict()


def _summarize_scene_audit_response(response: dict[str, Any], stage: str) -> dict[str, Any]:
    if "error" in response:
        raise RuntimeError(f"Scene audit failed {stage}: {response['error']['message']}")

    result = response.get("result", {})
    entities = result.get("entities", []) if isinstance(result, dict) else []
    unexpected_entities = [
        {
            "entityID": entity.get("entityID"),
            "type": entity.get("type"),
            "layer": entity.get("layer"),
            "bounding_box": entity.get("bounding_box"),
        }
        for entity in entities
        if isinstance(entity, dict) and entity.get("layer") == CLEAN_SCENE_AUDIT_LAYER
    ]
    return {
        "status": "passed" if not unexpected_entities else "failed",
        "stage": stage,
        "layer": CLEAN_SCENE_AUDIT_LAYER,
        "unexpected_entity_count": len(unexpected_entities),
        "unexpected_entities": unexpected_entities,
    }


def _raise_if_scene_audit_failed(summary: dict[str, Any]) -> None:
    if summary["status"] == "passed":
        return
    raise RuntimeError(
        "Clean scene audit failed "
        f"{summary['stage']}: {summary['unexpected_entity_count']} unexpected "
        f"{summary['layer']} entities remain"
    )


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


async def save_skp_model(
    output_path: str,
    *,
    require_clean_scene: bool = False,
) -> dict[str, Any]:
    """Save the active SketchUp model to a .skp file.

    Args:
        output_path: Destination file path. The Ruby bridge appends .skp when omitted.
        require_clean_scene: When true, fail if top-level Layer0 entities are
            present before or after saving.

    Returns:
        Dict with save status, file path, and model_revision.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        clean_scene_audit: dict[str, Any] | None = None
        if require_clean_scene:
            before_save = _summarize_scene_audit_response(
                bridge.send(_scene_audit_request("before_save")),
                "before_save",
            )
            _raise_if_scene_audit_failed(before_save)
            clean_scene_audit = {"before_save": before_save}

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"save_model_{id(save_skp_model)}",
                "operation_type": "save_model",
                "payload": {
                    "output_path": output_path,
                },
                "rollback_on_failure": False,
            }
        )

        response = bridge.send(request.to_dict())

        if "error" in response:
            raise RuntimeError(f"Save failed: {response['error']['message']}")

        result = response.get("result", {})
        if require_clean_scene:
            after_save = _summarize_scene_audit_response(
                bridge.send(_scene_audit_request("after_save")),
                "after_save",
            )
            _raise_if_scene_audit_failed(after_save)
            clean_scene_audit["after_save"] = after_save  # type: ignore[index]
            if isinstance(result, dict):
                result["clean_scene_audit"] = clean_scene_audit

        return result

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
