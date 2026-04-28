# Roadmap

## M0: Reposition

- Rename the project identity to SketchUp Agent Harness.
- Keep Claude support working.
- Add Codex plugin scaffolding.
- Document the designer project workspace boundary.

## M1: Bathroom Vertical Slice

Target prompt:

> Create a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light,
> and clearance check.

Required work:

- define `design_rules.json` seed rules for bathroom clearances
- normalize component manifest schema
- add fixtures for a tiny bathroom project
- validate placement before mutating SketchUp
- capture a snapshot after generation

## M2: Install Flow

- add `sketchup-agent init`
- configure Claude and Codex MCP entries from the same source
- install or update the SketchUp Ruby bridge
- create a clean designer project directory

## M3: Component Registry

- merge duplicate library manifests
- add schema validation for component manifests
- add local cache and `assets.lock.json`
- defer public website until registry workflow proves useful

## M4: Visual Loop

- capture SketchUp camera views
- pass screenshots or line views to image generation/rendering tools
- keep generated visuals advisory; `design_model.json` remains the source of truth
