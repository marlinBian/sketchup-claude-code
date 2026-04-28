# Runtime vs Development Skills

The repository contains two different categories of skills. They must not be
mixed.

## Runtime Skills

Runtime skills live in `skills/`.

They are installed with the Claude or Codex plugin and are meant to guide the
designer-facing natural language experience. They should describe design
workflows, spatial operations, component search, semantic placement, style
application, and validation behavior.

Runtime skills are part of the product surface.

## Development Skills

Development skills live outside this product repository. In the maintainer's
local workspace they are stored under:

```text
~/Code/ai4design/skills/sketchup-agent-harness/
```

They help maintain this repository. They are not shipped to designers by
default, and they should not be referenced by runtime plugin manifests.

Initial development skills:

- `suh-architect`: architecture and roadmap decisions
- `suh-contracts`: schemas, MCP contracts, fixtures, and compatibility tests
- `suh-release-smoke`: release and install smoke checks

Development skills can be installed manually by the maintainer or exposed
through a private Codex marketplace later. They should remain in the
`ai4design` development workspace unless there is a deliberate decision to
publish a separate maintainer plugin.

## Rule

If a skill helps a designer create or review a SketchUp design, it belongs in
`skills/`.

If a skill helps a maintainer change this repository, it belongs outside the
product repository in the `ai4design` development workspace.
