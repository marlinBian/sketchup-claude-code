# SCC (SketchUp-Claude-Code)

SCC enables bidirectional communication between Claude Code and SketchUp, allowing interior designers to create 3D models using natural language commands.

## Features

- **Natural Language Interface**: Control SketchUp using natural language (e.g., "add a 2m x 3m window on the south wall")
- **Foundation Modeling**: Create basic geometric elements (faces, walls, boxes, doors, windows, stairs)
- **Component Library**: Search and place furniture from built-in or custom component libraries
- **Semantic Positioning**: Position objects relative to each other (e.g., "lamp above dining table")
- **Style Presets**: Apply design styles (Scandinavian, Modern Industrial, Japandi, etc.)
- **Design Export**: Export to glTF and IFC formats

## Requirements

- **SketchUp** (2021 or later)
- **Python** 3.11+
- **Ruby** 3.2+

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/avenir/sketchup-claude-code.git
cd sketchup-claude-code

# 2. Install Python dependencies
cd mcp_server && pip install uv && uv sync && cd ..

# 3. Copy su_bridge to SketchUp plugins folder
# macOS: ~/Library/Application Support/SketchUp/SketchUp 2024/SketchUp/Plugins/
# Windows: C:\Users\<You>\AppData\Roaming\SketchUp\SketchUp 2024\SketchUp\Plugins\

# 4. Start MCP server
cd mcp_server && uv run python -m mcp_server.server

# 5. In SketchUp Ruby Console:
load 'su_bridge/lib/su_bridge.rb'
SuBridge.start
```

## Usage Example

```
You: Create a 4m x 5m living room with 2.4m ceiling height
You: Add a three-seater sofa against the north wall
You: Place a coffee table 600mm in front of the sofa
You: Apply the Scandinavian style
```

## MCP Tools

### Foundation Modeling
- `create_face`, `create_box`, `create_wall`, `create_group`
- `create_door`, `create_window`, `create_stairs`
- `move_entity`, `rotate_entity`, `scale_entity`, `copy_entity`
- `apply_material`, `apply_style`

### Component Search
- `search_local_library`, `search_sketchfab_models`, `place_component`

### Export
- `export_gltf`, `export_ifc`

## Project Structure

```
sketchup-claude-code/
├── CLAUDE.md              # Project constitution
├── LICENSE                # MIT License
├── README.md              # This file
├── mcp_server/            # Python MCP server
│   ├── mcp_server/
│   │   ├── server.py      # FastMCP entry point
│   │   ├── tools/         # MCP tools
│   │   └── resources/     # Design model resources
│   └── tests/             # Python tests
├── su_bridge/             # Ruby SketchUp plugin
│   ├── lib/su_bridge/     # Main bridge code
│   └── spec/              # Ruby tests
├── skills/                # LLM instruction sets
└── specs/                 # Protocol definitions
```

## Testing

```bash
# Python tests
cd mcp_server && uv run pytest tests/ -v

# Ruby tests
cd su_bridge && bundle exec rspec spec/

# Syntax check
ruby -c su_bridge/lib/su_bridge.rb
python3 -m py_compile mcp_server/mcp_server/server.py
```

## License

MIT License - see [LICENSE](LICENSE)
