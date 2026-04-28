# Installation

This page describes the intended installation model. The project is still in
early development, so some steps are currently manual.

## Designer Installation Model

Designers should install the harness through Claude or Codex plugin mechanisms,
then work in their own design project directories. They should not edit this
source repository during normal use.

The target setup has three parts:

1. Agent CLI plugin: exposes runtime skills and MCP configuration.
2. MCP server: runs the Python tool layer.
3. SketchUp Ruby bridge: runs inside SketchUp and listens on a local socket.

## Project Initialization

After the MCP package is installed in the active Python environment, create a
designer project directory with:

```bash
sketchup-agent init ~/Design/my-bathroom --template bathroom
```

For a blank project:

```bash
sketchup-agent init ~/Design/my-room --template empty
```

This creates:

- `design_model.json`
- `design_rules.json`
- `assets.lock.json`
- `.mcp.json`
- `snapshots/`

The generated `.mcp.json` starts the MCP server with:

```bash
python3 -m mcp_server.server
```

## Claude CLI

Target plugin flow:

```text
/plugin marketplace add https://github.com/marlinBian/sketchup-agent-harness
/plugin install sketchup-agent-harness
```

The plugin should expose:

- runtime skills from `skills/`
- MCP server startup from `mcp_server/start.sh`
- install guidance for the SketchUp Ruby bridge

## Codex CLI

Target plugin flow:

```bash
codex plugin marketplace add marlinBian/sketchup-agent-harness
```

The Codex adapter should expose runtime skills from `skills/` and MCP startup
through `.codex-plugin/plugin.json` and `.mcp.json`.

## SketchUp Ruby Bridge

Until the installer is automated, install the bridge manually.

macOS example:

```bash
mkdir -p ~/Library/Application\ Support/SketchUp/SketchUp\ 2024/SketchUp/Plugins/
cp -R su_bridge ~/Library/Application\ Support/SketchUp/SketchUp\ 2024/SketchUp/Plugins/
```

In the SketchUp Ruby Console:

```ruby
load '~/Library/Application Support/SketchUp/SketchUp 2024/SketchUp/Plugins/su_bridge/lib/su_bridge.rb'
SuBridge.start
```

The bridge should create `/tmp/su_bridge.sock`.

## Maintainer Setup

Maintainers working from the source repository can install local dependencies:

```bash
./setup.sh
```

Run the initializer from the source checkout:

```bash
cd mcp_server
uv run --extra dev sketchup-agent init /tmp/sah-bathroom --template bathroom --force
```

Python tests:

```bash
cd mcp_server
uv run --extra dev pytest tests/ -m "not integration" -v --tb=short
```

Ruby tests:

```bash
cd su_bridge
bundle install --path vendor/bundle
bundle exec rspec spec/ --format progress
```

## Cleanup

Remove the SketchUp bridge by deleting the copied `su_bridge` folder from the
SketchUp Plugins directory and restarting SketchUp.
