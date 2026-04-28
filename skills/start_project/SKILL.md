# Start Project Runtime Guide

## Purpose

Start from a clean designer project workspace. Designers should not operate
directly inside the harness source repository.

## When to Use

Use this guide when the user says:

- "start a new design"
- "create a new SketchUp Agent Harness project"
- "开始新项目"
- "新项目"

## Current Initialization Path

If the user has not initialized a project directory, guide them to run:

```bash
sketchup-agent init <project-path> --template bathroom
```

For a blank project:

```bash
sketchup-agent init <project-path> --template empty
```

For maintainers running from the source checkout:

```bash
cd mcp_server
uv run --extra dev sketchup-agent init <project-path> --template bathroom
```

## After Initialization

Check that the project contains:

- `design_model.json`
- `design_rules.json`
- `assets.lock.json`
- `.mcp.json`
- `AGENTS.md`
- `CLAUDE.md`
- `snapshots/`
- `snapshots/manifest.json`

Then continue with `plan_bathroom` or `execute_bathroom_plan` for the first
supported vertical slice. If the designer gives project preferences, store them
in `design_rules.json` before planning.

## User-Facing Guidance

English:

```text
Your project is initialized. The project state lives in design_model.json and
design_rules.json. We can now plan the bathroom slice or execute it in SketchUp.
```

Chinese:

```text
项目已经初始化。当前项目状态保存在 design_model.json 和 design_rules.json 中。接下来可以规划卫生间方案，或同步到 SketchUp。
```

## Guardrails

- Ask only for information needed to initialize or choose a template.
- Do not create a custom directory structure outside the current project shape.
- Do not promise broad room automation beyond implemented tools.
- Keep `design_model.json` as the canonical source of truth.
