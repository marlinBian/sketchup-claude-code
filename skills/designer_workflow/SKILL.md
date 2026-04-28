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

Use `get_project_state` to read the current structured model,
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

### 3. Execute Only When the User Wants SketchUp Updated

Use `execute_bathroom_plan` when the user wants the model updated in SketchUp and
the Ruby bridge is running.

Before calling it, confirm the bridge is expected to be available at
`/tmp/su_bridge.sock`. If execution fails because SketchUp is not running, report
that as an environment issue and keep the structured plan available.

### 4. Report Structured Results

After planning or execution, summarize:

- whether `validation_report.valid` is true
- failed clearance checks, if any
- files written, if `project_path` was provided
- execution status, if `execute_bathroom_plan` was used

Do not replace structured output with only prose. The design model remains the
canonical state.

### 5. Capture Visual Review Artifacts

Use `capture_project_snapshot` when the user asks for a screenshot or visual
review and a project path is available. Snapshot provenance is recorded in
`snapshots/manifest.json`.

## Supported User Prompts

English examples:

```text
Plan a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light, and
clearance check.
```

```text
Execute the bathroom plan in SketchUp.
```

Chinese examples:

```text
帮我规划一个 2 米 x 1.8 米的卫生间，包含马桶、洗手台、门、镜子和基础照明，并检查通行距离。
```

```text
把这个卫生间方案同步到 SketchUp。
```

## Guardrails

- Do not promise full-home automatic design yet.
- Do not claim jurisdictional code compliance. Current rules are ergonomic seed
  defaults.
- Do not use image rendering as source of truth.
- Treat snapshots as advisory artifacts.
- Do not write maintainer workflow instructions into designer project files.
