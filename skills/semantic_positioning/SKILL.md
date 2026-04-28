# Semantic Positioning Skill

## Purpose

Convert designer language such as "against the north wall" or "above the
vanity" into millimeter coordinates before calling placement tools.

## Inputs

Use the best available source, in this order:

1. `design_model.json` from the active project.
2. Registry metadata from `search_local_library`.
3. Scene state from `get_scene_info`.
4. Explicit dimensions supplied by the user.

If none of these sources provide enough geometry, ask one clarification question
or use a clearly labeled placeholder.

## Supported Relationships

| Relationship | Calculation Basis |
| --- | --- |
| `centered_in_room` | Center of room bounds |
| `against_wall` | Wall line, component depth, wall side |
| `above` | Reference anchor plus vertical offset |
| `beside` | Reference bounds plus clearance |
| `in_front_of` | Reference facing direction plus clearance |
| `aligned_with` | Shared x, y, or z coordinate |

## Workflow

1. Identify the target object and reference object or space.
2. Read dimensions, anchors, and clearances.
3. Convert the relationship into absolute coordinates.
4. Check fit using `design_rules.json` or registry clearances.
5. Call `place_component`, `create_box`, or another concrete tool.
6. Report assumptions and validation warnings.

## Example

```python
search_local_library(query="mirror", category="fixtures", limit=5)
place_component(
    component_name="Basic Wall Mirror 500",
    position_x=1200,
    position_y=0,
    position_z=1400,
    rotation=0,
    scale=1
)
```

## Guardrails

- Do not rely on semantic words without checking actual dimensions.
- Do not pretend generic semantic placement is collision-free.
- Do not overwrite `design_model.json` with unverified geometry.
- Prefer `plan_bathroom` for the supported bathroom slice.
