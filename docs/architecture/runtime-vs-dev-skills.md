# Skill Layers

SketchUp Agent Harness uses three different skill layers. They must not be
mixed.

## Product Runtime Skills

Product runtime skills live in `skills/`.

They are installed with the Claude or Codex plugin and are meant to guide the
designer-facing natural language experience. They should describe design
workflows, spatial operations, component search, semantic placement, style
application, and validation behavior.

Runtime skills are part of the product surface.

The repository copy is the authoring source, not the expected designer runtime
location. Installation must register or copy these skills through the supported
Claude, Codex, or future agent CLI plugin/skill mechanisms so the selected AI
tool can load them normally.

Product runtime skills must stay generic across projects. They may define how
to create, update, and use project-specific runtime memory, but they must not
encode one source image's room names, coordinates, dimensions, labels, or
designer corrections as reusable product behavior.

## Project/Session Dynamic Runtime Skills

Project/session dynamic runtime skills are generated during designer use inside
the active design project, usually under that project's supported agent skill
locations, such as:

```text
<design-project>/.agents/skills/
<design-project>/.claude/skills/
```

These skills are not shipped by default. They can be created after importing a
source plan, after repeated designer corrections, or after the designer defines
project-specific preferences. They are allowed to be specific to a source,
project, or session.

Examples of valid dynamic runtime skill content:

- a source-specific symbol legend extracted from one imported floor plan
- known corrections the designer made for one import source
- project-local room naming conventions
- project-local preferences that should guide later natural-language changes
- confidence notes and repair history for an import source

Dynamic runtime skills are guidance only. `design_model.json` remains the
canonical editable truth, and import evidence remains under
`imports/<import_id>/`.

Dynamic runtime skills must not be copied into the product repository's
`skills/` directory, and they must not be stored in maintainer development skill
directories. If a dynamic skill exposes a pattern that should apply broadly,
generalize the pattern first, add tests across variants, then update product
code, docs, or baseline runtime skills.

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
`skills/` only when it is generic product behavior and must be distributed
through the product install/plugin flow.

If a skill helps a designer continue a specific project or remember facts about
a specific import source, it belongs in that active design project's dynamic
runtime skill locations.

If a skill helps a maintainer change this repository, it belongs outside the
product repository in the `ai4design` development workspace.
