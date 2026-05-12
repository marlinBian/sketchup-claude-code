---
name: natural-commands
description: Map English and Chinese natural-language design requests to supported SketchUp Agent Harness tools.
---

# Natural Command Mapping

## Purpose

Map English and Chinese natural-language design requests to supported MCP tools.
This file is user-facing runtime guidance, not maintainer workflow guidance.

## Current Intent Mapping

- Start a project: "start a new design", "开始新项目".
  Use `sketchup-agent init` guidance.
- Plan a bathroom: "plan a small bathroom", "规划卫生间".
  Use `plan_bathroom`.
- Create or resize a room: "create a 4m by 5m studio", "建一个4米乘5米的房间".
  Use `set_project_space` to write rectangular space bounds into
  `design_model.json`, then use `plan_project_execution` or
  `execute_project_model` if the designer wants SketchUp updated.
- Execute a bathroom: "sync to SketchUp", "同步到 SketchUp".
  Use `execute_bathroom_plan`.
- Execute current project truth: "sync the current design model", "同步当前模型".
  Use `plan_project_execution` first, then `execute_project_model` when the
  trace has no skipped instances and the bridge is running.
  Use `clean_before_execute=True` when the user expects SketchUp to match the
  current project truth exactly rather than append another copy.
- Start SketchUp bridge: "open SketchUp", "启动 SketchUp", "连接 SketchUp".
  Use `launch_sketchup_bridge` and report `possible_blockers` if
  `socket_ready` is false.
- Import floor plan source: "import this floor plan", "导入这张户型图".
  Use the staged import flow from `import-floorplan`: prepare or reference the
  source, extract, choose either fast coarse import or evidence-backed
  `source_interpretation_path`, generate `design_model.json`, then clean-replay
  to SketchUp when requested. If the source is a visible chat/CLI attachment
  with no local file path, use `source_reference` with
  `source_reference_type=chat_image_attachment` instead of inventing a text-note
  source file. Do not ask the designer to confirm routine wall, door, window, or
  numeric candidates before generating the first model. Claim source-fidelity
  only when structured source constraints exist with honest provenance. Use the
  tool-generated project-local dynamic skill as scoped memory; never add
  source-specific facts to shipped skills.
- Rescale imported source: "this plan should be 8200 mm wide",
  "这个户型整体宽度应该是 8200 毫米". Use `rescale_imported_model` or
  `repair_imported_region` rather than asking the designer to edit JSON.
- Repair imported mismatch: "this door differs from the source",
  "这个门和原图不一致". Use `review_model_against_import_source`, then
  `repair_imported_region` with the specific correction. If the correction
  should guide future turns for the same project/source, update the project
  dynamic runtime skill through `project-runtime-memory`.
- Normalize imported exterior wall alignment: "this straight exterior wall is
  offset", "这条外墙应该是直的". Use
  `normalize_imported_wall_alignment` when imported near-boundary wall segments
  are offset by a small wall-thickness-sized step.
- Repair imported exterior corner notch: "the top-left corner notch is
  missing", "左上角折角漏掉了". Use `repair_imported_corner_notch` when a
  source-backed exterior stepped corner is missing from generated truth.
- Repair imported boundary coverage: "this room boundary is missing a wall",
  "这里漏了一段墙". Use `review_imported_boundary_coverage`, then
  `repair_imported_boundary_coverage` when an imported space footprint edge
  exists but the explicit wall list missed a wall segment. Long gaps can be
  repaired automatically when wall-continuity evidence is strong; short gaps
  should remain opening/intentional-gap candidates unless the source evidence
  supports a wall.
- Repair imported shell overreach: "the import has an extra enclosed area",
  "这里多包了一块空间", "右下角多出一块区域". Use
  `review_imported_wall_space_consistency`, then
  `repair_imported_shell_overreach` when explicit imported walls enclose space
  outside any imported room or balcony footprint.
- Search components: "find a sofa", "找一个马桶".
  Use `search_components` for machine-readable registry data. Use
  `search_local_library` only for a short display summary.
- Import local component asset: "use this downloaded SKP as a component",
  "把这个 skp 加入组件库". Use `import_project_component_asset` when the user
  provides a local `.skp` path plus enough dimensions/license context.
- Place component: "place the sofa here", "放一个沙发".
  When a project path exists, use `add_component_instance` to update
  `design_model.json`, then use `plan_project_execution` or
  `execute_project_model` if the designer wants SketchUp updated. Use
  `place_component` only for ad hoc live SketchUp placement without a
  project-backed instance.
- Place component by relationship: "put the vanity against the north wall",
  "把洗手台靠北墙放", "center the sofa in the room", "把沙发放在房间中间".
  When a project path and rectangular space exist, use
  `add_component_instance_semantic` with `relation="against_wall"` or
  `relation="centered_in_space"`. Use `wall_side` only for `against_wall`.
- Place component relative to another component: "put the mirror above the
  vanity", "把镜子放在洗手台上方". Use `add_component_instance_relative` with
  `relation="above"` after confirming the reference instance ID.
- Create primitive: "make a box", "建一个柜体占位".
  Use `create_box`.
- Change material: "make it white", "改成白色".
  Use `apply_material`.
- Apply style: "use Scandinavian style", "换成北欧风".
  Use `apply_style`.
- Capture view: "take a snapshot", "截图".
  Use `capture_project_snapshot` when a project path is available.
- Prepare render prompt: "render this view", "生成一张效果图".
  Use `prepare_render_brief` before calling an image or rendering tool so the
  generated prompt preserves project geometry and snapshot provenance.
- Record rendered image: "save this render", "记录这张渲染图".
  Use `record_render_artifact` to preserve renderer/model provenance before
  interpreting the image as feedback.
- Save version: "save this version", "保存一下".
  Use `save_project_version` when a project path is available. `save_version`
  is only a compatibility alias.
- Remember project-local guidance: "remember that this source uses this symbol",
  "以后这个项目按这个规则理解". Use `project-runtime-memory` to create or
  update a project/session dynamic runtime skill in the active design project.
  Do not put this scoped guidance into shipped product skills.
- Compare versions: "compare these two drafts", "对比两个方案".
  Use `compare_project_versions` for saved versions or a saved version against
  current project truth.
- Check layout: "check this layout", "检查一下方案".
  Use `validate_project_layout` for geometry and clearance checks. Use
  `validate_design_project` for the broader project health check.

Chinese examples are deliberate bilingual user prompt support. Keep internal
instructions and tool names English-first.

## Ambiguity Handling

Ask one short question only when execution would otherwise be unsafe:

- Missing target: "Which object should I change?"
- Missing location: "Where should this component be placed?"
- Missing project path: "Which project directory should I initialize?"
- Bridge dependency: use `launch_sketchup_bridge` once before asking the
  designer to manually resolve SketchUp windows, sign-in, license, or update
  prompts.

When a reasonable default exists, use it. For the first supported planning
slice, default to the bathroom template and report the exact assumptions.

## Chinese Alias Handling

Pass Chinese component words directly to `search_components` first:

```python
search_components(query="马桶", category="fixture", limit=5)
```

If search is weak, retry with a canonical English term:

```python
search_components(query="toilet", category="fixture", limit=5)
```

## Guardrails

- Do not invent unsupported automation from a natural-language request.
- Do not ask multiple survey-style questions before using implemented defaults.
- Do not turn import into a preflight approval workflow; import should generate
  working truth first and support source-backed repair later.
- Do not turn one user's floor plan into reusable extraction rules. Prefer
  general geometry, topology, scale, provenance, and source-evidence logic.
- Do not mix Chinese into code identifiers, schema keys, or tool names.
- Do not treat rendered images as source of truth.
