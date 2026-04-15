# Common Operations Skill

## Purpose

Quick reference for frequent design operations that designers request.

## Operations by Category

### Furniture Placement

#### Place a Sofa
```python
# "Place a modern grey sofa against the north wall"
place_component(
    component_name="sofa",
    position_x=3000, position_y=4000, position_z=0,
    rotation=180  # Facing south
)
```

#### Place a Dining Table
```python
# "Center a dining table in the dining area"
place_component(
    component_name="dining_table",
    position_x=3000, position_y=2000, position_z=0,
    rotation=0
)
```

#### Place a Bed
```python
# "Add a double bed to the master bedroom"
place_component(
    component_name="bed_double",
    position_x=8000, position_y=2000, position_z=0,
    rotation=90  # Headboard on left
)
```

### Lighting

#### Pendant Light Above Table
```python
# "Hang a pendant light 1.2m above the dining table"
# First, get table position from design_model.json
# Then:
place_lighting(
    lighting_type="chandelier",
    position_x=3000, position_y=2000, position_z=1950,  # 750(table) + 1200(above)
    mount_height=1950
)
```

#### Floor Lamp Beside Sofa
```python
# "Add a floor lamp to the left of the sofa"
# Position: sofa.left_x - lamp_clearance
place_lighting(
    lighting_type="floor_lamp",
    position_x=500, position_y=2000, position_z=0
)
```

#### Recessed Spotlights
```python
# "Add 4 recessed spotlights in the ceiling"
positions = [
    [2000, 2000, 2800],
    [4000, 2000, 2800],
    [2000, 3000, 2800],
    [4000, 3000, 2800]
]
for pos in positions:
    place_lighting(
        lighting_type="spotlight",
        position_x=pos[0], position_y=pos[1], position_z=pos[2],
        ceiling_height=2800
    )
```

### Doors & Windows

#### Add a Door to a Wall
```python
# "Add a 900mm wide door on the east wall"
create_door(
    wall_id="entity_wall_001",
    position_x=2000, position_y=0,
    width=900,
    height=2100,
    swing_direction="left"
)
```

#### Add Windows
```python
# "Add a 1.2m x 1m window on the south wall, 900mm from floor"
create_window(
    wall_id="entity_wall_002",
    position_x=1500, position_y=0,
    width=1200,
    height=1000,
    sill_height=900
)
```

### Materials & Style

#### Apply Style to Room
```python
# "Apply Scandinavian style to the living room"
apply_style(style_name="scandinavian")
```

#### Apply Material to Entity
```python
# "Make the floor oak wood"
apply_material(
    entity_ids=["entity_floor_001"],
    color="#C4A77D"
)
```

### Layout Modifications

#### Move Furniture
```python
# "Move the sofa 500mm to the left"
move_entity(
    entity_ids=["entity_sofa_001"],
    delta_x=-500, delta_y=0, delta_z=0
)
```

#### Rotate Furniture
```python
# "Rotate the armchair to face the TV"
rotate_entity(
    entity_ids=["entity_chair_001"],
    center_x=5000, center_y=2000, center_z=0,
    axis="z",
    angle=45
)
```

#### Copy Furniture
```python
# "Add 4 matching chairs around the dining table"
chair_positions = [
    [2000, 2000, 0],   # Top
    [4000, 2000, 0],   # Bottom
    [3000, 1200, 0],   # Left
    [3000, 2800, 0]    # Right
]
for pos in chair_positions:
    copy_entity(
        entity_ids=["entity_chair_template"],
        delta_x=pos[0]-3000, delta_y=pos[1]-2000, delta_z=0
    )
```

### Space Creation

#### Create a Room with Walls
```python
# "Create a 6m x 4m living room"
width, depth, height = 6000, 4000, 2800
# South wall
create_wall(start_x=0, start_y=0, start_z=0, end_x=width, end_y=0, end_z=0, height=height, thickness=200)
# East wall
create_wall(start_x=width, start_y=0, start_z=0, end_x=width, end_y=depth, end_z=0, height=height, thickness=200)
# North wall
create_wall(start_x=width, start_y=depth, start_z=0, end_x=0, end_y=depth, end_z=0, height=height, thickness=200)
# West wall
create_wall(start_x=0, start_y=depth, start_z=0, end_x=0, end_y=0, end_z=0, height=height, thickness=200)
```

### Export & Documentation

#### Capture View
```python
# "Take a bird's eye photo of the living room"
capture_design(
    output_path="/designs/project/snapshot_living_room_birdseye.png",
    view_preset="living_room_birdseye"
)
```

#### Export for Client
```python
# "Export the design as glTF"
export_gltf(output_path="/designs/project/model.gltf", include_textures=True)
```

## Common Conversions

| Real World | Millimeters |
|-----------|-------------|
| 1 meter | 1000 mm |
| 1 centimeter | 10 mm |
| 1 foot | 304.8 mm |
| 1 inch | 25.4 mm |
| Door width | 800-900 mm |
| Door height | 2000-2100 mm |
| Window width | 600-1800 mm |
| Window height | 600-1500 mm |
| Table height | 750 mm |
| Chair seat | 450 mm |
| Sofa height | 850 mm |
| Counter height | 900 mm |

## Typical Clearances

| Application | Clearance |
|------------|-----------|
| Walking path | 800 mm |
| Chair behind table | 600 mm |
| Sofa to coffee table | 400 mm |
| Bed to nightstand | 600 mm |
| TV to seating | 1500-2000 mm |

## Error Recovery

| Error | Recovery |
|-------|----------|
| Component not found | Use `create_box` as temporary or search library |
| Position collision | Move existing item or choose alternative position |
| Invalid wall | Create new wall first |
