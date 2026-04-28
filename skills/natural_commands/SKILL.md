# Natural Command Mapping

## Purpose

Map English and Chinese natural-language design requests to supported MCP tools.
This file is user-facing runtime guidance, not maintainer workflow guidance.

## Current Intent Mapping

- Start a project: "start a new design", "开始新项目".
  Use `sketchup-agent init` guidance.
- Plan a bathroom: "plan a small bathroom", "规划卫生间".
  Use `plan_bathroom`.
- Execute a bathroom: "sync to SketchUp", "同步到 SketchUp".
  Use `execute_bathroom_plan`.
- Execute current project truth: "sync the current design model", "同步当前模型".
  Use `plan_project_execution` first, then `execute_project_model` when the
  trace has no skipped instances and the bridge is running.
- Search components: "find a sofa", "找一个马桶".
  Use `search_local_library`.
- Place component: "place the sofa here", "放一个沙发".
  Use `place_component`.
- Create primitive: "make a box", "建一个柜体占位".
  Use `create_box`.
- Change material: "make it white", "改成白色".
  Use `apply_material`.
- Apply style: "use Scandinavian style", "换成北欧风".
  Use `apply_style`.
- Capture view: "take a snapshot", "截图".
  Use `capture_project_snapshot` when a project path is available.
- Save version: "save this version", "保存一下".
  Use `save_version`.

Chinese examples are deliberate bilingual user prompt support. Keep internal
instructions and tool names English-first.

## Ambiguity Handling

Ask one short question only when execution would otherwise be unsafe:

- Missing target: "Which object should I change?"
- Missing location: "Where should this component be placed?"
- Missing project path: "Which project directory should I initialize?"
- Bridge dependency: "Is SketchUp running with the bridge loaded?"

When a reasonable default exists, use it. For the first supported planning
slice, default to the bathroom template and report the exact assumptions.

## Chinese Alias Handling

Pass Chinese component words directly to `search_local_library` first:

```python
search_local_library(query="马桶", category="fixture", limit=5)
```

If search is weak, retry with a canonical English term:

```python
search_local_library(query="toilet", category="fixture", limit=5)
```

## Guardrails

- Do not invent unsupported automation from a natural-language request.
- Do not ask multiple survey-style questions before using implemented defaults.
- Do not mix Chinese into code identifiers, schema keys, or tool names.
- Do not treat rendered images as source of truth.
