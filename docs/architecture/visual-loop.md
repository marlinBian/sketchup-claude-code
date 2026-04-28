# Visual Loop

The visual loop stores screenshots and future renderings as review artifacts.
It does not replace `design_model.json` as the source of truth.

## Current Scope

The first supported visual workflow is project snapshot capture:

1. The agent plans or executes structured model changes.
2. The user asks for a visual review artifact.
3. `capture_project_snapshot` captures a SketchUp view into `snapshots/`.
4. The tool appends provenance to `snapshots/manifest.json`.
5. `prepare_render_brief` converts the structured project truth and optional
   snapshot into a renderer-ready prompt while preserving geometry constraints.
6. If a rendering or image generation tool creates a derived image,
   `record_render_artifact` stores that output with renderer/model provenance.
7. If the user wants to act on visual feedback, `record_visual_feedback`
   records structured proposed actions in the same manifest before any model
   mutation happens.
8. `list_visual_feedback` and `update_visual_feedback_action_status` track
   proposed, accepted, rejected, and applied actions.
9. `apply_visual_feedback_action` can apply supported structured actions to
   `design_model.json` and mark them applied in one step.

The manifest records:

- snapshot file path
- timestamp
- source model file
- camera preset
- width and height
- optional user prompt
- `advisory: true`

Generated/rendered visual artifacts record:

- generated or rendered image file path or URL
- source snapshot ID or file, when available
- renderer tool and model
- prompt
- optional width and height
- `advisory: true`

The manifest can also record visual reviews. A review contains:

- source snapshot ID or file, when available
- summary of the visual observation
- renderer or reviewer provenance, when available
- proposed structured actions with a target, intent, payload, and status
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

Automatic application is intentionally narrow. Component, lighting, material,
style, rule, and note actions can be applied directly because they map to
existing project truth or `design_rules.json` fields. Geometry actions must use
dedicated structured tools so the agent does not infer physical changes
directly from pixels.

Future image generation or rendering integrations should add renderer/model
provenance to this manifest instead of writing untracked images.
