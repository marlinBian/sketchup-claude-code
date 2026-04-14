# SCC (SketchUp-Claude-Code) Project Constitution

## Overview

**SCC** enables bidirectional communication between an LLM (Claude Code) and SketchUp for interior design automation. Designers issue natural language commands like "add a 2m x 3m window on the south wall" and receive confirmation with spatial feedback.

## Architecture

```
                    ┌─────────────────────────────┐
                    │     Claude Code (LLM)       │
                    │     User Natural Language   │
                    └──────────────┬──────────────┘
                                   │ JSON-RPC 2.0 / STDIO
                    ┌──────────────▼──────────────┐
                    │     /mcp_server/            │
                    │  Python MCP Server         │
                    │  - FastMCP (mcp-python-sdk) │
                    │  - Space computation engine │
                    │  - Protocol serializer      │
                    └──────────────┬──────────────┘
                                   │ Unix Socket / Named Pipe
                    ┌──────────────▼──────────────┐
                    │     /su_bridge/             │
                    │  Ruby SketchUp Plugin      │
                    │  - Non-blocking listener    │
                    │  - UI.start_timer dispatch  │
                    │  - Undo transaction wrapper │
                    └──────────────┬──────────────┘
                                   │ SketchUp Ruby API
                    ┌──────────────▼──────────────┐
                    │     SketchUp Application    │
                    │  - 3D modeling engine       │
                    │  - Scene graph              │
                    └─────────────────────────────┘
```

## Plugin Marketplace Distribution

SCC is distributed as a Claude Code plugin marketplace.

### First-Time Installation

**Important:** After cloning, run the setup script once:

```bash
git clone https://github.com/avenir/sketchup-claude-code.git
cd sketchup-claude-code
./setup.sh
```

The setup script will:
1. Install `uv` (if not present)
2. Install Python dependencies for the MCP server
3. Guide you through SketchUp Ruby plugin installation

### Adding the Plugin to Claude Code

```bash
/plugin marketplace add https://github.com/avenir/sketchup-claude-code
/plugin install sketchup-claude-code@sketchup-claude-code
```

### SketchUp Ruby Plugin Installation

The Ruby plugin must be installed manually in SketchUp:

1. Find your SketchUp Plugins folder:
   - macOS: `~/Library/Application Support/SketchUp/SketchUp 2024/SketchUp/Plugins/`
   - Windows: `C:\Users\YourName\AppData\Roaming\SketchUp\SketchUp 2024\SketchUp\Plugins\`

2. Copy the `su_bridge/` folder to the Plugins folder

3. Restart SketchUp

4. In SketchUp Ruby Console, run:
   ```ruby
   load 'su_bridge/lib/su_bridge.rb'
   SuBridge.start
   ```

### Updating

```bash
git pull && ./setup.sh
```

**Plugin components:**
- `mcpServers.sketchup-mcp`: Python FastMCP server for Claude Code tools
- Skills for design workflows (in `skills/` directory)

## Directory Structure

```
sketchup-claude-code/
├── CLAUDE.md                          # Project constitution (this file)
├── setup.sh                           # First-time setup script
├── .claude-plugin/                    # Claude Code plugin marketplace
│   ├── marketplace.json               # Marketplace catalog for /plugin marketplace add
│   └── plugin.json                    # Plugin manifest with MCP server config
├── mcp_server/                        # Python logic layer
│   ├── pyproject.toml
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py                  # FastMCP entry point
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── model_tools.py         # Entity creation/deletion
│   │   │   ├── query_tools.py         # Model queries
│   │   │   └── export_tools.py        # glTF/IFC export
│   │   ├── resources/
│   │   │   ├── __init__.py
│   │   │   ├── model_resource.py      # model://current
│   │   │   └── entity_resource.py     # entity://{id}
│   │   ├── protocol/
│   │   │   ├── __init__.py
│   │   │   ├── jsonrpc.py             # JSON-RPC 2.0 serialization
│   │   │   ├── spatial.py            # mm/Z-up coordinate utilities
│   │   │   └── rollback.py            # Atomic operation with rollback
│   │   └── bridge/
│   │       ├── __init__.py
│   │       └── socket_bridge.py       # Unix socket client to su_bridge
│   └── tests/
├── su_bridge/                         # Ruby SketchUp plugin layer
│   ├── su_bridge.rb                  # Main entry point /loader
│   ├── su_bridge/
│   │   ├── __init__.rb
│   │   ├── server_listener.rb         # Non-blocking socket server
│   │   ├── command_dispatcher.rb     # Routes JSON-RPC to Ruby API
│   │   ├── undo_manager.rb            # Undo transaction wrapper
│   │   ├── entities/
│   │   │   ├── __init__.rb
│   │   │   ├── face_builder.rb        # Face/mesh creation
│   │   │   ├── group_builder.rb       # Group/component handling
│   │   │   └── material_applier.rb    # Material/texture assignment
│   │   └── protocol/
│   │       ├── __init__.rb
│   │       └── json_rpc_handler.rb    # Parse/validate incoming RPC
│   └── spec/
│       └── su_bridge_spec.rb         # RSpec tests
├── specs/                             # Core protocol definitions
│   ├── rpc_protocol.md                # JSON-RPC 2.0 interface spec
│   ├── spatial_constraints.md          # Coordinate system, constraints
│   └── undo_semantics.md              # Atomic rollback semantics
└── skills/                            # Designer workflow instruction sets
    ├── SKILL.md                       # Root skill manifest
    ├── designer_workflow/              # Interior design command suite
    │   └── SKILL.md
    └── common_operations/            # Wall/door/window operations
        └── SKILL.md
```

---

## Core Principles

### Principle 1: Bidirectional Communication

All modeling commands MUST return state feedback. No fire-and-forget operations. Every `execute_operation` call returns the affected entity IDs, spatial delta, and model revision.

**Required response fields:**
- `entity_ids`: List of created/modified entity IDs
- `spatial_delta`: Bounding box and volume of changes
- `model_revision`: Current model revision number
- `elapsed_ms`: Operation duration

### Principle 2: Undo Transaction Wrapper

Every mutating operation MUST be wrapped in a SketchUp Undo transaction. If the Ruby layer throws any exception, the transaction MUST be rolled back and an error returned to the Python layer.

**Rules:**
1. Begin Undo operation before any mutation
2. If exception occurs: call `UndoManager.rollback` and return error
3. If success: `UndoManager.release` and return result
4. Never leave a transaction open on error

### Principle 3: mm / Z-Up Coordinate System

All coordinates in the protocol are in **millimeters** with **Z-axis pointing up**. The Python layer is responsible for any unit conversion from user-facing units (meters, feet, inches) to mm before sending commands.

**Conventions:**
- Internal units: millimeters (mm)
- Z-axis: points upward (standard SketchUp)
- Origin: SketchUp model origin
- No unit suffixes in protocol (e.g., `1000` means 1000mm, not 1m)

### Principle 4: Atomic Operations with Rollback

Each `execute_operation` request is atomic. On failure, the operation is rolled back and a structured error returned. Partial success is not allowed.

**Flow:**
1. Validate request parameters
2. Begin transaction
3. Execute operation
4. On success: commit and return result
5. On failure: rollback and return error with `rollback_status: "completed"`

### Principle 5: Non-Blocking SketchUp Interaction

SketchUp UI must never freeze. All Ruby operations use `UI.start_timer` for deferred execution. Long operations report progress via incremental status updates.

**Requirements:**
- Socket listener runs on main thread via `UI.start_timer`
- No blocking I/O in Ruby callbacks
- Progress updates via incremental responses
- Timeout handling for long operations

---

## Protocol: execute_operation

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "execute_operation",
  "params": {
    "operation_id": "op_abc123",
    "operation_type": "create_face",
    "payload": {
      "vertices": [[0, 0, 0], [1000, 0, 0], [1000, 500, 0], [0, 500, 0]],
      "material_id": "mat_wood_oak",
      "layer": "Furniture"
    },
    "rollback_on_failure": true
  },
  "id": 42
}
```

### Success Response

```json
{
  "jsonrpc": "2.0",
  "result": {
    "operation_id": "op_abc123",
    "status": "success",
    "entity_ids": ["ent_001", "ent_002"],
    "spatial_delta": {
      "bounding_box": {
        "min": [0, 0, 0],
        "max": [1000, 500, 0]
      },
      "volume_mm3": 0
    },
    "model_revision": 17,
    "elapsed_ms": 12
  },
  "id": 42
}
```

### Error Response (with rollback)

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Face creation failed: points are collinear",
    "data": {
      "operation_id": "op_abc123",
      "rollback_status": "completed",
      "model_revision": 16
    }
  },
  "id": 42
}
```

### Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32000 | `OPERATION_ERROR` | General operation failure |
| -32001 | `VALIDATION_ERROR` | Invalid parameters or geometry |
| -32002 | `UNDO_FAILED` | Rollback did not complete cleanly |
| -32003 | `SKETCHUP_BUSY` | SketchUp is busy, retry suggested |
| -32004 | `ENTITY_NOT_FOUND` | Referenced entity ID does not exist |
| -32005 | `PERMISSION_DENIED` | Operation not allowed in current context |

---

## Asset Management

### Component Library

The component library is located at `mcp_server/assets/library.json` and contains furniture definitions with metadata.

**Library Entry Structure:**
```json
{
  "id": "sofa_modern_double",
  "name": "现代双人沙发",
  "name_en": "Modern Double Sofa",
  "category": "living_room",
  "skp_path": "${SKETCHUP_ASSETS}/furniture/sofa_modern_double.skp",
  "default_dimensions": {"width": 2000, "depth": 900, "height": 850},
  "insertion_point": {
    "description": "前缘中心",
    "offset": [0, 0, 0],
    "face_direction": "+y"
  },
  "bounds": {"min": [0, 0, 0], "max": [2000, 900, 850]}
}
```

### SKP Asset Path Resolution

SKP paths support environment variable substitution:
- `${SKETCHUP_ASSETS}` - Resolved from `SKETCHUP_ASSETS` env var
- Default: `/Applications/SketchUp.app/Contents/Resources`

**Setting the asset path:**
```bash
export SKETCHUP_ASSETS=/path/to/your/sketchup_assets
```

### Managing Local .skp Models

1. **Organize by category:**
   ```
   SKETCHUP_ASSETS/
   ├── furniture/
   │   ├── sofa_modern_double.skp
   │   ├── dining_table_rect.skp
   │   └── bed_double.skp
   ├── fixtures/
   │   └── lamp_floor.skp
   └── structural/
       └── column.skp
   ```

2. **Add new components:**
   - Create or obtain .skp file
   - Place in appropriate category folder
   - Add entry to `library.json` with:
     - Unique `id`
     - `name` (Chinese)
     - `name_en` (English)
     - `skp_path` relative to `SKETCHUP_ASSETS`
     - `default_dimensions` in mm
     - `insertion_point` offset
     - `bounds` for collision detection

3. **Component requirements:**
   - Units: millimeters
   - Origin: at insertion point
   - Forward face: +Y direction
   - Scale: realistic 1:1 dimensions

### Placement Rules

Default clearances from `library.json`:
| Rule | Value |
|------|-------|
| `min_clearance` | 600mm |
| `door_clearance` | 900mm |
| `walkway_width` | 800mm |

---

## Sketchfab 3D Model Search

SCC includes tools to search Sketchfab's library of Creative Commons licensed 3D models and download them for use in SketchUp.

### Search for Models

```python
# Search Sketchfab for furniture and objects
search_sketchfab_models(query: "modern sofa", count: 10)
search_sketchfab_models(query: "floor lamp", count: 5)
search_sketchfab_models(query: "potted plant interior", sort: "likes")
```

### Download Models

```python
# Download a model (OBJ format recommended for SketchUp)
download_sketchfab_model(model_uid: "abc123...", format_hint: "obj")

# Search and download in one step
search_and_download_sketchfab(query: "minimalist coffee table")
```

### Downloaded Model Storage

Models are downloaded to: `~/SketchUp/SCC/downloaded_models/`

After download, import into SketchUp via **File > Import** and select the downloaded file.

### Workflow: Adding a New Object

1. **Search**: `search_sketchfab_models(query: "modern gray sofa")`
2. **Review results**: Check view count, likes, and description
3. **Download**: `download_sketchfab_model(model_uid: "xxx", format_hint: "obj")`
4. **Import**: In SketchUp, use File > Import to add the .obj file
5. **Position**: Use SCC tools to position and scale the imported model

### Model Format Notes

| Format | SketchUp Compatibility | Notes |
|--------|------------------------|-------|
| OBJ | Best | Native import support |
| GLTF/GLB | Requires conversion | Use external converter |
| FBX | Limited | May lose materials |

---

## Design Version Control

### Overview

Designs are versioned using a snapshot system that captures the complete model state at key milestones.

### Version File Structure

```
designs/
└── project_name/
    ├── v1.0_initial/
    │   ├── model.skp
    │   ├── snapshot_客厅_birdseye.png
    │   ├── snapshot_主卧_perspective.png
    │   └── metadata.json
    ├── v1.1_after_furniture/
    │   ├── model.skp
    │   └── metadata.json
    └── v2.0_final/
        ├── model.skp
        └── metadata.json
```

### Metadata Format (metadata.json)

```json
{
  "version": "1.0",
  "created_at": "2026-04-14T10:30:00Z",
  "created_by": "Claude",
  "description": "Initial layout with walls and basic furniture",
  "camera_views": {
    "living_room_birdseye": "snapshot_客厅_birdseye.png",
    "master_bedroom": "snapshot_主卧_perspective.png"
  },
  "entity_count": 142,
  "style_preset": "japandi_cream",
  "components_used": [
    "sofa_modern_double",
    "dining_table_rect",
    "bed_double"
  ]
}
```

### Snapshot Naming Convention

Format: `snapshot_{space}_{view_preset}.png`

Examples:
- `snapshot_客厅_panoramic.png`
- `snapshot_主卧_birdseye.png`
- `snapshot_餐厅_perspective.png`

### Version Control Commands

#### Save Version
```python
async def save_version(
    project_name: str,
    version_tag: str,
    description: str,
    output_dir: str = "./designs"
) -> dict[str, Any]:
    """Save current model state as a versioned snapshot."""
```

#### Load Version
```python
async def load_version(
    project_name: str,
    version_tag: str,
    output_dir: str = "./designs"
) -> dict[str, Any]:
    """Load a previous version of the design."""
```

#### List Versions
```python
async def list_versions(
    project_name: str,
    output_dir: str = "./designs"
) -> list[dict[str, Any]]:
    """List all versions of a project."""
```

### Automatic Snapshots

The system can capture automatic snapshots at key points:

1. **After wall creation** - `snapshot_walls_complete.png`
2. **After furniture placement** - `snapshot_furniture_placed.png`
3. **After material application** - `snapshot_materials_applied.png`
4. **Final delivery** - `snapshot_final_delivery.png`

### Design Export Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| SketchUp | `.skp` | Editing, further work |
| glTF | `.gltf` / `.glb` | Web, AR/VR |
| IFC | `.ifc` | BIM, architectural handover |
| PNG | `.png` | Presentation, client review |
| PDF | `.pdf` | Print, documentation |

### Capture Presets

```python
# Capture from preset views
capture_design(
    output_path="/designs/project/v1.0/snapshot_客厅.png",
    view_preset="living_room_birdseye",
    width=1920,
    height=1080
)

# Multi-angle capture for client presentation
for view in ["panoramic", "living_room_birdseye", "master_bedroom", "dining_area"]:
    capture_design(
        output_path=f"/designs/project/v1.0/snapshot_{view}.png",
        view_preset=view
    )
```

---

## Implementation Phases

### Phase 1: Foundation
- [x] Create `CLAUDE.md` at project root
- [x] Create `/specs/rpc_protocol.md` with full JSON-RPC 2.0 interface
- [x] Create `/specs/spatial_constraints.md` (mm/Z-up conventions)
- [x] Create `/specs/undo_semantics.md` (atomic rollback rules)
- [x] Initialize `/mcp_server/` with `pyproject.toml` and FastMCP skeleton
- [x] Initialize `/su_bridge/` with Ruby gem structure and basic listener

### Phase 2: Protocol Bridge
- [x] Implement Unix socket bridge between Python and Ruby
- [x] Implement non-blocking `UI.start_timer` listener in Ruby
- [x] Implement JSON-RPC serialization in Python
- [x] Implement `execute_operation` tool in Python with rollback support

### Phase 3: Core Tools
- [x] `create_face`, `create_box`, `create_group` tools
- [x] `query_entities`, `query_model_info` resources
- [x] `create_wall` tool with alignment support
- [x] Undo transaction wrapper in Ruby

### Phase 4: Skills
- [x] Designer workflow skills (wall placement, door/window insertion)
- [x] Common material and layer conventions
- [x] Spatial validation skill (collision detection)

### Phase 5: Visual & Export
- [x] Material system with Hex/RGB color support
- [x] Style presets (Japandi, Industrial, Scandinavian, etc.)
- [x] Lighting placement (spotlight, chandelier, floor_lamp)
- [x] Camera presets and capture/export tools
- [x] Design version control and snapshot system

### Phase 6: Plugin Marketplace
- [x] Create `.claude-plugin/marketplace.json` for `/plugin marketplace add` support
- [x] Create `.claude-plugin/plugin.json` with MCP server configuration
- [x] Update CLAUDE.md with marketplace distribution documentation
- [x] Add Sketchfab 3D model search tools
- [x] Add Sketchfab search skill

---

## Verification

1. **Python server starts**: `cd mcp_server && uv run python -m mcp_server.server` (should emit JSON-RPC initialize response on STDIO)
2. **Ruby plugin loads**: In SketchUp's Ruby console, `load 'su_bridge/su_bridge.rb'` should not error
3. **Protocol spec is valid**: The markdown in `/specs/rpc_protocol.md` should contain all required JSON-RPC fields
4. **Unit tests pass**: `cd mcp_server && uv run pytest` and `cd su_bridge && bundle exec rspec`
