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

## Supported Tool Groups

Scene and geometry:

- `get_scene_info`
- `get_selection_info`
- `create_wall`
- `create_face`
- `create_box`
- `create_door`
- `create_window`
- `create_stairs`

Components and layout:

- `search_components`
- `get_component_manifest`
- `register_project_component`
- `register_selected_component`
- `add_component_instance`
- `execute_component_instance`
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
- `record_visual_feedback`
- `list_visual_feedback`
- `update_visual_feedback_action_status`
- `generate_report`
- `save_version`
- `list_versions`

## Common Flows

### Place a Registry Component

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
