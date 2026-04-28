# Project Workspace

This file defines what a designer's working directory should contain. Designers
should not clone the harness repository to create a design project.

## Target Shape

```text
my-design-project/
  design_model.json
  design_rules.json
  assets.lock.json
  assets/
    components/
  model.skp
  snapshots/
    manifest.json
  versions/
    draft_1/
      metadata.json
      design_model.json
```

## Files

`design_model.json` is the spatial source of truth. It describes spaces,
components, lighting, semantic anchors, layers, and known SketchUp entity IDs in
millimeters.

The legacy hidden filename `.design_model.json` remains readable during the
migration window, but new project initialization must create `design_model.json`.

`design_rules.json` stores project-level preferences and constraints. It should
override built-in defaults without modifying the harness installation.

The first bundled rules are deliberately small bathroom seed rules. They are
ergonomic defaults, not jurisdictional building code. Validation reports should
state whether a value came from built-in defaults, an installed profile,
project-local rules, or the active user instruction.

`assets.lock.json` records the components actually used by this project. It
includes component IDs, local cache paths, upstream source metadata when known,
license metadata, and procedural fallback information.

`assets/components/` is the project-local cache root for component geometry. The
initial implementation creates this directory and records target cache paths.
External downloads are still explicit actions, not automatic background work.

`model.skp` is the SketchUp model generated or synchronized by the bridge.

Agents can inspect project state through MCP tools:

- `get_project_state` reads the current `design_model.json`, effective
  `design_rules.json`, compact `assets.lock.json`, and visual feedback
  summaries, plus saved version and bridge execution summaries when those files
  exist
- `list_project_components` returns component and lighting instances
- `validate_design_project` runs the same core checks as
  `sketchup-agent validate`, including whether current project truth can produce
  a bridge execution trace without skipped instances
- `add_component_instance` records a selected registry component in
  `design_model.json` and refreshes `assets.lock.json`
- `execute_component_instance` executes a project-backed component instance in
  SketchUp and records the returned entity ID when available
- `plan_project_execution` derives a deterministic bridge trace from the whole
  current `design_model.json` without requiring SketchUp
- `execute_project_model` runs that project trace against the bridge and records
  returned entity IDs and operation metadata back into `design_model.json`

`snapshots/` stores captures used for review, regression checks, and visual
handoff. `snapshots/manifest.json` records provenance for each artifact and
marks visual outputs and visual feedback action plans as advisory.

`versions/` stores structured project truth snapshots. Version snapshots copy
the core project files for review and rollback planning; they do not replace Git
or make SketchUp pixels the source of truth.

## Rule Precedence

Rules should resolve in this order, from lowest to highest priority:

1. built-in standards bundled with the harness
2. installed designer profile
3. `design_rules.json` in the project
4. explicit user instruction in the current CLI session

The MCP server should report which rule source was used when a validation result
matters to a design decision.

## Installation Boundary

The harness installation lives outside the design project. A future
`sketchup-agent init` command should create only project files and lightweight
agent settings. It should not copy source code into the design project.
