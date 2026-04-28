# Spatial Validation Skill

## Purpose

Check whether a proposed layout is plausible before executing SketchUp changes.
Current validation is ergonomic and geometric, not legal code compliance.

## Preferred Validation Paths

For the supported bathroom slice, use:

```python
plan_bathroom(project_path="<project-path>")
```

The returned `validation_report` is the most reliable current validation output.

For generic placement, combine:

- `get_project_state` for the current `design_model.json`, effective design
  rules, asset-lock summary, and visual feedback summary
- `validate_project_layout` for project-backed containment, physical overlap,
  and simple front-clearance checks
- `get_design_rules` for project-specific rules
- `search_components` or `get_component_manifest` for registry dimensions and
  clearances
- scene information from `get_scene_info`

## Generic Checklist

Before placement:

1. Search the registry and read component dimensions.
2. Identify the target room or wall from `get_project_state`.
3. Calculate proposed bounds in millimeters.
4. Check minimum clearances from `get_design_rules`.
5. Use `validate_project_layout` after project-backed placement.
6. Use `validate_design_project` to catch project file, asset lock, runtime
   skill, layout, and execution-trace problems.
7. Use `get_scene_info` when SketchUp state may differ from files.
8. Report assumptions when validation is only approximate.

## Project Layout Validation

```python
validate_project_layout(project_path="<project-path>")
```

This checks:

- component bounds are inside their linked or inferred rectangular space
- component 3D bounds do not physically overlap within the same space
- wall-backed components with `clearance.front` have enough front space

It is deterministic and headless. It does not prove full collision-free design,
door-swing code compliance, circulation analysis, or jurisdictional compliance.

## Typical Ergonomic Seeds

| Item | Minimum Millimeters |
| --- | ---: |
| General walking path | 800 |
| Bathroom fixture front clearance | 600 |
| Toilet side clearance | 250 |
| Door swing avoidance | 700 |
| Chair pull-out zone | 600 |

## Failure Reporting

If validation fails, return:

```json
{
  "valid": false,
  "issue": "front clearance is below the configured minimum",
  "required_mm": 600,
  "actual_mm": 420,
  "suggestion": "move the vanity 180 mm east"
}
```

## Guardrails

- Do not claim jurisdictional compliance from seed validation rules.
- Do not hide validation failures behind a successful SketchUp operation.
- Do not mutate SketchUp when a clearance conflict is known and avoidable.
- Keep visual renders separate from validation evidence.
