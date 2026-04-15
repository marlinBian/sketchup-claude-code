# Semantic Positioning Skill

## Purpose

Enable LLM to position objects using **semantic relationships** rather than raw coordinates. Example: "lamp above dining table" instead of "position: [3000, 2000, 1950]".

## Core Concept

Every furniture piece can define **semantic anchors** - named points that other objects can reference.

```json
{
  "dining_table_001": {
    "semantic_anchor": "dining_table_center",
    "position": [3000, 2000, 0],
    "dimensions": {"width": 1400, "depth": 800}
  }
}
```

## Relationship Types

### 1. Above / Below
```python
# "Place a pendant light 1.2m above the dining table"
lamp_position = dining_table_center + [0, 0, 1200]
```

### 2. Left / Right / Front / Back
```python
# "Place a floor lamp to the left of the sofa"
sofa_left = sofa_position.x - (sofa_width/2 + lamp_clearance)
lamp_position = [sofa_left, sofa_position.y, 0]
```

### 3. Centered On
```python
# "Center the rug on the living room"
room_center = [(room_min.x + room_max.x)/2, (room_min.y + room_max.y)/2, 0]
rug_position = room_center
```

### 4. Facing
```python
# "Face the sofa towards the TV"
facing_vector = tv_position - sofa_position
sofa_rotation = atan2(facing_vector.x, facing_vector.y)
```

### 5. Aligned With
```python
# "Align the painting with the center of the sofa"
painting_position.x = sofa_center.x  # Same X
painting_position.y = wall_center.y   # On the wall
```

### 6. Distance From
```python
# "Place the chair 800mm from the dining table"
table_edge = table_position.x + table_width/2
chair_x = table_edge + 800 + chair_width/2
```

## Standard Clearances (mm)

| Relationship | Clearance |
|-------------|-----------|
| Chair to table | 600 |
| Sofa to coffee table | 400 |
| Walking path | 800 |
| Door swing | 900 |
| TV to seating | 1500-2000 |
| Pendant light above table | 1200-1500 |
| Wall lamp beside bed | 1500 (height) |

## Usage in LLM Workflow

```
User: "Add a floor lamp next to the sofa on the left side"

1. Read design_model.json
2. Find sofa_001
3. Calculate "left side":
   - sofa_left_x = sofa.position.x - sofa.width/2
   - lamp_x = sofa_left_x - lamp.clearance - lamp.width/2
   - lamp_y = sofa.position.y
4. Create component with calculated position
5. Update design_model.json with relative_to reference
```

## Semantic Anchor Naming

Use descriptive names:

| Object | Anchor | Meaning |
|--------|--------|---------|
| Dining table | `dining_table_center` | Center of table top |
| Sofa | `sofa_center` | Center of sofa |
| Sofa | `sofa_back_edge` | Back edge of sofa |
| Bed | `bed_headboard` | Top edge (headboard side) |
| Desk | `desk_center` | Center of desk |
| Window | `window_center` | Center of window glass |

## Code Templates

### Python Implementation
```python
def resolve_position(relationship: dict, design_model: dict) -> list:
    """Resolve a semantic position to absolute coordinates."""
    rel_type = relationship["type"]

    if rel_type == "above":
        anchor_pos = find_anchor(relationship["anchor"], design_model)
        return add(anchor_pos, [0, 0, relationship["height_offset"]])

    elif rel_type == "left_of":
        ref_pos = get_component_position(relationship["reference"], design_model)
        ref_width = get_component_width(relationship["reference"], design_model)
        offset = relationship.get("clearance", 600)
        return [ref_pos[0] - ref_width/2 - offset, ref_pos[1], ref_pos[2]]

    elif rel_type == "centered_on":
        space = get_space(relationship["space"], design_model)
        return center_of_bounds(space["bounds"])

    # ... other types
```

### LLM Prompt Template
```
To place "{object}" using semantic positioning:

1. Find reference object in design_model.json
2. Determine relationship type (above/left_of/centered_on/etc)
3. Look up standard clearances from this skill
4. Calculate absolute position
5. Create component with position
6. Add relative_to to design_model.json
```

## Common Patterns

### Dining Room
- Pendant light: `above dining_table_center, height=1200-1500mm`
- Area rug: `centered_on dining_area`
- Chairs: `around dining_table, spacing=600mm`

### Living Room
- Coffee table: `in_front_of sofa, distance=400mm`
- Floor lamp: `left_of or right_of sofa`
- TV: `facing sofa, distance=1500-2000mm`

### Bedroom
- Nightstand: `left_of or right_of bed, distance=600mm`
- Lamp on nightstand: `above nightstand, height=600mm`
- Mirror: `above dresser or on wall opposite bed`

### Bathroom
- Mirror: `above vanity, height=1500mm from floor`
- Towel bar: `beside bathtub or shower`
