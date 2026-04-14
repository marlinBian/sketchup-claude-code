# Spatial Validation Skill

## Purpose

Validate furniture placement before executing to prevent collisions and ensure proper clearance distances.

## When to Use

Use this skill when the user requests:
- "Place a [sofa/chair/table] in [location]"
- "Move [furniture] to [position]"
- "Put the [item] against the [wall/side]"
- Any placement that could cause spatial conflicts

## Pre-Placement Validation Checklist

Before calling `place_component`, Claude should:

1. **Call `get_scene_info`** to get current scene state:
   - Existing entity positions
   - Wall locations
   - Room boundaries

2. **Calculate target bounds** for new component:
   - Use component's `bounds` from `library.json`
   - Account for rotation
   - Add clearance buffer

3. **Check for collisions** with:
   - Walls (use wall bounding boxes)
   - Existing furniture (from scene info)
   - Room boundaries

4. **Verify clearances**:
   - Minimum 600mm between furniture
   - 900mm clearance for doors
   - 800mm walkway width

## Collision Detection Algorithm

```python
def check_collision(new_bounds, existing_entities, min_clearance=600):
    """Check AABB collision with clearance buffer."""
    for entity in existing_entities:
        # Expand entity bounds by clearance
        ent_min = entity.bounds.min
        ent_max = entity.bounds.max

        # Check overlap (with clearance subtracted)
        if (new_bounds.min.x - min_clearance < ent_max.x and
            new_bounds.max.x + min_clearance > ent_min.x and
            new_bounds.min.y - min_clearance < ent_max.y and
            new_bounds.max.y + min_clearance > ent_min.y and
            new_bounds.min.z < ent_max.z and
            new_bounds.max.z > ent_min.z):
            return True, entity
    return False, None
```

## Wall Alignment Logic

For "place against [direction] wall" commands:

### Identifying Wall Direction
- **North wall**: y is at maximum (high y values)
- **South wall**: y is at minimum (low y values)
- **East wall**: x is at maximum (high x values)
- **West wall**: x is at minimum (low x values)

### Alignment Offset Calculation
```python
def align_to_wall(wall_info, component_bounds, alignment="inner"):
    # wall_info: {start: [x1,y1,z1], end: [x2,y2,z2], thickness: t}
    # alignment: "inner" (贴墙), "outer" (离墙), "center" (居中)

    # Calculate perpendicular offset from wall centerline
    offset = thickness / 2  # for center alignment
    if alignment == "inner":
        offset = thickness
    elif alignment == "outer":
        offset = 0

    # Position = wall_start + perpendicular_offset
    return position
```

## Example Validation Flow

```
User: "将餐桌贴着北墙放置"

1. Get scene info
   → Returns walls, entities, bounds

2. Find north wall
   → Wall at y=5000mm (for example)

3. Get dining_table dimensions from library.json
   → width=1600, depth=800

4. Calculate position
   → North wall at y=5000
   → Table depth=800
   → Inner alignment: y = 5000 - 800/2 = 4600

5. Check collision with existing entities
   → No collision detected

6. Place component at [1600, 4600, 0] with rotation=0
```

## Error Responses

If validation fails, return:
```json
{
  "valid": false,
  "error": "Collision detected with entity ent_123",
  "suggestion": "Move table 600mm to the east",
  "alternative_positions": [
    {"position": [2200, 4600, 0], "rotation": 0},
    {"position": [1600, 4000, 0], "rotation": 0}
  ]
}
```

## Clearance Constants

| Type | Minimum Clearance |
|------|-------------------|
| General furniture | 600mm |
| Door swing | 900mm |
| Walkway | 800mm |
| Seating (chair pull-out) | 1000mm |
| TV to seating | 2000mm |

## Skill Usage in Claude

```markdown
When placing furniture:
1. Load component bounds from library.json
2. Call get_scene_info to check existing entities
3. Calculate target position based on wall alignment
4. Run collision detection
5. If valid: proceed with place_component
6. If invalid: suggest alternatives
```
