# Visual Loop

The visual loop stores screenshots and future renderings as review artifacts.
It does not replace `design_model.json` as the source of truth.

## Current Scope

The first supported visual workflow is project snapshot capture:

1. The agent plans or executes structured model changes.
2. The user asks for a visual review artifact.
3. `capture_project_snapshot` captures a SketchUp view into `snapshots/`.
4. The tool appends provenance to `snapshots/manifest.json`.

The manifest records:

- snapshot file path
- timestamp
- source model file
- camera preset
- width and height
- optional user prompt
- `advisory: true`

## Project Files

```text
my-design-project/
  design_model.json
  snapshots/
    manifest.json
    20260428T010203Z_top.png
```

## Boundary

Screenshots and rendered images can guide design decisions. If the user accepts
a visual suggestion, the agent must convert that suggestion into structured
model changes, component selections, rule updates, or material changes before
mutating the project truth.

Future image generation or rendering integrations should add renderer/model
provenance to this manifest instead of writing untracked images.
