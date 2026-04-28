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
  assets.lock.json
  .mcp.json
  AGENTS.md
  CLAUDE.md
  assets/
    components/
  model.skp
  snapshots/
    manifest.json
```

Agents can inspect this state with `get_project_state`, list placed objects with
`list_project_components`, and run file checks with `validate_design_project`.

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

Rule precedence is:

1. built-in harness defaults
2. installed designer profile
3. project `design_rules.json`
4. explicit instruction in the current agent session

## Component Registry

The harness uses semantic component metadata before placing reusable objects.
Agents can use `search_components` and `get_component_manifest` to read
dimensions, anchors, clearances, asset paths, and license data.

Use `add_component_instance` when a selected component should become part of the
project source of truth. It updates `design_model.json` and refreshes
`assets.lock.json`.

Use `execute_component_instance` when that project-backed instance should be
sent to SketchUp and linked to the returned SketchUp entity ID.

Project `assets.lock.json` records the components actually referenced by the
design project.

## Visual Output

Screenshots and generated renderings are review artifacts. They can guide design
decisions, but `design_model.json` remains the source of truth for the model.
Snapshot provenance is stored in `snapshots/manifest.json`.
