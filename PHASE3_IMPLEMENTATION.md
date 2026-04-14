# Phase 3: Spatial Awareness & Wall Builder

## Summary

This phase adds spatial query and wall creation capabilities to the SCC system.

---

## create_wall JSON-RPC Parameters

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "execute_operation",
  "params": {
    "operation_id": "wall_12345",
    "operation_type": "create_wall",
    "payload": {
      "start": [0, 0, 0],
      "end": [3000, 0, 0],
      "height": 2400,
      "thickness": 150,
      "alignment": "center",
      "material_id": "mat_concrete",
      "layer": "Walls"
    },
    "rollback_on_failure": true
  },
  "id": 42
}
```

### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start` | number[] | Yes | Start point [x, y, z] in mm |
| `end` | number[] | Yes | End point [x, y, z] in mm |
| `height` | number | Yes | Wall height in mm |
| `thickness` | number | Yes | Wall thickness in mm |
| `alignment` | string | No | `"center"` (default), `"inner"`, `"outer"` |
| `material_id` | string | No | Material ID |
| `layer` | string | No | Layer name (default: `"Walls"`) |

### Success Response

```json
{
  "jsonrpc": "2.0",
  "result": {
    "operation_id": "wall_12345",
    "status": "success",
    "entity_ids": ["<group_entity_id>"],
    "spatial_delta": {
      "bounding_box": {
        "min": [-75, 0, 0],
        "max": [3075, 150, 2400]
      },
      "volume_mm3": 110250000
    },
    "model_revision": 2,
    "elapsed_ms": 15
  },
  "id": 42
}
```

---

## Wall Alignment Logic

See `specs/spatial_constraints.md` for full specification.

### Center Alignment (default)
- Wall centered on the line between start and end
- `offset = thickness / 2`

### Inner Alignment
- Wall inside the line (maximizes exterior space)
- `offset = thickness`

### Outer Alignment
- Wall outside the line (weatherproofing)
- `offset = 0`

---

## Files Modified/Created

### Python (mcp_server/)

**`mcp_server/tools/query_tools.py`** - Updated with:
- `get_scene_info()` - Queries model bounding box, entity counts, layers
- `query_entities()` - Filters entities by type/layer
- `query_model_info()` - Alias for get_scene_info

**`mcp_server/server.py`** - Updated with FastMCP tools:
- `@mcp.tool() get_scene_info()` - Scene info tool
- `@mcp.tool() create_wall()` - Wall creation tool with 8 params
- `@mcp.tool() create_face()` - Face creation tool
- `@mcp.tool() create_box()` - Box creation tool

### Ruby (su_bridge/)

**`su_bridge/lib/su_bridge/entities/wall_builder.rb`** - New:
- `WallBuilder.create()` - Creates wall with alignment
- `WallBuilder.calculate_vertices()` - 8-vertex box calculation
- `WallBuilder.create_wall_group()` - Creates SketchUp group
- `WallBuilder.spatial_delta()` - Returns bounding box and volume
- Internal `Vector3d` class for calculations

**`su_bridge/lib/su_bridge/command_dispatcher.rb`** - Updated:
- Added `"create_wall" => :handle_create_wall`
- Added `"get_scene_info" => :handle_get_scene_info`
- Implemented `handle_create_wall()`
- Implemented `handle_get_scene_info()`

**`su_bridge/lib/su_bridge.rb`** - Updated:
- Added `require "su_bridge/entities/wall_builder"`

---

## MCP Tool Signatures (Python)

### get_scene_info()
```python
@mcp.tool()
async def get_scene_info() -> TextContent:
    """Get current SketchUp scene information."""
```

### create_wall()
```python
@mcp.tool()
async def create_wall(
    start_x: float,
    start_y: float,
    start_z: float,
    end_x: float,
    end_y: float,
    end_z: float,
    height: float,
    thickness: float,
    alignment: str = "center",
) -> TextContent:
```

### create_face()
```python
@mcp.tool()
async def create_face(
    vertices: list[list[float]],
    layer: str | None = None,
) -> TextContent:
```

### create_box()
```python
@mcp.tool()
async def create_box(
    corner_x: float,
    corner_y: float,
    corner_z: float,
    width: float,
    depth: float,
    height: float,
) -> TextContent:
```

---

## Verification

### Ruby Syntax Check
```bash
cd su_bridge
ruby -c lib/su_bridge/command_dispatcher.rb
ruby -c lib/su_bridge/entities/wall_builder.rb
ruby -c lib/su_bridge.rb
```

### Python Syntax Check
```bash
cd mcp_server
python3 -c "import ast; ast.parse(open('mcp_server/server.py').read())"
```

### Load in SketchUp
```ruby
load '/path/to/sketchup-claude-code/su_bridge/lib/su_bridge.rb'
SuBridge::ServerListener.new.start

# Test wall creation manually
require 'json'
sock = UNIXSocket.new('/tmp/su_bridge.sock')
request = {
  jsonrpc: '2.0',
  method: 'execute_operation',
  params: {
    operation_id: 'test_wall',
    operation_type: 'create_wall',
    payload: {
      start: [0, 0, 0],
      end: [3000, 0, 0],
      height: 2400,
      thickness: 150,
      alignment: 'center'
    }
  },
  id: 1
}
sock.write(JSON.generate(request) + "\n")
puts sock.read
sock.close
```

---

## Telemetry (Entity ID Return)

The wall creation response includes the group entity_id:

```json
{
  "result": {
    "entity_ids": ["<SketchUp group entity ID>"],
    "spatial_delta": {
      "bounding_box": {...},
      "volume_mm3": 110250000
    },
    ...
  }
}
```

This entity_id can be used for:
- Subsequent operations on the wall
- Grouping with other entities
- Material application
- Deletion if needed
