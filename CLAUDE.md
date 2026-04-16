# SCC (SketchUp-Claude-Code) Project Constitution

---

## ⚠️ CRITICAL: Two Independent Perspectives

This project serves TWO completely different use cases. You MUST understand both:

### 👤 Designer Perspective (End User)

**Designer NEVER clones this repository!**

Designers install via Claude Code plugin marketplace:
```bash
# 1. Install plugin via Claude Code
/plugin marketplace add https://github.com/marlinBian/sketchup-claude-code
/plugin install sketchup-claude-code

# 2. Create a clean project directory
mkdir ~/Design/my-room && cd ~/Design/my-room
claude

# 3. Start designing - that's it!
# "Create a 4m x 5m living room with Scandinavian style"
```

Designer's working directory contains ONLY:
```
~/Design/my-room/
├── design_model.json   ← AI reads/writes this
└── model.skp          ← SketchUp file
```

Designers NEVER see: `skills/`, `rules/`, `mcp_server/`, `su_bridge/`, `specs/`

### 👨‍💻 Developer Perspective (You)

You work in the **repository directory**:
```
~/Code/sketchup-claude-code/   ← Full source code
├── skills/                   ← Modify to improve designer experience
├── rules/                   ← Modify to add constraints
├── mcp_server/              ← Modify MCP tools
├── su_bridge/               ← Modify Ruby SketchUp plugin
├── specs/                   ← Protocol documentation
└── .claude-plugin/          ← Plugin configuration
```

When developing:
- Modify skills/rules to improve AI behavior
- Test changes locally
- Push to GitHub when ready
- Designers get updates via marketplace

---

## Overview

**SCC** enables bidirectional communication between an LLM (Claude Code) and SketchUp for interior design automation. Designers issue natural language commands like "add a 2m x 3m window on the south wall" and receive confirmation with spatial feedback.

**Target Users**: Professional interior designers who want to create 3D models using natural language, not programmers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code (LLM)                       │
│         设计师自然语言: "在餐桌上方1.2米挂餐桌灯"            │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 SCC Plugin Layer (ECC)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Skills    │  │   Rules     │  │       Hooks        │ │
│  │ - designer  │  │ - spatial   │  │ - on_scene_change │ │
│  │ - geometry  │  │ - naming    │  │ - on_entity_add   │ │
│  │ - workflow  │  │ - units      │  │ - on_save        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Design Model (抽象状态层)                        │
│  - design_model.json (LLM 可读写)                            │
│  - 组件清单、空间布局、材质定义                              │
│  - 语义位置 (餐桌上方、主卧床头)                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   MCP Server Layer                           │
│  - model_tools (create_*, apply_*)                          │
│  - query_tools (get_scene_info)                             │
│  - component_tools (place_component, search)                │
│  - export_tools (gltf, ifc)                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   Ruby Bridge Layer                          │
│  - Socket bridge                                            │
│  - UndoManager                                              │
│  - Entity builders (Face, Wall, Door, Window, Stairs)       │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    SketchUp                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Three-Layer Capability Architecture

SCC uses a **three-layer approach** to cover all design scenarios:

### Layer 1: Foundation Modeling (Core)

Basic geometric elements that form the foundation of all 3D modeling:

| Tool | Description | Use Case |
|------|-------------|----------|
| `create_face` | Create face from vertices | Any polygon surface |
| `create_wall` | Create wall with alignment | Interior/exterior walls |
| `create_box` | Create 3D box | Simple furniture, volumes |
| `create_group` | Group entities | Combine related geometry |
| `create_door` | Door with frame and swing | Interior door openings |
| `create_window` | Window with frame and glass | Window openings in walls |
| `create_stairs` | Staircase between levels | Multi-story access |
| `move_entity` | Translate entities | Reposition objects |
| `rotate_entity` | Rotate around axis | Orient objects |
| `scale_entity` | Scale uniformly/non-uniformly | Resize objects |
| `copy_entity` | Duplicate entities | Clone for repetition |
| `apply_material` | Apply color/texture | Surface appearance |
| `apply_style` | Apply style preset | Whole-model theming |

**Principle**: These are building blocks. LLM combines them to create any object.

### Layer 2: Component Search (Discovery)

Search external 3D model libraries for ready-made components:

| Source | Tool | Description |
|--------|------|-------------|
| SketchUp 3D Warehouse | `search_warehouse` | Official SketchUp models |
| Sketchfab | `search_sketchfab_models` | Creative Commons 3D models |
| Local Library | `place_component` | User's custom .skp files |

**Workflow**: Search → Download/Place → Position → Adjust

### Layer 3: AI-Generated Geometry (Creation)

When Layer 1 and Layer 2 can't meet the need, use foundation elements to compose any geometry:

```
User: "Create an L-shaped sofa"
LLM Decision:
1. Check local library → No L-shaped sofa
2. Check Sketchfab → May not have exact match
3. Compose using foundation elements:
   - create_group() to create sofa group
   - create_face() for seat cushions
   - create_box() for armrests and back
```

**Key Insight**: Don't enumerate all possible objects. Give LLM foundation tools + context, let it compose.

---

## Design Model (Abstract State Layer)

Design Model is the **shared abstract layer** between LLM and SketchUp. It provides a JSON-based representation that enables high-level semantic operations.

### File Location

```
designs/{project_name}/
├── design_model.json      # Main design state (LLM reads/writes)
├── model.skp              # SketchUp file
└── snapshots/             # Visual snapshots
```

### Semantic Positioning

Enables commands like "lamp above dining table":

```json
{
  "components": {
    "dining_table_001": {
      "semantic_anchor": "dining_table_center",
      "position": [3000, 2000, 0],
      "above_position": {
        "height_offset": 1200,
        "used_for": ["dining_light_001"]
      }
    }
  }
}
```

See `skills/semantic_positioning/SKILL.md` for full documentation.

---

## ECC Plugin Structure

### Skills

Skills are **instruction sets** that guide LLM behavior for specific domains.

| Skill | File | Purpose |
|-------|------|---------|
| `geometry_composition` | `skills/geometry_composition/SKILL.md` | Compose furniture from primitives |
| `designer_workflow` | `skills/designer_workflow/SKILL.md` | Standard design workflow |
| `semantic_positioning` | `skills/semantic_positioning/SKILL.md` | Relative positioning |
| `common_operations` | `skills/common_operations/SKILL.md` | Frequent design operations |

### Rules

Rules are **constraints** that guide LLM behavior:

| Rule | File | Purpose |
|------|------|---------|
| `spatial_constraints` | `specs/spatial_constraints.md` | Collision, minimum clearances |
| `naming_convention` | `specs/naming_convention.rules` | Entity naming standards |
| `unit_conversion` | `specs/unit_conversion.rules` | mm/m/ft conversion |

### Hooks

Hooks are **automation triggers** on events:

| Hook | Trigger | Action |
|------|---------|--------|
| `on_entity_add` | Entity created | Update design_model.json |
| `on_entity_delete` | Entity deleted | Update design_model.json |
| `on_transform` | Entity moved/rotated/scaled | Update semantic positions |
| `on_save` | Model saved | Sync design_model.json |

---

## Plugin Marketplace Distribution

SCC is distributed as a Claude Code plugin marketplace. **Designers do NOT clone the repository!**

### For Designers: Installation

```bash
# 1. Install SCC plugin via Claude Code
/plugin marketplace add https://github.com/marlinBian/sketchup-claude-code
/plugin install sketchup-claude-code

# 2. Copy SketchUp plugin (one-time)
/plugin install sketchup-claude-code@sketchup-claude-code --setup

# 3. In SketchUp Ruby Console, run once:
load '~/Library/Application Support/SketchUp/SketchUp 2024/SketchUp/Plugins/su_bridge/lib/su_bridge.rb'
SuBridge.start

# 4. Create your design project
mkdir ~/Design/my-room && cd ~/Design/my-room
claude

# 5. Start designing!
```

### For Developers: Local Testing

```bash
# Clone to local plugin directory for testing
git clone https://github.com/marlinBian/sketchup-claude-code ~/.claude/plugins/sketchup-claude-code

# Copy su_bridge to SketchUp plugins folder
cp -r ~/.claude/plugins/sketchup-claude-code/su_bridge ~/Library/Application\ Support/SketchUp/SketchUp\ 2024/SketchUp/Plugins/

# Run setup
cd ~/.claude/plugins/sketchup-claude-code && ./setup.sh

# Test in a clean project directory
mkdir ~/Design/test && cd ~/Design/test
claude
```

---

## Directory Structure

```
sketchup-claude-code/
├── CLAUDE.md                          # Project constitution (this file)
├── setup.sh                           # First-time setup script
├── designs/                           # Design projects
│   └── {project_name}/
│       ├── design_model.json           # Design state (LLM readable)
│       └── model.skp                  # SketchUp file
├── .claude-plugin/                    # Claude Code plugin marketplace
│   ├── marketplace.json
│   └── plugin.json
├── mcp_server/                        # Python MCP server
│   ├── pyproject.toml
│   ├── mcp_server/
│   │   ├── server.py                  # FastMCP entry point
│   │   ├── tools/                     # MCP tools
│   │   │   ├── model_tools.py
│   │   │   ├── query_tools.py
│   │   │   ├── component_tools.py
│   │   │   └── export_tools.py
│   │   ├── resources/
│   │   │   └── design_model_resource.py
│   │   ├── protocol/
│   │   └── bridge/
│   └── tests/
├── su_bridge/                         # Ruby SketchUp plugin
│   ├── su_bridge.rb                  # Main entry point
│   ├── lib/su_bridge/
│   │   ├── server_listener.rb         # Non-blocking socket server
│   │   ├── command_dispatcher.rb     # Routes JSON-RPC to Ruby API
│   │   ├── undo_manager.rb            # Undo transaction wrapper
│   │   ├── entities/
│   │   │   ├── face_builder.rb
│   │   │   ├── wall_builder.rb
│   │   │   ├── door_builder.rb
│   │   │   ├── window_builder.rb
│   │   │   ├── stairs_builder.rb
│   │   │   └── material_applier.rb
│   │   └── protocol/
│   └── spec/
├── specs/                             # Protocol definitions
│   ├── rpc_protocol.md
│   ├── spatial_constraints.md
│   ├── naming_convention.rules
│   └── undo_semantics.md
├── skills/                            # LLM instruction sets
│   ├── SKILL.md
│   ├── geometry_composition/
│   │   └── SKILL.md
│   ├── designer_workflow/
│   │   └── SKILL.md
│   ├── semantic_positioning/
│   │   └── SKILL.md
│   └── common_operations/
│       └── SKILL.md
├── scripts/                           # Utility scripts
│   ├── reload_su_bridge.rb
│   └── cleanup_su_bridge.rb
└── .gitignore
```

---

## Core Principles

### Principle 1: Bidirectional Communication

All modeling commands MUST return state feedback. No fire-and-forget operations.

### Principle 2: Undo Transaction Wrapper

Every mutating operation wrapped in SketchUp Undo transaction. On exception, rollback.

### Principle 3: mm / Z-Up Coordinate System

All coordinates in **millimeters** with Z-axis pointing up.

### Principle 4: Atomic Operations with Rollback

Each operation is atomic. On failure, rollback and return structured error.

### Principle 5: Non-Blocking SketchUp Interaction

All Ruby operations use `UI.start_timer` for deferred execution.

### Principle 6: Design Model Synchronization

Design Model (design_model.json) MUST be synchronized with SketchUp state.

### Principle 7: Semantic Positioning

LLM positions objects using semantic relationships, not raw coordinates.

---

## MCP Tools Reference

### Foundation Modeling

```python
create_face(vertices: list[list[float]], layer: str = None)
create_box(corner_x: float, corner_y: float, corner_z: float, width: float, depth: float, height: float)
create_wall(start_x: float, start_y: float, start_z: float, end_x: float, end_y: float, end_z: float, height: float, thickness: float, alignment: str = "center")
create_group(entity_ids: list[str], name: str = None)
create_door(wall_id: str, position_x: float, position_y: float, width: float = 900, height: float = 2100, swing_direction: str = "left")
create_window(wall_id: str, position_x: float, position_y: float, width: float = 1200, height: float = 1000, sill_height: float = 900)
create_stairs(start_x: float, start_y: float, start_z: float, end_x: float, end_y: float, end_z: float, width: float = 1000, num_steps: int = 12)
```

### Entity Operations

```python
move_entity(entity_ids: list[str], delta_x: float, delta_y: float, delta_z: float)
rotate_entity(entity_ids: list[str], center_x: float, center_y: float, center_z: float, axis: str, angle: float)
scale_entity(entity_ids: list[str], center_x: float, center_y: float, center_z: float, scale: float)
copy_entity(entity_ids: list[str], delta_x: float, delta_y: float, delta_z: float)
delete_entity(entity_ids: list[str])
```

### Material & Style

```python
apply_material(entity_ids: list[str], color: str = None, material_id: str = None, texture_scale_x: int = None, texture_scale_y: int = None)
apply_style(style_name: str, entity_ids: list[str] = None)
# Style options: "japandi_cream", "modern_industrial", "scandinavian", "mediterranean", "bohemian", "contemporary_minimalist"
```

### Query

```python
get_scene_info() -> dict  # Returns bounding_box, entity_counts, layers
query_entities(entity_type: str = None, layer: str = None, limit: int = 100)
```

### Component & Lighting

```python
place_component(component_name: str, position_x: float = 0, position_y: float = 0, position_z: float = 0, rotation: float = 0, scale: float = 1)
place_lighting(lighting_type: str, position_x: float, position_y: float, position_z: float = 0, ceiling_height: float = 2400, mount_height: float = 2000, rotation: float = 0)
# lighting_type: "spotlight", "chandelier", "floor_lamp"
```

### Camera & Capture

```python
set_camera_view(view_preset: str = None, eye_x: float = None, eye_y: float = None, eye_z: float = None, target_x: float = None, target_y: float = None, target_z: float = None)
capture_design(output_path: str, view_preset: str = None, width: int = 1920, height: int = 1080, return_base64: bool = False)
```

### Component Search

```python
search_sketchfab_models(query: str, count: int = 10, sort: str = "relevance")
download_sketchfab_model(model_uid: str, format_hint: str = "obj", output_dir: str = None)
search_and_download_sketchfab(query: str, format_hint: str = "obj")
```

### Export

```python
export_gltf(output_path: str, include_textures: bool = True)
export_ifc(output_path: str)
```

---

## Implementation Phases

### Phase 1: Foundation ✅
- [x] Create `CLAUDE.md` at project root
- [x] Create `/specs/rpc_protocol.md`
- [x] Initialize `/mcp_server/` with FastMCP skeleton
- [x] Initialize `/su_bridge/` with Ruby plugin

### Phase 2: Protocol Bridge ✅
- [x] Implement Unix socket bridge
- [x] Implement non-blocking `UI.start_timer` listener
- [x] Implement `execute_operation` tool

### Phase 3: Core Tools ✅
- [x] `create_face`, `create_box`, `create_wall`, `create_group`
- [x] `query_entities`, `get_scene_info`
- [x] `move_entity`, `rotate_entity`, `scale_entity`, `copy_entity`
- [x] `create_door`, `create_window`, `create_stairs`
- [x] Undo transaction wrapper

### Phase 4: Skills (ECC) ✅
- [x] `geometry_composition/SKILL.md` - Furniture composition patterns
- [x] `designer_workflow/SKILL.md` - Standard design workflow
- [x] `semantic_positioning/SKILL.md` - Relative positioning
- [x] `common_operations/SKILL.md` - Frequent operations
- [x] `component_search/SKILL.md` - Library search workflow

### Phase 5: Rules ✅
- [x] `rules/spatial_validator.rb` - Spatial constraint validation
- [x] `specs/naming_convention.rules` - Entity naming standards
- [x] `specs/unit_conversion.rules` - Unit conversion rules
- [x] `specs/layer_convention.rules` - Layer usage guidelines

### Phase 6: Design Model ✅
- [x] `design_model_schema.py` - JSON Schema and validation
- [x] `design_model_resource.py` - MCP resources for reading
- [x] `design_model_sync.rb` - SketchUp to JSON sync

### Phase 7: Hooks ✅
- [x] `Hooks::EntityObserver` - Basic SketchUp observer
- [x] `on_save` - Sync on model save
- [x] `on_entity_add` - Auto-add to design model (debounced)
- [x] `on_entity_delete` - Auto-remove from design model (debounced)
- [x] `on_transform` - Update semantic positions
- [x] `Hooks.configure()` - Configurable debounce and sync options

### Phase 8: Component Search MCP ✅
- [x] `search_local_library` - Fuzzy search local .skp files
- [x] `list_local_library_categories` - List available categories
- [x] `search_warehouse` - 3D Warehouse URL generator
- [x] `download_from_warehouse` - Download guidance

### Phase 9: Visual & Export ✅
- [x] Material system with Hex/RGB color
- [x] All 6 style presets
- [x] Lighting placement
- [x] Camera presets and capture
- [x] Design version control
- [x] `export_gltf`, `export_ifc`

### Phase 10: Plugin Marketplace ✅
- [x] `.claude-plugin/marketplace.json`
- [x] `.claude-plugin/plugin.json`
- [x] Sketchfab 3D model search

### Phase 11: GitHub Preparation ✅
- [x] GitHub Actions CI/CD workflow
- [x] LICENSE file (MIT)
- [x] README.md user documentation
- [x] .gitignore
- [x] CONTRIBUTING.md
- [x] Issue templates

---

## Verification

### Quick Verification

```bash
# 1. Verify Ruby syntax
cd su_bridge && for f in lib/su_bridge/**/*.rb spec/*.rb; do ruby -c "$f"; done

# 2. Verify Python syntax
cd mcp_server && uv run python -m py_compile mcp_server/server.py

# 3. Run Python tests
cd mcp_server && uv run pytest tests/ -v

# 4. Run integration tests (requires SketchUp running)
cd mcp_server && uv run pytest tests/test_integration.py -v
```

### Manual Test Sequence

1. Open SketchUp, run `SuBridge.start`
2. Test: `get_scene_info` - should return scene info
3. Test: `create_wall` - should create wall
4. Test: `apply_style` - should apply Scandinavian style
5. Test: `move_entity` - should move created wall

### Plugin Reinstall Flow

```bash
/plugin marketplace remove sketchup-claude-code
rm -rf ~/.claude-doubao/plugins/cache/sketchup-claude-code
/plugin marketplace add /Users/avenir/Code/personal/sketchup-claude-code
```

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| TextContent validation error | Return type mismatch | Use `TextContent(type="text", text=...)` |
| Socket connection refused | Ruby bridge not started | Run `SuBridge.start` in SketchUp |
| Tools listed but call fails | Cache has old code | Reinstall plugin |
| Ruby reload issues | UI.start_timer persistence | Restart SketchUp |

---

## Marketplace Debugging Guide

### ⚠️ CRITICAL: GitHub Default Branch Matters

The Claude Code marketplace uses GitHub's **default branch** (HEAD), NOT the `main` branch.

**Check default branch:**
```bash
git ls-remote https://github.com/marlinBian/sketchup-claude-code.git HEAD
```

**If HEAD points to old commit:**
- The marketplace will serve outdated code
- Debug: Check `~/.claude-model/.claude-doubao/plugins/marketplaces/sketchup-claude-code/mcp_server/start.sh`
- If it shows `uv run python` instead of `python3`, the cached code is stale

**Fix: Ensure fixes are in the default branch (master on this repo):**
```bash
# Merge fixes to master branch
git checkout master
git merge main
git push origin master
```

### Marketplace Cache Location

Claude Code stores marketplace plugins at:
```
~/.claude-model/.claude-doubao/plugins/
├── marketplaces/sketchup-claude-code/  ← Git clone of repo
└── cache/sketchup-claude-code/         ← Package cache
```

### Debugging Steps for Plugin Installation Issues

1. **Remove marketplace and clear cache:**
   ```bash
   /plugin marketplace remove sketchup-claude-code
   rm -rf ~/.claude-model/.claude-doubao/plugins/marketplaces/sketchup-claude-code
   rm -rf ~/.claude-model/.claude-doubao/plugins/cache/sketchup-claude-code
   ```

2. **Re-add marketplace:**
   ```bash
   /plugin marketplace add https://github.com/marlinBian/sketchup-claude-code
   ```

3. **Install plugin:**
   ```bash
   /plugin install sketchup-claude-code
   ```

4. **Verify installation:**
   ```bash
   cat ~/.claude-model/.claude-doubao/plugins/marketplaces/sketchup-claude-code/mcp_server/start.sh
   ```
   Should show `python3 -m mcp_server.server`, NOT `uv run python`

5. **Check MCP status:**
   ```
   /mcp
   ```
   Look for `sketchup-claude-code:sketchup-mcp · ✔ connected`

### Why `uv run python` Might Appear

- The `start.sh` file was changed from `uv run python` to `python3`
- But marketplace cached the old version because:
  1. GitHub default branch pointed to old commit
  2. OR marketplace cache wasn't cleared

### Prevention

**Before pushing fixes:**
1. Verify the fix commit is on the default branch (master)
2. Check: `git ls-remote https://github.com/marlinBian/sketchup-claude-code.git HEAD`
3. Confirm the commit hash matches your fix

---

## Contributing

When adding new features:

1. Add MCP tool to `server.py`
2. Add Ruby handler to `command_dispatcher.rb`
3. Add entity builder if needed
4. Add skill documentation if new workflow
5. Add tests (unit + integration)
6. Update this CLAUDE.md

---

## License

MIT
