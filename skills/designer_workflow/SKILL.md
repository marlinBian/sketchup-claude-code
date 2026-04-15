# Designer Workflow Skill

## Purpose

Guide LLM through standard interior design workflows, from empty model to complete design.

## Workflow Stages

### Stage 1: Project Setup
```
1. Create/open project
2. Initialize design_model.json
3. Set project metadata (style, dimensions)
```

### Stage 2: Space Definition
```
1. Create outer walls (create_wall)
2. Define rooms/spaces in design_model.json
3. Set layer conventions
```

### Stage 3: Structural Elements
```
1. Interior walls (create_wall)
2. Doors (create_door)
3. Windows (create_window)
4. Stairs if multi-level (create_stairs)
```

### Stage 4: Electrical & Lighting
```
1. Place lighting fixtures (place_lighting)
2. Add switches (semantic positioning)
```

### Stage 5: Furniture Layout
```
1. Place major furniture (place_component)
2. Position using semantic relationships
3. Apply furniture materials
```

### Stage 6: Decor & Finishes
```
1. Apply wall colors/materials (apply_style)
2. Add rugs, curtains, accessories
3. Place decorative lighting
```

### Stage 7: Review & Export
```
1. Capture snapshots from multiple views
2. Export to glTF/IFC
3. Save version
```

## Decision Tree

```
User Request
    │
    ├─► "Create a new room"
    │       → Define space bounds
    │       → Create walls
    │       → Update design_model.json
    │
    ├─► "Add [furniture type]"
    │       → Search component library
    │       → Find or create component
    │       → Semantic positioning
    │       → Update design_model.json
    │
    ├─► "Move [object] to [position]"
    │       → Calculate new position
    │       → move_entity
    │       → Update design_model.json
    │
    ├─► "Change style to [style]"
    │       → apply_style
    │       → Update design_model.json metadata
    │
    ├─► "Add lighting"
    │       → Determine light type
    │       → Semantic positioning
    │       → Update design_model.json
    │
    └─► "Export my design"
            → Capture snapshots
            → Export glTF/IFC
            → Save version
```

## Common Commands

### Room Creation
```
create_room(name: "living_room", width: 6000, depth: 4000, height: 2800)
```

### Furniture Placement
```
place_near(furniture: "sofa", reference: "tv", distance: 1500, facing: "tv")
place_above(furniture: "pendant_light", reference: "dining_table", height: 1200)
```

### Style Application
```
apply_style("scandinavian")
apply_material(entity_ids: [...], color: "#8B4513")
```

## Layer Conventions

| Layer | Contents |
|-------|----------|
| Walls | create_wall, create_door, create_window |
| Furniture | place_component, create_group |
| Lighting | place_lighting |
| Fixtures | place_component (bathroom, kitchen) |
| Materials | apply_material, apply_style |
| Annotations | (future) measurements, labels |

## Error Handling

| Error | Recovery |
|-------|----------|
| Component not found in library | Compose using geometry_composition skill |
| Position collision | Find nearest valid position, warn user |
| Material not found | Use default material, log warning |
| Invalid semantic reference | Calculate absolute position, inform user |

## Validation Rules

Before executing:
1. Check component exists in library or can be composed
2. Verify position is within project bounds
3. Check for collisions with existing components
4. Validate layer exists

After execution:
1. Confirm entity created in SketchUp
2. Update design_model.json
3. Return confirmation with spatial info
