# ADR 0001: Agent Harness Boundary

Status: accepted
Date: 2026-04-28

## Context

The project started as SketchUp-Claude-Code: a Claude Code plugin that lets an
interior designer control SketchUp with natural language. The long-term product
goal is broader: support both Claude CLI and Codex CLI while keeping the user
experience conversational and designer-facing.

The current repository already contains the reusable core:

- Python MCP server in `mcp_server/`
- SketchUp Ruby bridge in `su_bridge/`
- shared runtime skills in `skills/`
- protocol and spatial rules in `specs/`
- JSON design model schema in `mcp_server/mcp_server/resources/`

## Decision

Treat Claude and Codex as adapters around one shared SketchUp agent harness.

The reusable product core is:

- the design model and component schemas
- the MCP tools and resources
- the SketchUp bridge
- the runtime skills that guide design interactions
- the project workspace conventions

The CLI-specific surfaces are thin wrappers:

- `.claude-plugin/` for Claude plugin distribution
- `.codex-plugin/`, `.mcp.json`, and `.agents/plugins/` for Codex plugin distribution
- `AGENTS.md` and `CLAUDE.md` for development-time agent orientation

## Consequences

- Core code must not import or assume Claude-specific paths.
- Runtime skills should avoid Claude-only wording unless the behavior is truly
  Claude-specific.
- Future setup commands should configure both Claude and Codex from the same
  source of truth.
- The plugin manifests may differ, but they must point at the same MCP server
  and runtime skills.

## Non-goals

- Do not build a web component registry yet.
- Do not split the component registry into a second repository until real assets
  and licensing workflows exist.
- Do not require designers to use VS Code or edit code files directly.
