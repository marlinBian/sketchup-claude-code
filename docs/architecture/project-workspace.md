# Project Workspace

This file defines what a designer's working directory should contain. Designers
should not clone the harness repository to create a design project.

## Target Shape

```text
my-design-project/
  design_model.json
  design_rules.json
  assets.lock.json
  model.skp
  snapshots/
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

`assets.lock.json` records the components actually used by this project,
including component IDs, versions, local cache paths, upstream source URLs, and
license metadata.

`model.skp` is the SketchUp model generated or synchronized by the bridge.

`snapshots/` stores captures used for review, regression checks, and visual
handoff.

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
