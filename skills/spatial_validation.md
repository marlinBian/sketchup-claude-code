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

- `design_model.json`
- `design_rules.json`
- component dimensions and clearances from the registry
- scene information from `get_scene_info`

## Generic Checklist

Before placement:

1. Search the registry and read component dimensions.
2. Identify the target room or wall from `design_model.json`.
3. Calculate proposed bounds in millimeters.
4. Check minimum clearances from `design_rules.json`.
5. Use `get_scene_info` when SketchUp state may differ from files.
6. Report assumptions when validation is only approximate.

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
