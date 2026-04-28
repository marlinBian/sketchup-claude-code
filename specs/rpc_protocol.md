# RPC Protocol Specification

## JSON-RPC 2.0 Interface for SketchUp Agent Harness Bridge

This document defines the JSON-RPC 2.0 interface between the Python MCP server and the Ruby SketchUp plugin.

---

## Transport

- **Primary**: Unix domain socket (`/tmp/su_bridge.sock`)
- **Alternative**: Windows named pipe (`\\.\pipe\su_bridge`)

---

## Version

- JSON-RPC version: `2.0`
- Protocol version: `1.0`

---

## Global Structure

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "string",
  "params": {},
  "id": "number | string"
}
```

### Response (Success)

```json
{
  "jsonrpc": "2.0",
  "result": {},
  "id": "number | string"
}
```

### Response (Error)

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": "number",
    "message": "string",
    "data": {}
  },
  "id": "number | string"
}
```

---

## Methods

### `execute_operation`

Executes a modeling operation in SketchUp with automatic rollback on failure.

#### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `method` | string | Yes | Must be `"execute_operation"` |
| `params.operation_id` | string | Yes | Unique operation identifier (e.g., `"op_abc123"`) |
| `params.operation_type` | string | Yes | Operation type (see Operation Types) |
| `params.payload` | object | Yes | Operation-specific parameters |
| `params.rollback_on_failure` | boolean | No | Default `true`. Rollback on failure |
| `id` | number \| string | Yes | Request identifier for response matching |

#### Response (Success)

| Field | Type | Description |
|-------|------|-------------|
| `result.operation_id` | string | Matches request |
| `result.status` | string | `"success"` |
| `result.entity_ids` | string[] | Created/modified entity IDs |
| `result.spatial_delta` | object | Bounding box and volume |
| `result.model_revision` | number | Model revision after operation |
| `result.elapsed_ms` | number | Operation duration in milliseconds |

#### Response (Error)

| Field | Type | Description |
|-------|------|-------------|
| `error.code` | number | Error code (see Error Codes) |
| `error.message` | string | Human-readable error message |
| `error.data` | object | Error details |
| `error.data.operation_id` | string | Failed operation ID |
| `error.data.rollback_status` | string | `"completed"` or `"failed"` |
| `error.data.model_revision` | number | Model revision after rollback |

#### Spatial Delta Object

```json
{
  "bounding_box": {
    "min": [0, 0, 0],
    "max": [1000, 500, 0]
  },
  "volume_mm3": 0
}
```

---

## Operation Types

### `create_face`

Creates a face from vertices.

**Payload:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vertices` | number[][] | Yes | Array of [x, y, z] points in mm |
| `material_id` | string | No | Material to apply |
| `layer` | string | No | Layer name |

**Example:**
```json
{
  "operation_type": "create_face",
  "payload": {
    "vertices": [[0, 0, 0], [1000, 0, 0], [1000, 500, 0], [0, 500, 0]],
    "material_id": "mat_wood_oak",
    "layer": "Furniture"
  }
}
```

### `create_box`

Creates a 3D box (extruded face).

**Payload:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `corner` | number[] | Yes | Bottom-left corner [x, y, z] in mm |
| `width` | number | Yes | Width in mm |
| `depth` | number | Yes | Depth in mm |
| `height` | number | Yes | Height in mm |
| `material_id` | string | No | Material to apply |
| `layer` | string | No | Layer name |

### `create_group`

Creates a group containing entities.

**Payload:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_ids` | string[] | Yes | Entities to group |
| `name` | string | No | Group name |

### `delete_entity`

Deletes entities by ID.

**Payload:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_ids` | string[] | Yes | Entities to delete |

### `set_material`

Applies material to entities.

**Payload:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_ids` | string[] | Yes | Target entities |
| `material_id` | string | Yes | Material ID |

### `query_entities`

Queries entities by type or layer.

**Payload:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entity_type` | string | No | Filter by type (e.g., `"face"`, `"edge"`) |
| `layer` | string | No | Filter by layer |
| `limit` | number | No | Max results (default 100) |

### `query_model_info`

Returns model metadata.

**Payload:**

None required.

---

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32000 | `OPERATION_ERROR` | General operation failure |
| -32001 | `VALIDATION_ERROR` | Invalid parameters or geometry |
| -32002 | `UNDO_FAILED` | Rollback did not complete cleanly |
| -32003 | `SKETCHUP_BUSY` | SketchUp is busy, retry suggested |
| -32004 | `ENTITY_NOT_FOUND` | Referenced entity ID does not exist |
| -32005 | `PERMISSION_DENIED` | Operation not allowed in current context |

---

## Notification (Progress)

Server may send progress notifications (no `id` field):

```json
{
  "jsonrpc": "2.0",
  "method": "progress",
  "params": {
    "operation_id": "op_abc123",
    "status": "in_progress",
    "percent": 50,
    "message": "Creating geometry..."
  }
}
```

---

## Batch Requests

Not supported in v1.0.

---

## Example Conversations

### Create a Face

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_operation",
  "params": {
    "operation_id": "op_001",
    "operation_type": "create_face",
    "payload": {
      "vertices": [[0, 0, 0], [2000, 0, 0], [2000, 1000, 0], [0, 1000, 0]]
    },
    "rollback_on_failure": true
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "operation_id": "op_001",
    "status": "success",
    "entity_ids": ["ent_001"],
    "spatial_delta": {
      "bounding_box": {
        "min": [0, 0, 0],
        "max": [2000, 1000, 0]
      },
      "volume_mm3": 0
    },
    "model_revision": 2,
    "elapsed_ms": 8
  },
  "id": 1
}
```

### Failed Operation with Rollback

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "execute_operation",
  "params": {
    "operation_id": "op_002",
    "operation_type": "create_face",
    "payload": {
      "vertices": [[0, 0, 0], [1000, 0, 0], [500, 0, 0]]
    },
    "rollback_on_failure": true
  },
  "id": 2
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Face creation failed: points are collinear",
    "data": {
      "operation_id": "op_002",
      "rollback_status": "completed",
      "model_revision": 1
    }
  },
  "id": 2
}
```
