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


def sync_execution_report_to_design_model(
    design_model: dict[str, Any],
    execution_report: dict[str, Any],
) -> dict[str, Any]:
    """Record bridge execution entity IDs and operation results in design_model."""
    sync = {
        "recorded_operations": [],
        "updated_components": [],
        "updated_lighting": [],
    }
    execution = design_model.setdefault("execution", {})
    operations = execution.setdefault("bridge_operations", {})

    for record in execution_report.get("results", []):
        if not record.get("ok"):
            continue

        response_result = record.get("response", {}).get("result", {})
        entity_ids = [str(entity_id) for entity_id in response_result.get("entity_ids", [])]
        operation_id = record.get("operation_id")
        if not operation_id:
            continue

        operations[operation_id] = {
            "operation_type": record.get("operation_type"),
            "entity_ids": entity_ids,
            "spatial_delta": response_result.get("spatial_delta", {}),
            "status": response_result.get("status"),
        }
        sync["recorded_operations"].append(operation_id)

        payload = (
            record.get("request", {})
            .get("params", {})
            .get("payload", {})
        )
        instance_id = payload.get("instance_id")
        if not instance_id or not entity_ids:
            continue

        if instance_id in design_model.get("components", {}):
            component = design_model["components"][instance_id]
            component["entity_id"] = entity_ids[0]
            component["execution"] = {"operation_id": operation_id}
            sync["updated_components"].append(instance_id)
        elif instance_id in design_model.get("lighting", {}):
            lighting = design_model["lighting"][instance_id]
            lighting["entity_id"] = entity_ids[0]
            lighting["execution"] = {"operation_id": operation_id}
            sync["updated_lighting"].append(instance_id)

    return sync
