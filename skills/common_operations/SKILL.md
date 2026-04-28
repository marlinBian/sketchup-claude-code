# Common Operations Skill

## Purpose

Use the currently implemented MCP tools for frequent designer requests. Keep
responses grounded in the tools that exist today.

## Operating Rules

Before mutating SketchUp:

- Read or infer the active project workspace.
- Preserve `design_model.json` as the source of truth when project files exist.
- Use millimeters for positions and dimensions.
- Prefer semantic registry data over guessed component dimensions.

After mutation:

- Report whether the bridge operation succeeded.
- Mention files written when a project path was provided.
- Keep any failed operation actionable and retryable.

When SketchUp execution is requested but `/tmp/su_bridge.sock` is unavailable,
use `launch_sketchup_bridge` before asking the designer to intervene. Start with
`sketchup_version="2024"` when no version is known. If the result reports update,
welcome-screen, sign-in, or license blockers, pass those structured blockers
back to the designer.

## Supported Tool Groups

Scene and geometry:

- `launch_sketchup_bridge`
- `get_bridge_info`
- `get_scene_info`
- `get_selection_info`
- `create_wall`
- `create_face`
- `create_box`
- `create_door`
- `create_window`
- `create_stairs`

Components and layout:

- `set_project_space`
- `search_components`
- `get_component_manifest`
- `import_project_component_asset`
- `register_project_component`
- `register_selected_component`
- `add_component_instance`
- `execute_component_instance`
- `plan_project_execution`
- `execute_project_model`
- `search_local_library`
- `place_component`
- `move_entity`
- `rotate_entity`
- `scale_entity`
- `copy_entity`

Materials, style, and lighting:

- `apply_material`
- `apply_style`
- `place_lighting`

Views, reporting, and versions:

- `set_camera_view`
- `capture_design`
- `capture_project_snapshot`
- `record_render_artifact`
- `record_visual_feedback`
- `list_visual_feedback`
- `update_visual_feedback_action_status`
- `apply_visual_feedback_action`
- `generate_project_report`
- `generate_report`
- `save_project_version`
- `list_project_versions`
- `restore_project_version`
- `save_version` (compatibility alias for `save_project_version`)
- `list_versions` (compatibility alias for `list_project_versions`)

## Common Flows

### Place a Registry Component

Project-backed placement:

```python
search_components(query="sofa", category="furniture", limit=5)
add_component_instance(
    project_path="<project-path>",
    component_id="sofa_modern_2seat",
    position_x=3000,
    position_y=2000,
    position_z=0
)
execute_component_instance(
    project_path="<project-path>",
    instance_id="sofa_001"
)
```

Ad hoc live SketchUp placement without project truth:

```python
place_component(
    component_name="Modern 2-Seat Sofa",
    position_x=3000,
    position_y=2000,
    position_z=0,
    rotation=0,
    scale=1
)
```

Use `execute_component_instance` when the designer also wants SketchUp updated
and the bridge is running. Use `place_component` only for ad hoc execution
without a project-backed instance.

### Execute Current Project Truth

Use `set_project_space` when the designer asks to create or resize a room,
studio, office, hallway, storage area, or other rectangular space in project
truth:

```python
set_project_space(
    project_path="<project-path>",
    space_id="studio_001",
    space_type="office",
    width=4000,
    depth=5000,
    height=2800
)
```

This writes `spaces.<space_id>.bounds` in `design_model.json`, clears stale wall
execution feedback for that space, and marks SketchUp sync status dirty until
`execute_project_model` runs successfully.

Before sending the whole project to SketchUp, build the trace from the current
`design_model.json`:

```python
plan_project_execution(project_path="<project-path>")
```

If `skipped_count` is greater than zero, report the skipped instances and fix
the project truth or registry metadata before execution. Do not silently omit
components.

When the trace is clean and SketchUp bridge is running:

```python
execute_project_model(project_path="<project-path>")
```

Use `execute_project_model` for project-backed synchronization. It records
returned SketchUp entity IDs and operation metadata back into
`design_model.json` when execution succeeds, including generated space walls
under `spaces.<space_id>.execution.walls.<side>`.

### Create Simple Geometry

```python
create_box(
    corner_x=0,
    corner_y=0,
    corner_z=0,
    width=1200,
    depth=450,
    height=750,
    layer="Furniture"
)
```

### Apply a Style Preset

```python
apply_style(style_name="scandinavian")
```

### Capture a View

```python
capture_project_snapshot(
    project_path="<project-path>",
    view_preset="top",
    label="review"
)
```

When the designer accepts or discusses a visual suggestion, record the
interpretation as structured proposed actions before changing project truth:

```python
record_visual_feedback(
    project_path="<project-path>",
    summary="The vanity feels too heavy in the captured view.",
    actions=[
        {
            "type": "component",
            "target": "vanity_001",
            "intent": "Replace with a narrower wall-mounted vanity.",
            "status": "proposed"
        }
    ],
    source_snapshot_id="<snapshot-id>"
)
```

Use `list_visual_feedback` to inspect pending visual actions. After the user
accepts an action and the agent applies the corresponding structured model,
component, rule, material, or style change, call
`update_visual_feedback_action_status` with `status="applied"`.

For supported action types, use `apply_visual_feedback_action` to apply the
structured change and mark the action as applied in one step. The automatic path
is intentionally limited to component, lighting, material, style, rule, and note
actions; geometry changes require a more specific structured tool.

## Useful Dimensions

| Item | Typical Millimeters |
| --- | ---: |
| 1 meter | 1000 |
| Interior door width | 700-900 |
| Interior door height | 2000-2100 |
| Table height | 720-760 |
| Seat height | 430-470 |
| Counter height | 850-900 |
| General walking path | 800-900 |

## Guardrails

- Do not claim that manual coordinate work is fully automatic design.
- Do not place unknown components without searching the registry first.
- Do not bypass `design_model.json` for project-backed component placement.
- Do not promise legal code compliance from ergonomic seed values.
- Do not describe placeholder boxes as final production assets.
- Treat snapshots and rendered images as advisory review artifacts.
- Do not mutate `design_model.json` directly from image pixels; record
  structured visual feedback actions first.
