# Designer Guide

SketchUp Agent Harness is intended to let designers work with SketchUp through
natural-language agent CLIs.

## Core Idea

You describe design intent. The harness turns that intent into structured
project state and SketchUp operations.

The important project files are expected to live in your design project
directory:

```text
my-design-project/
  design_model.json
  design_rules.json
  component_library.json
  assets.lock.json
  .mcp.json
  AGENTS.md
  CLAUDE.md
  .agents/
    skills/
  .claude/
    skills/
  assets/
    components/
  model.skp
  snapshots/
    manifest.json
```

Agents can inspect this state with `get_project_state`, list placed objects with
`list_project_components`, and run file checks with `validate_design_project`.

When SketchUp execution is requested, agents can start the live bridge with
`launch_sketchup_bridge`. This opens SketchUp through a model window and waits
for `/tmp/su_bridge.sock`. If SketchUp is blocked by a welcome screen, update
prompt, sign-in prompt, license prompt, or missing bridge install, the tool
returns structured blockers instead of silently failing.

## Example Requests

English:

```text
Create a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light,
and clearance check.
```

Chinese:

```text
创建一个 2 米 x 1.8 米的卫生间，包含马桶、洗手台、门、镜子、基础照明，并检查通行距离。
```

## Design Rules

Project-specific design rules should live in `design_rules.json`. These rules
can capture preferred clearances, fixture sizes, material preferences, or local
workflow conventions.

Agents can read rules with `get_design_rules` and update project preferences
with `set_design_clearance`, `set_fixture_dimension`, and
`set_design_preference`.

Reusable personal defaults can live in a designer profile at
`~/.sketchup-agent-harness/design_rules.json`, activated through
`SKETCHUP_AGENT_DESIGN_RULES`. Agents can inspect and create that profile with
`get_designer_profile_status` and `init_designer_profile`. They should update it
with `set_designer_profile_clearance`,
`set_designer_profile_fixture_dimension`, or
`set_designer_profile_preference` only when you explicitly ask for a preference
to apply to future projects.

Rule precedence is:

1. built-in harness defaults
2. installed designer profile from `SKETCHUP_AGENT_DESIGN_RULES`
3. project `design_rules.json`
4. explicit instruction in the current agent session

## Component Registry

The harness uses semantic component metadata before placing reusable objects.
Agents can use `search_components` and `get_component_manifest` to read
dimensions, anchors, clearances, asset paths, and license data.

Use `register_project_component` when a project-specific object should become a
reusable semantic component. It writes metadata to `component_library.json`.
Search and placement tools use this project-local registry when `project_path`
is provided.

Use `import_project_component_asset` when the reusable object already exists as
a local `.skp` file. It copies that file into `assets/components/` and registers
the required semantic metadata. The agent still needs dimensions, anchors,
clearance assumptions, and license/provenance details; the model file alone is
not sufficient.

Use `add_component_instance` when a selected component should become part of the
project source of truth. It updates `design_model.json` and refreshes
`assets.lock.json`.

Use `add_component_instance_semantic` when the request is relative to a known
rectangular space, such as placing a vanity against the north wall or centering
a sofa in a room. It resolves the relationship to millimeter coordinates,
updates `design_model.json`, and records the placement assumption. It checks the
component's bounds against the space bounds, but it is not a complete collision
or code-compliance solver.

Use `add_component_instance_relative` when the request is relative to an
existing component instance, such as placing a mirror above a vanity. It can
reuse wall provenance from the reference component so wall-mounted objects stay
on the same wall plane.

Use `execute_component_instance` when that project-backed instance should be
sent to SketchUp and linked to the returned SketchUp entity ID.

Project `assets.lock.json` records the components actually referenced by the
design project.

## Versions

Use `save_project_version` to preserve structured project truth milestones and
`list_project_versions` to inspect saved drafts. Use `compare_project_versions`
before restoring or when you want a structured A/B comparison of spaces,
components, rules, assets, or visual artifacts. Use `restore_project_version`
only when you explicitly want to overwrite current project files from a saved
version.

## Visual Output

Screenshots and generated renderings are review artifacts. They can guide design
decisions, but `design_model.json` remains the source of truth for the model.
Snapshot, render, and visual-feedback provenance is stored in
`snapshots/manifest.json`.

Use `record_render_artifact` for images produced by rendering or image
generation tools. Use `prepare_render_brief` before rendering when an agent
needs a prompt that preserves project geometry, source snapshot provenance, and
renderer settings. Use `record_visual_feedback` when a designer wants to convert
visual observations into explicit component, lighting, material, style, rule,
or note actions.
