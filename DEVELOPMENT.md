# Development

This repository is the product source for SketchUp Agent Harness. Maintainer
workflow skills live outside the product repository in the local AI4Design
workspace.

## Architecture

```text
Agent CLI
  -> runtime skills
  -> MCP server
  -> SketchUp Ruby bridge
  -> SketchUp model
```

Core boundaries:

- Claude and Codex are adapters.
- MCP tools expose shared behavior.
- The Ruby bridge executes SketchUp operations.
- Runtime skills guide the designer-facing natural-language workflow.
- `design_model.json` is the intended spatial source of truth.

## Development Skills

Do not put maintainer workflow skills in product `skills/`. Product `skills/`
are designer-facing runtime skills.

Local maintainer skills live at:

```text
~/Code/ai4design/.agents/skills/
```

## Baseline Checks

Python:

```bash
cd mcp_server
uv run --extra dev pytest tests/ -m "not integration" -v --tb=short
```

Ruby:

```bash
cd su_bridge
bundle install --path vendor/bundle
bundle exec rspec spec/ --format progress
```

Ruby syntax fallback:

```bash
find su_bridge/lib su_bridge/spec -name '*.rb' -print0 | xargs -0 -n1 ruby -c
```

Project initialization smoke:

```bash
cd mcp_server
uv run --extra dev sketchup-agent init /tmp/sah-bathroom --template bathroom --force
```

Bridge install dry run:

```bash
cd mcp_server
uv run --extra dev sketchup-agent install-bridge --sketchup-version 2024 --dry-run
```

Doctor check:

```bash
cd mcp_server
uv run --extra dev sketchup-agent doctor /tmp/sah-bathroom --sketchup-version 2024
```

Wheel packaging check:

```bash
cd mcp_server
uv build --wheel --out-dir /tmp/sah-dist --clear
```

## Integration Tests

Live integration tests require SketchUp with the installed bridge loader running
and `/tmp/su_bridge.sock` available:

```bash
cd mcp_server
uv run --extra dev pytest tests/test_integration.py -m integration -v --tb=short
```

## Current Development Order

1. Stabilize baseline checks and English-first docs.
2. Lock schema and manifest contracts for the bathroom slice.
3. Build a headless bathroom vertical slice.
4. Execute the slice through the SketchUp Ruby bridge.
5. Automate installation and project initialization.
6. Expand the component registry.
7. Add visual feedback loops while keeping structured state canonical.
