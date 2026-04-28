"""Execute bridge operation traces against the SketchUp socket bridge."""

from typing import Any

from mcp_server.bridge.socket_bridge import SocketBridge
from mcp_server.protocol.jsonrpc import JsonRpcRequest


def bridge_request_for_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Convert an operation trace entry to a JSON-RPC request."""
    return JsonRpcRequest(
        method="execute_operation",
        params={
            "operation_id": operation["operation_id"],
            "operation_type": operation["operation_type"],
            "payload": operation.get("payload", {}),
            "rollback_on_failure": operation.get("rollback_on_failure", True),
        },
    ).to_dict()


def execute_bridge_operations(
    operations: list[dict[str, Any]],
    bridge: SocketBridge | None = None,
    stop_on_error: bool = True,
) -> dict[str, Any]:
    """Execute bridge operation trace entries in order.

    The caller may inject a fake bridge for tests. When no bridge is provided,
    this function creates a SocketBridge and disconnects it before returning.
    """
    active_bridge = bridge or SocketBridge()
    owns_bridge = bridge is None
    results: list[dict[str, Any]] = []

    try:
        for index, operation in enumerate(operations):
            request = bridge_request_for_operation(operation)
            response = active_bridge.send(request)
            record = {
                "index": index,
                "operation_id": operation["operation_id"],
                "operation_type": operation["operation_type"],
                "request": request,
                "response": response,
                "ok": "error" not in response,
            }
            results.append(record)

            if stop_on_error and not record["ok"]:
                break
    finally:
        if owns_bridge:
            active_bridge.disconnect()

    return {
        "status": "success" if all(result["ok"] for result in results) else "failed",
        "executed_count": len(results),
        "requested_count": len(operations),
        "results": results,
    }
