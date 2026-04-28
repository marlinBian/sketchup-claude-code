# SketchUp Agent Harness

This repository is becoming SketchUp Agent Harness: a natural-language harness
for controlling SketchUp through agent CLIs. Claude and Codex are adapters; the
shared core is the MCP server, SketchUp Ruby bridge, design model schema,
runtime skills, and protocol docs.

## Current Boundaries

- `mcp_server/`: Python MCP server and tools.
- `su_bridge/`: Ruby SketchUp plugin and socket bridge.
- `skills/`: runtime skills authored for designers and shipped through Claude,
  Codex, or future agent CLI plugin/install flows.
- `specs/`: protocol and spatial behavior specs.
- `docs/adr/`: architecture decisions.
- `.claude-plugin/`: Claude plugin adapter.
- `.codex-plugin/`, `.mcp.json`, `.agents/plugins/`: Codex plugin adapter.

Maintainer-only Codex skills for developing this repository are intentionally
kept outside the product repository, under the local `ai4design` workspace.

## Development Rules

- Keep Claude-specific and Codex-specific logic out of the core MCP server.
- Keep designer project files separate from this source repository.
- Treat `skills/` as the runtime skill authoring source. Installers and plugin
  manifests must expose those skills in each AI tool's supported runtime
  location; designers should not need to copy files from the source tree.
- Use millimeters and Z-up coordinates across protocol boundaries.
- Add or update tests when changing schemas, MCP tool contracts, or placement behavior.
- Do not put maintainer workflow skills under `skills/` or ship them in plugin
  manifests.

## Verification

Run focused checks after changes:

```bash
cd mcp_server && uv run pytest tests/ -v --tb=short
cd su_bridge && bundle exec rspec spec/ --format progress
```

Ruby specs may require SketchUp-specific context for full coverage. At minimum,
run syntax checks before publishing bridge changes.
