---
description: Compose simple placeholder geometry from supported modeling tools.
---

# Geometry Composition Skill

## Purpose

Create simple placeholder geometry when the component registry does not contain
the requested object, or when the designer explicitly wants a massing model
instead of a detailed asset.

## Supported Building Blocks

- `create_box` for rectangular volumes.
- `create_face` for flat surfaces.
- `apply_material` for simple colors.
- `move_entity`, `rotate_entity`, `scale_entity`, and `copy_entity` for edits.

Use detailed component placement when a registry asset exists. Use geometry
composition for placeholders, test volumes, and simple built-ins.

## Workflow

1. Confirm the object can be represented with simple geometry.
2. Choose millimeter dimensions from the user, registry, or ergonomic defaults.
3. Create the smallest number of primitives needed.
4. Apply a simple material if useful.
5. Report that the result is a placeholder when it is not a real asset.

## Example

Create a basic vanity placeholder:

```python
create_box(
    corner_x=400,
    corner_y=0,
    corner_z=0,
    width=600,
    depth=460,
    height=850,
    layer="Fixtures"
)
apply_material(entity_ids=["entity_vanity_001"], color="#F5F0E8")
```

## Guardrails

- Do not describe composed boxes as production-ready furniture models.
- Do not create complex assets when the packaged registry has a better match.
- Do not skip placement validation for large placeholder volumes.
- Do not write Chinese into code identifiers or entity names by default.
