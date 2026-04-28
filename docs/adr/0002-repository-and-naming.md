# ADR 0002: Repository and Naming

Status: accepted
Date: 2026-04-28

## Decision

Use `sketchup-agent-harness` as the next repository name and technical package
identity.

Use `SketchUp Agent Harness` as the developer-facing product name.

Use `SketchUp Design Agent` as the designer-facing product phrase when a less
technical label is needed.

## Rationale

`sketchup-agent-harness` keeps the strongest search term, SketchUp, while
removing the Claude-only boundary. It is more concrete than `spatial-harness`,
which should be reserved for a future protocol-only extraction if the project
eventually supports additional modeling tools.

## Migration Plan

1. Keep the current repository working while adding Codex plugin support.
2. Rename the GitHub repository from `sketchup-claude-code` to
   `sketchup-agent-harness`. Completed on 2026-04-28.
3. Keep old plugin and package names as compatibility aliases only where needed.
4. Update user-facing docs after the plugin manifests and install flow are
   validated locally.

## Repository Split Policy

Keep everything in one repository for now:

- core harness
- Claude adapter
- Codex adapter
- seed component manifests
- schema and validation tests

Create `sketchup-agent-components` later only when the project has enough real
assets to justify separate versioning, storage, licensing, and review workflows.
