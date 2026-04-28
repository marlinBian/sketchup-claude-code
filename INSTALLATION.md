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
- `assets/components/`
- `.mcp.json`
- `AGENTS.md`
- `CLAUDE.md`
- `snapshots/`
- `snapshots/manifest.json`

New design projects use the installed MCP console script:

```bash
sketchup-agent-mcp
```

The source plugin `.mcp.json` starts the same MCP server through:

```bash
./mcp_server/start.sh
```

The startup script prefers `uv run` when `uv` is available so plugin startup can
use the package dependencies declared by `mcp_server/pyproject.toml`.

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

Quit SketchUp first, then install or update the bridge from the installed
package:

```bash
sketchup-agent install-bridge --sketchup-version 2024 --force
```

To inspect the target path first:

```bash
sketchup-agent install-bridge --sketchup-version 2024 --dry-run
```

The installer copies the `su_bridge/` runtime folder and writes a
`su_bridge.rb` loader into the SketchUp Plugins directory. SketchUp loads that
file on startup, so opening SketchUp should start the bridge automatically. On
macOS, the installer also enables `su_bridge.rb` in SketchUp's private extension
preferences when that preferences file already exists.

The installed Python package includes the Ruby bridge runtime, so designers do
not need a source checkout for this command. Maintainers running from the source
tree can use the same command through `uv run --extra dev sketchup-agent ...`.

When `--force` replaces an existing install, the previous `su_bridge/` folder
and `su_bridge.rb` loader are moved to timestamped `*.backup-*` paths in the
same Plugins folder.

Manual macOS fallback:

```bash
mkdir -p ~/Library/Application\ Support/SketchUp\ 2024/SketchUp/Plugins/
cp -R su_bridge ~/Library/Application\ Support/SketchUp\ 2024/SketchUp/Plugins/
plugins_dir=~/Library/Application\ Support/SketchUp\ 2024/SketchUp/Plugins
cat > "$plugins_dir/su_bridge.rb" <<'RUBY'
# frozen_string_literal: true

bridge_path = File.expand_path("su_bridge/lib/su_bridge.rb", __dir__)
require bridge_path
SuBridge.start if defined?(SuBridge)
RUBY
```

Open SketchUp after installing. The bridge is ready when
`/tmp/su_bridge.sock` exists.

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

Validate a project workspace:

```bash
cd mcp_server
uv run --extra dev sketchup-agent validate /tmp/sah-bathroom
```

Check the installed commands, project files, SketchUp bridge install, and live
socket:

```bash
cd mcp_server
uv run --extra dev sketchup-agent doctor /tmp/sah-bathroom --sketchup-version 2024
```

Run the local smoke check without SketchUp:

```bash
cd mcp_server
uv run --extra dev sketchup-agent smoke /tmp/sah-smoke --force
```

Check the plugin startup path:

```bash
./mcp_server/start.sh --startup-check
```

Run the smoke check against a live SketchUp bridge:

```bash
cd mcp_server
uv run --extra dev sketchup-agent smoke /tmp/sah-smoke --force --with-bridge
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

Remove the SketchUp bridge by deleting the copied `su_bridge` folder and
`su_bridge.rb` loader from the SketchUp Plugins directory, then restart
SketchUp.
