# Designer Workflow Skill

## Purpose

Guide the designer through the currently implemented SketchUp Agent Harness
workflow. Keep `design_model.json` as the source of truth and use SketchUp as
the executed view.

## Current Supported Flow

### 1. Confirm Project Workspace

The designer should work inside a design project directory, not the source
repository.

Expected files:

- `design_model.json`
- `design_rules.json`
- `assets.lock.json`
- `.mcp.json`
- `snapshots/`
- `snapshots/manifest.json`

Use `get_project_state` to read the current structured model, effective design
rules, asset-lock summary, visual feedback summary, and saved version summary. Use
its execution summary to see whether SketchUp entity IDs have been synced. Use
`list_project_components` to inspect placed component-like instances, and
`validate_design_project` before reporting that the project files are internally
consistent.

If these files are missing, tell the user to initialize the project with:

```bash
sketchup-agent init <project-path> --template bathroom
```

If the user asks whether setup is healthy, guide them to run:

```bash
sketchup-agent doctor <project-path> --sketchup-version 2024
```

If the user asks to inspect current files without opening an agent tool call,
guide them to run:

```bash
sketchup-agent state <project-path>
```

During source development, the equivalent command is:

```bash
cd mcp_server
uv run --extra dev sketchup-agent init <project-path> --template bathroom
```

### 2. Plan Before Executing

For the first vertical slice, prefer `plan_bathroom` before mutation. It returns:

- `design_model`
- `design_rules`
- `validation_report`
- `bridge_operations`

Use this when the user asks to create or review a small bathroom, especially if
SketchUp is not open yet. If the project already has `design_rules.json`, the
planner should use it instead of silently reverting to built-in defaults.

Use `get_design_rules`, `set_design_clearance`, `set_fixture_dimension`, or
`set_design_preference` when the designer changes a project preference before
planning.

### 3. Place Components Into Project Truth

Use `search_components` or `get_component_manifest` before placing reusable
objects. If the designer gives exact coordinates, call `add_component_instance`.
If the designer gives a supported relationship to a rectangular space, call
`add_component_instance_semantic`.

Supported semantic placement relations are:

- `centered_in_space`
- `against_wall` with `wall_side` as `north`, `south`, `east`, or `west`

After component placement, use `plan_project_execution` to confirm the updated
`design_model.json` can be converted into a bridge trace. Use
`execute_project_model` only when the designer wants SketchUp updated.

### 4. Execute Only When the User Wants SketchUp Updated

Use `execute_bathroom_plan` when the user wants the model updated in SketchUp and
the Ruby bridge is running.

If the bridge is not running, use `launch_sketchup_bridge` before execution
rather than only telling the designer to open SketchUp. A successful launch
returns `socket_ready: true`. If it returns `socket_ready: false`, report the
`possible_blockers` field and keep the structured plan/project truth unchanged.

For an existing project that already has `design_model.json`, prefer
`plan_project_execution` before whole-project synchronization. It derives the
bridge trace from current project truth. If it returns skipped instances, report
them and fix the missing space bounds, component references, or registry entries
before executing.

Use `execute_project_model` when the designer wants the current project truth
sent to SketchUp. On success, use `execution_sync` to report which generated
space walls, component instances, and lighting instances received SketchUp
`entity_id` values.

Before calling it, confirm the bridge is available at `/tmp/su_bridge.sock`.
If execution fails because SketchUp is not running, retry the startup path once
with `launch_sketchup_bridge`; then report any environment blockers and keep the
structured plan available.

### 5. Report Structured Results

After planning or execution, summarize:

- whether `validation_report.valid` is true
- failed clearance checks, if any
- files written, if `project_path` was provided
- execution status, if `execute_bathroom_plan` was used
- skipped instances, if `plan_project_execution` refused to convert part of the
  project truth
- execution sync details, if `execute_project_model` was used

Do not replace structured output with only prose. The design model remains the
canonical state.

### 6. Save Reviewable Versions

Use `save_project_version` when the designer asks to save a milestone, compare
alternatives later, or preserve a rollback point. Use `list_project_versions`
when the designer asks what versions exist. Use `compare_project_versions` when
the designer asks how two drafts differ or whether the current project changed
from a saved milestone. Use `restore_project_version` only after the designer
explicitly asks to restore a version, because it overwrites current project
truth files.

### 7. Capture Visual Review Artifacts

Use `capture_project_snapshot` when the user asks for a screenshot or visual
review and a project path is available. Snapshot provenance is recorded in
`snapshots/manifest.json`.

Before asking a rendering or image generation tool to produce a derived visual,
use `prepare_render_brief` to produce a prompt from `design_model.json`,
effective project context, and the source snapshot. The brief must preserve the
structured layout and should be passed through to `record_render_artifact` after
the renderer returns an output path or URL.

When a generated or external rendered image is produced from a snapshot, call
`record_render_artifact` with the output path or URL, renderer tool/model,
prompt, and source snapshot information. Rendered images remain advisory
artifacts; they do not replace `design_model.json`.

If the user wants to act on a screenshot or rendered image, call
`record_visual_feedback` first with proposed structured actions. Only mutate
`design_model.json`, components, rules, materials, or styles after the visual
feedback has been converted into explicit actions.

Use `get_project_state` or `list_visual_feedback` before applying pending visual
actions. After an accepted action has been applied through structured tools, call
`update_visual_feedback_action_status` with `status="applied"` so the manifest
does not become a stale suggestion log.

Use `apply_visual_feedback_action` only for supported structured actions:
component, lighting, material, style, rule, and note. Do not use it to apply
geometry changes from pixels; use dedicated geometry tools instead.

## Supported User Prompts

English examples:

```text
Plan a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light, and
clearance check.
```

```text
Execute the bathroom plan in SketchUp.
```

```text
Sync the current design_model.json to SketchUp.
```

```text
Put the vanity against the north wall of bathroom_001.
```

Chinese examples:

```text
帮我规划一个 2 米 x 1.8 米的卫生间，包含马桶、洗手台、门、镜子和基础照明，并检查通行距离。
```

```text
把这个卫生间方案同步到 SketchUp。
```

```text
把当前 design_model.json 同步到 SketchUp。
```

```text
把洗手台靠 bathroom_001 的北墙放。
```

## Guardrails

- Do not promise full-home automatic design yet.
- Do not claim jurisdictional code compliance. Current rules are ergonomic seed
  defaults.
- Do not use image rendering as source of truth.
- Treat snapshots as advisory artifacts.
- Do not directly apply visual pixels as geometry; convert accepted visual
  feedback into structured actions first.
- Do not write maintainer workflow instructions into designer project files.
