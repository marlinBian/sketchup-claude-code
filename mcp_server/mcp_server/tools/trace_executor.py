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


def _merged_spatial_delta(segments: dict[str, Any]) -> dict[str, Any]:
    """Return a spatial delta that encloses all executed wall segments."""
    bounds = []
    volume = 0.0
    for segment in segments.values():
        spatial_delta = segment.get("spatial_delta", {})
        bounding_box = spatial_delta.get("bounding_box", {})
        min_point = bounding_box.get("min")
        max_point = bounding_box.get("max")
        if isinstance(min_point, list) and isinstance(max_point, list):
            bounds.append((min_point, max_point))
        volume += float(spatial_delta.get("volume_mm3") or 0)

    if not bounds:
        return {}

    return {
        "bounding_box": {
            "min": [
                min(bound[0][index] for bound in bounds)
                for index in range(3)
            ],
            "max": [
                max(bound[1][index] for bound in bounds)
                for index in range(3)
            ],
        },
        "volume_mm3": volume,
    }


def _sync_wall_execution(
    wall: dict[str, Any],
    *,
    wall_segment_id: str,
    operation_id: str,
    entity_ids: list[str],
    spatial_delta: dict[str, Any],
    status: str | None,
) -> None:
    """Record one or more executed bridge segments on a design_model wall."""
    existing = wall.get("execution")
    if not isinstance(existing, dict):
        existing = {}

    segments = existing.setdefault("segments", {})
    segments[wall_segment_id] = {
        "operation_id": operation_id,
        "entity_ids": entity_ids,
        "spatial_delta": spatial_delta,
        "status": status,
    }

    operation_ids: list[str] = []
    all_entity_ids: list[str] = []
    statuses: list[str | None] = []
    for segment in segments.values():
        segment_operation_id = segment.get("operation_id")
        if segment_operation_id and segment_operation_id not in operation_ids:
            operation_ids.append(segment_operation_id)
        all_entity_ids.extend(str(entity_id) for entity_id in segment.get("entity_ids", []))
        statuses.append(segment.get("status"))

    wall["execution"] = {
        "operation_id": operation_id,
        "operation_ids": operation_ids,
        "entity_ids": all_entity_ids,
        "segments": segments,
        "spatial_delta": _merged_spatial_delta(segments),
        "status": "success" if all(value == "success" for value in statuses) else status,
    }


def _sync_opening_execution(
    design_model: dict[str, Any],
    sync: dict[str, Any],
    *,
    opening_id: str,
    operation_id: str,
    entity_ids: list[str],
    spatial_delta: dict[str, Any],
    status: str | None,
) -> None:
    """Record bridge execution feedback on a hosted opening."""
    if opening_id not in design_model.get("openings", {}):
        return

    opening = design_model["openings"][opening_id]
    opening["execution"] = {
        "operation_id": operation_id,
        "entity_ids": entity_ids,
        "spatial_delta": spatial_delta,
        "status": status,
    }
    if opening_id not in sync["updated_openings"]:
        sync["updated_openings"].append(opening_id)


def _successful_records(execution_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return successful bridge records with an operation id."""
    return [
        record
        for record in execution_report.get("results", [])
        if record.get("ok") and record.get("operation_id")
    ]


def _record_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Return the payload sent for an executed bridge record."""
    payload = (
        record.get("request", {})
        .get("params", {})
        .get("payload", {})
    )
    return payload if isinstance(payload, dict) else {}


def _opening_ids_from_response(record: dict[str, Any]) -> list[str]:
    """Return hosted opening ids included in a bridge response."""
    response_result = record.get("response", {}).get("result", {})
    opening_ids: list[str] = []
    for opening_result in response_result.get("opening_results", []):
        opening_id = opening_result.get("opening_id")
        if opening_id:
            opening_ids.append(str(opening_id))
    return opening_ids


def _prepare_current_sync_targets(
    design_model: dict[str, Any],
    execution_report: dict[str, Any],
    sync: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Clear stale execution state before recording a new successful replay."""
    execution = design_model.setdefault("execution", {})
    previous_operations = execution.get("bridge_operations", {})
    if not isinstance(previous_operations, dict):
        previous_operations = {}

    records = _successful_records(execution_report)
    current_operation_ids = [
        str(record["operation_id"])
        for record in records
    ]
    sync["removed_operations"] = sorted(
        set(previous_operations) - set(current_operation_ids)
    )

    operations: dict[str, Any] = {}
    execution["bridge_operations"] = operations

    walls = design_model.get("walls", {})
    openings = design_model.get("openings", {})
    components = design_model.get("components", {})
    lighting = design_model.get("lighting", {})

    cleared_walls: set[str] = set()
    cleared_openings: set[str] = set()
    cleared_components: set[str] = set()
    cleared_lighting: set[str] = set()

    for record in records:
        payload = _record_payload(record)

        wall_id = payload.get("wall_id")
        if wall_id in walls and wall_id not in cleared_walls:
            walls[wall_id].pop("execution", None)
            cleared_walls.add(str(wall_id))

        opening_id = payload.get("opening_id")
        if opening_id in openings and opening_id not in cleared_openings:
            openings[opening_id].pop("execution", None)
            cleared_openings.add(str(opening_id))

        for hosted_opening_id in _opening_ids_from_response(record):
            if (
                hosted_opening_id in openings
                and hosted_opening_id not in cleared_openings
            ):
                openings[hosted_opening_id].pop("execution", None)
                cleared_openings.add(hosted_opening_id)

        instance_id = payload.get("instance_id")
        if instance_id in components and instance_id not in cleared_components:
            components[instance_id].pop("execution", None)
            components[instance_id].pop("entity_id", None)
            cleared_components.add(str(instance_id))
        elif instance_id in lighting and instance_id not in cleared_lighting:
            lighting[instance_id].pop("execution", None)
            lighting[instance_id].pop("entity_id", None)
            cleared_lighting.add(str(instance_id))

    sync["cleared_walls"] = sorted(cleared_walls)
    sync["cleared_openings"] = sorted(cleared_openings)
    sync["cleared_components"] = sorted(cleared_components)
    sync["cleared_lighting"] = sorted(cleared_lighting)
    return operations


def sync_execution_report_to_design_model(
    design_model: dict[str, Any],
    execution_report: dict[str, Any],
) -> dict[str, Any]:
    """Record bridge execution entity IDs and operation results in design_model."""
    sync = {
        "recorded_operations": [],
        "updated_components": [],
        "updated_lighting": [],
        "updated_spaces": [],
        "updated_space_walls": [],
        "updated_walls": [],
        "updated_openings": [],
        "removed_operations": [],
        "cleared_walls": [],
        "cleared_openings": [],
        "cleared_components": [],
        "cleared_lighting": [],
    }
    operations = _prepare_current_sync_targets(
        design_model,
        execution_report,
        sync,
    )

    for record in _successful_records(execution_report):

        response_result = record.get("response", {}).get("result", {})
        entity_ids = [str(entity_id) for entity_id in response_result.get("entity_ids", [])]
        operation_id = record.get("operation_id")

        operations[operation_id] = {
            "operation_type": record.get("operation_type"),
            "entity_ids": entity_ids,
            "spatial_delta": response_result.get("spatial_delta", {}),
            "status": response_result.get("status"),
        }
        if response_result.get("opening_results"):
            operations[operation_id]["opening_results"] = response_result[
                "opening_results"
            ]
        sync["recorded_operations"].append(operation_id)

        payload = _record_payload(record)
        instance_id = payload.get("instance_id")
        if not instance_id or not entity_ids:
            wall_id = payload.get("wall_id")
            if wall_id and wall_id in design_model.get("walls", {}):
                wall = design_model["walls"][wall_id]
                _sync_wall_execution(
                    wall,
                    wall_segment_id=payload.get("wall_segment_id") or wall_id,
                    operation_id=operation_id,
                    entity_ids=entity_ids,
                    spatial_delta=response_result.get("spatial_delta", {}),
                    status=response_result.get("status"),
                )
                if wall_id not in sync["updated_walls"]:
                    sync["updated_walls"].append(wall_id)
                for opening_result in response_result.get("opening_results", []):
                    opening_id = opening_result.get("opening_id")
                    if not opening_id:
                        continue
                    _sync_opening_execution(
                        design_model,
                        sync,
                        opening_id=opening_id,
                        operation_id=operation_id,
                        entity_ids=[
                            str(entity_id)
                            for entity_id in opening_result.get("entity_ids", [])
                        ],
                        spatial_delta=opening_result.get("spatial_delta", {}),
                        status=opening_result.get("status"),
                    )
                continue

            opening_id = payload.get("opening_id")
            if opening_id and opening_id in design_model.get("openings", {}):
                _sync_opening_execution(
                    design_model,
                    sync,
                    opening_id=opening_id,
                    operation_id=operation_id,
                    entity_ids=entity_ids,
                    spatial_delta=response_result.get("spatial_delta", {}),
                    status=response_result.get("status"),
                )
                continue

            space_id = payload.get("space_id")
            wall_side = payload.get("wall_side")
            if space_id and wall_side and space_id in design_model.get("spaces", {}):
                space = design_model["spaces"][space_id]
                execution = space.setdefault("execution", {})
                walls = execution.setdefault("walls", {})
                walls[wall_side] = {
                    "operation_id": operation_id,
                    "entity_ids": entity_ids,
                    "spatial_delta": response_result.get("spatial_delta", {}),
                    "status": response_result.get("status"),
                }
                if space_id not in sync["updated_spaces"]:
                    sync["updated_spaces"].append(space_id)
                sync["updated_space_walls"].append(f"{space_id}.{wall_side}")
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
