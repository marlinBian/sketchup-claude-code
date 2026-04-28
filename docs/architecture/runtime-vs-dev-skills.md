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

The repository copy is the authoring source, not the expected designer runtime
location. Installation must register or copy these skills through the supported
Claude, Codex, or future agent CLI plugin/skill mechanisms so the selected AI
tool can load them normally.

## Development Skills

Development skills live outside this product repository. In the maintainer's
local workspace they are stored under:

```text
~/Code/ai4design/.agents/skills/
```

They help maintain this repository. They are not shipped to designers by
default, and they should not be referenced by runtime plugin manifests.

Initial development skills:

- `suh-architect`: architecture and roadmap decisions
- `suh-baseline-ci`: repository hygiene, test setup, and CI behavior
- `suh-bridge-ruby`: SketchUp Ruby bridge changes
- `suh-component-registry`: component metadata and registry behavior
- `suh-contracts`: schemas, MCP contracts, fixtures, and compatibility tests
- `suh-implement-slice`: end-to-end product slices
- `suh-install-flow`: installation and onboarding behavior
- `suh-issue-triage`: GitHub issues, PR feedback, and user reports
- `suh-language-audit`: English-first and Chinese localization checks
- `suh-mcp-tools`: Python MCP tools and resources
- `suh-release-smoke`: release and install smoke checks
- `suh-runtime-skills`: designer-facing runtime skill authoring
- `suh-skill-governance`: maintainer skill evolution and gap handling
- `suh-visual-loop`: snapshots, camera capture, and rendering feedback

Development skills can be installed manually by the maintainer or exposed
through a private Codex marketplace later. They should remain in the
`ai4design` development workspace unless there is a deliberate decision to
publish a separate maintainer plugin.

## Rule

If a skill helps a designer create or review a SketchUp design, it belongs in
`skills/` and must be distributed through the product install/plugin flow.

If a skill helps a maintainer change this repository, it belongs outside the
product repository in the `ai4design` development workspace.
