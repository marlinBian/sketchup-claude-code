# Capability Map

This document summarizes the product capabilities that belong to SketchUp Agent
Harness as product truth. It is intentionally separate from maintainer workflow
notes and central knowledge-base abstractions.

## Product Boundary

SketchUp Agent Harness is a CLI-first natural-language control layer for
SketchUp. Claude CLI and Codex CLI are adapters. The shared product core is:

- Python MCP server and command-line tools
- SketchUp Ruby bridge
- structured project truth files
- designer-facing runtime skills
- component and design-rule metadata
- install, validation, smoke, and release checks

Designers should work in their own design project directories. They should not
need to edit this source repository during normal use.

## Project Workspace

A design project owns the working state:

- `design_model.json`: editable design truth
- `design_rules.json`: project-local rules and preferences
- `component_library.json`: project component metadata
- `assets.lock.json`: used component and asset references
- `imports/`: imported source material, manifests, evidence, and extracted data
- `snapshots/manifest.json`: visual review artifacts and provenance
- `.agents/skills/`: Codex project-local runtime skills
- `.claude/skills/`: Claude project-local runtime skills

SketchUp scenes, screenshots, image renders, and imported source files are
execution or review artifacts. They do not replace `design_model.json` as the
working source of truth.

## Runtime Skill Layers

The product has three distinct skill layers:

- Shipped runtime skills live in `skills/` and are packaged for designers.
- Project/session dynamic runtime skills may be generated inside a designer
  project to preserve source-specific import memory or designer corrections.
- Maintainer development skills live outside the product repository in the
  AI4Design workspace.

Shipped runtime skills must stay generic. They must not encode one imported
floor plan, one customer source, or one debugging session as product behavior.

## Current 1.0 Capabilities

### Installation And Packaging

- Package the Python MCP server as `sketchup-agent-harness-mcp`.
- Package designer runtime skills into the installed wheel.
- Package the SketchUp Ruby bridge runtime into the installed wheel.
- Initialize project-local Claude and Codex runtime skill directories.
- Install the SketchUp bridge into a selected SketchUp plugin directory.
- Run startup, doctor, smoke, and release checks from source and installed
  package paths.
- Build both source distribution and wheel release artifacts.

### MCP And CLI Tools

- Initialize design projects with `sketchup-agent init`.
- Validate project files with `sketchup-agent validate`.
- Inspect project truth and effective rules with `sketchup-agent state`.
- Diagnose harness, project, and bridge state with `sketchup-agent doctor`.
- Plan and execute project bridge operations.
- Launch SketchUp through a model window and wait for the bridge socket.
- Run headless smoke and release smoke checks.

### SketchUp Ruby Bridge

- Load the bridge from SketchUp via `su_bridge.rb`.
- Listen on a local socket.
- Execute bridge operations generated from project truth.
- Return operation results and runtime metadata.
- Keep live SketchUp integration separate from default headless tests.

### Structured Project Truth

- Validate `design_model.json`, `design_rules.json`, component manifests,
  asset locks, import manifests, and snapshot manifests.
- Represent spaces, walls, openings, component instances, rules, assumptions,
  provenance, and bridge execution plans.
- Keep model mutations explicit and auditable.

### Component Registry

- Search packaged and project-local component metadata.
- Read canonical component manifests.
- Add project-local component instances.
- Lock used component references into project assets.
- Track dimensions, bounds, anchors, clearances, aliases, source, license, and
  redistribution notes.

### Design Rules

- Store built-in default rules.
- Merge optional designer profile rules.
- Override rules at project level.
- Apply rules to deterministic planning and validation.
- Keep validation reports explicit about failed checks.

### Import Pipeline

- Register DWG, DXF, PDF, image, scan, photo, or source-reference imports.
- Generate an editable first-pass working model instead of blocking on repeated
  user confirmations.
- Store source provenance, assumptions, extracted evidence, and generated
  project state under `imports/`.
- Generate project-local dynamic runtime memory when source-specific
  interpretation is needed.
- Preserve the rule that imported sources guide the working truth but do not
  become the only truth.

### Visual Loop

- Store visual snapshots with provenance.
- Treat screenshots and rendered images as review artifacts.
- Map accepted visual feedback back into structured model changes instead of
  making pixels the source of truth.

## Known Limits

- Image and drawing imports are first-pass working models, not survey-grade
  conversions.
- Live SketchUp bridge validation requires SketchUp to be open in a model
  window with the bridge loaded.
- Component assets are still mostly semantic placeholders unless richer model
  assets are installed or registered.
- Public component registry distribution is intentionally deferred until
  contribution and storage needs are proven.
- Designer-facing installation still depends on available Claude and Codex
  plugin mechanisms.

## Knowledge Ownership

Product facts belong in this repository. Maintainer workflow lessons belong in
the AI4Design workspace. Stable, generalized insights may be promoted to the
central knowledge base through the federation workflow, but central summaries do
not replace this repository as product truth.
