# SketchUp Agent Harness

SketchUp Agent Harness is a natural-language control layer for SketchUp through
agent CLIs such as Claude Code and Codex CLI.

Claude and Codex are adapters. The shared core is the MCP server, the SketchUp
Ruby bridge, the design model schema, component metadata, runtime skills, and
protocol documentation.

Chinese documentation is available in [README.zh-CN.md](README.zh-CN.md).

## Product Boundary

Designers should not clone this repository for normal design work. The target
workflow is:

1. Install the harness plugin for the selected agent CLI.
2. Install or update the SketchUp Ruby bridge.
3. Create a clean design project directory.
4. Run Claude or Codex in that design project directory.
5. Describe the design in natural language.

Runtime skills are authored in `skills/`, but installation must expose them
through the supported Claude or Codex plugin/skill mechanism. The source tree is
not the designer's operating surface.

## Current Status

This project is in early development. The current priority is stabilizing the
baseline, then building the bathroom vertical slice:

> Create a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light,
> and clearance check.

## Repository Layout

```text
mcp_server/       Python MCP server and tools
su_bridge/        SketchUp Ruby bridge and socket server
skills/           Designer-facing runtime skills
specs/            Protocol and spatial behavior specifications
docs/             Architecture docs, ADRs, and localized docs
.claude-plugin/   Claude plugin adapter
.codex-plugin/    Codex plugin adapter
.agents/plugins/  Codex local plugin marketplace metadata
```

## Development Checks

Local product smoke without SketchUp:

```bash
cd mcp_server
uv run --extra dev sketchup-agent smoke /tmp/sah-smoke --force
```

Plugin startup smoke:

```bash
./mcp_server/start.sh --startup-check
```

Bridge install dry run:

```bash
cd mcp_server
uv run --extra dev sketchup-agent install-bridge --sketchup-version 2024 --dry-run
```

Doctor check:

```bash
cd mcp_server
uv run --extra dev sketchup-agent doctor /tmp/sah-smoke --sketchup-version 2024
```

Package wheel smoke:

```bash
cd mcp_server
uv build --wheel --out-dir /tmp/sah-dist --clear
```

Python baseline tests, excluding live SketchUp integration tests:

```bash
cd mcp_server
uv run --extra dev pytest tests/ -m "not integration" -v --tb=short
```

Ruby bridge specs:

```bash
cd su_bridge
bundle install --path vendor/bundle
bundle exec rspec spec/ --format progress
```

Live SketchUp integration tests require SketchUp to be open with `SuBridge`
running and `/tmp/su_bridge.sock` available.

## Documentation

- [Installation](INSTALLATION.md)
- [Quickstart](QUICKSTART.md)
- [Designer Guide](DESIGNER_GUIDE.md)
- [Development](DEVELOPMENT.md)
- [Roadmap](docs/roadmap.md)
- [Runtime vs Development Skills](docs/architecture/runtime-vs-dev-skills.md)
