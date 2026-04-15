---
description: Compose complex furniture and objects from foundation modeling tools (create_face, create_box, create_group)
---

# Geometry Composition Skill

## Overview

Layer 1 (foundation tools) combined with Layer 3 (composition patterns) can create **any** furniture or object. This skill provides building blocks and patterns - not an exhaustive object catalog.

**Key Principle**: Don't enumerate all possible objects. Give the LLM foundation tools + composition patterns, let it compose anything the user needs.

---

## Core Building Blocks

### create_face

Create flat surfaces from vertices. Use for:
- Custom polygon shapes (non-rectangular cushions)
- Angled surfaces (skinny tables, beveled edges)
- Curved approximations (multiple small faces)

```python
# Create a custom-shaped cushion face
create_face(
  vertices=[[0, 0, 0], [500, 0, 0], [500, 500, 0], [0, 500, 0]],
  material_id="fabric_gray",
  layer="Furniture"
)
```

### create_box

Create 3D rectangular volumes. Use for:
- Flat panels (tabletops, shelves, panels)
- Structural parts (legs, frames, supports)
- Volume objects (boxes, cabinets)

```python
# Create a tabletop: 1400x800x40mm
create_box(
  corner_x=0, corner_y=0, corner_z=730,
  width=1400, depth=800, height=40,
  material_id="wood_oak",
  layer="Furniture"
)
```

### create_group

Combine multiple entities into a single group for:
- Easy selection and manipulation
- Material inheritance (group takes material of first entity)
- Hierarchical organization

```python
# Group all table parts into one entity
create_group(
  entity_ids=["entity_leg_1", "entity_leg_2", "entity_leg_3", "entity_leg_4", "entity_top"],
  name="dining_table_1400x800"
)
```

### apply_material

Apply colors or textures to surfaces. Common hex colors:

| Material | Hex Color | Use Case |
|----------|-----------|----------|
| Oak wood | `#8B4513` | Dining tables, chairs |
| Walnut | `#5D432C` | Dark wood furniture |
| White fabric | `#F5F5F5` | Sofa cushions, chairs |
| Gray fabric | `#808080` | Modern sofas |
| Metal black | `#2A2A2A` | Table legs, frames |
| Metal silver | `#C0C0C0` | Modern legs |
| Glass | `#ADD8E6` | Tabletops, shelves |

```python
apply_material(
  entity_ids=["entity_001"],
  color="#8B4513"
)
```

---

## Composition Patterns

### Dining Table (1400x800x750mm)

```
Pattern: 桌面 + 桌腿 + 框架 (Tabletop + Legs + Frame)

1. Create 4 legs (create_box):
   - 80x80x720mm each
   - Positions: corners at [0,0], [1320,0], [0,720], [1320,720]
   - Material: metal_black

2. Create tabletop (create_box):
   - 1400x800x40mm
   - Position: height 730mm ( tabletop bottom = 750 - 20)
   - Material: wood_oak

3. Create apron/frame (create_box) - optional reinforcement:
   - 1400x800x20mm
   - Position: height 720mm (under tabletop)
   - Material: wood_oak

4. Group all (create_group): table_complete
```

### Chair

```
Pattern: 座垫 + 靠背 + 腿 (Seat + Backrest + Legs)

1. Create 4 legs (create_box):
   - 50x50x450mm
   - Positions at corners
   - Material: wood_walnut

2. Create seat cushion (create_box):
   - 500x500x80mm
   - Position: height 450mm
   - Material: fabric_gray

3. Create backrest (create_box):
   - 500x80x500mm
   - Position: at rear of seat, height 450-950mm
   - Material: fabric_gray

4. Optional armrests (create_box):
   - 50x400x150mm each side
   - Position: height 650mm
   - Material: wood_walnut

5. Group all: chair_complete
```

### Bookshelf (800x300x1800mm)

```
Pattern: 框架 + 隔板 (Frame + Shelves)

1. Create outer frame sides (create_box):
   - 30x300x1800mm left and right
   - Material: wood_oak

2. Create top and bottom panels (create_box):
   - 800x300x30mm top and bottom
   - Material: wood_oak

3. Create back panel (create_box):
   - 800x1800x10mm
   - Material: wood_oak

4. Create shelves (create_box) at heights:
   - [100, 400, 700, 1000, 1300, 1600]mm
   - Each: 740x280x25mm (slightly smaller than interior)
   - Material: wood_oak

5. Group all: bookshelf_800x300x1800
```

### Sofa (L-shaped: 2000x900 + 900x900)

```
Pattern: 底座 + 靠垫 + 扶手 (Base + Cushions + Armrests)

1. Create base section 1 (create_box):
   - 2000x900x400mm
   - Material: wood_frame

2. Create base section 2 (create_box) - perpendicular:
   - 900x900x400mm
   - Position: attached at end of section 1
   - Material: wood_frame

3. Create seat cushions (create_box):
   - 700x700x150mm (3 cushions for main section)
   - Position: on top of base at height 400mm
   - Material: fabric_gray

4. Create back cushions (create_box):
   - 700x200x500mm (3 cushions)
   - Position: height 400-900mm at rear
   - Material: fabric_gray

5. Create armrests (create_box):
   - 200x900x600mm each side
   - Position: height 400-1000mm
   - Material: fabric_darkgray

6. Group all: sofa_L_shaped
```

### Bed (Double: 2000x1600mm)

```
Pattern: 床垫 + 床架 + 床头板 + 床尾板 (Mattress + Frame + Headboard + Footboard)

1. Create bed frame (create_box):
   - 2100x1700x300mm
   - Position: floor level
   - Material: wood_walnut

2. Create mattress (create_box):
   - 2000x1600x200mm
   - Position: on frame, height 300mm
   - Material: fabric_white

3. Create headboard (create_box):
   - 2000x100x1200mm
   - Position: at head of bed, height 300-1500mm
   - Material: wood_walnut

4. Create footboard (create_box):
   - 2000x50x400mm
   - Position: at foot of bed, height 300-700mm
   - Material: wood_walnut

5. Create legs (create_box) - optional:
   - 100x100x100mm at each corner of frame
   - Material: wood_walnut

6. Group all: bed_double_2000x1600
```

### Coffee Table (1200x600x450mm)

```
Pattern: 桌面 + 腿 (Tabletop + Legs)

1. Create 4 tapered legs (create_box):
   - 60x60x430mm each
   - Position: at corners, height from floor to tabletop underside
   - Material: metal_black

2. Create glass tabletop (create_box):
   - 1200x600x20mm
   - Position: height 450mm
   - Material: glass_lightblue (with opacity 0.3)

3. Create lower shelf (create_box) - optional:
   - 1000x500x15mm
   - Position: height 150mm
   - Material: metal_black

4. Group all: coffee_table_1200x600
```

### TV Console (1800x400x500mm)

```
Pattern: 柜体 + 门 + 腿 (Cabinet + Doors + Legs)

1. Create main cabinet body (create_box):
   - 1800x400x480mm
   - Material: wood_white

2. Create doors (create_box) - 2 or 3 sections:
   - 600x400x20mm each
   - Position: front face of cabinet
   - Material: wood_white

3. Create legs (create_box):
   - 50x50x100mm at each corner
   - Material: metal_black

4. Group all: tv_console_1800x400x500
```

---

## Material Application Tips

### Applying Materials

```python
# Before grouping - apply to individual entities
apply_material(entity_ids=["entity_leg_1"], color="#5D432C")
apply_material(entity_ids=["entity_top"], color="#8B4513")

# Group inherits material from first entity
create_group(entity_ids=["entity_leg_1", "entity_leg_2", "entity_top"])
```

### Common Material Colors

| Object Part | Recommended Color |
|-------------|-------------------|
| Wood furniture frame | `#8B4513` (Oak), `#5D432C` (Walnut), `#DEB887` (Birch) |
| Fabric cushions | `#F5F5F5` (White), `#808080` (Gray), `#4A4A4A` (Charcoal) |
| Metal legs/frames | `#2A2A2A` (Black), `#C0C0C0` (Silver), `#B87333` (Copper) |
| Glass surfaces | `#ADD8E6` (Light blue), `#E0FFFF` (Pale cyan) |
| Leather | `#8B0000` (Dark red), `#2F2F2F` (Black), `#D2691E` (Tan) |

### Material Opacity

```python
# Solid materials
apply_material(entity_ids=["entity_001"], color="#8B4513")

# Glass/translucent
apply_material(entity_ids=["entity_glass"], color="#ADD8E6")
```

---

## Common Dimensions Reference

### Seating

| Object | Width | Depth | Height (total) | Seat Height |
|--------|-------|-------|----------------|-------------|
| Dining chair | 450-500 | 450-500 | 850-950 | 450-480 |
| Armchair | 800-900 | 800-900 | 800-900 | 400-450 |
| Sofa (3-seater) | 2200-2400 | 900-1000 | 850-900 | 400-450 |
| Sofa (2-seater) | 1600-1800 | 900-1000 | 850-900 | 400-450 |
| Office chair | 600-700 | 600-700 | 1100-1300 | 450-500 |
| Bar stool | 400-450 | 400-450 | 1000-1200 | 750-800 |

### Tables

| Object | Width | Depth | Height |
|--------|-------|-------|--------|
| Dining table (6-person) | 1800-2000 | 900-1000 | 750-760 |
| Dining table (4-person) | 1200-1400 | 700-900 | 750-760 |
| Coffee table | 1000-1400 | 500-700 | 400-500 |
| Side table | 400-600 | 400-600 | 500-650 |
| Desk | 1200-1600 | 600-800 | 720-750 |
| Console table | 1000-1500 | 300-400 | 800-900 |

### Storage

| Object | Width | Depth | Height |
|--------|-------|-------|--------|
| Bookshelf | 800-1000 | 300-350 | 1800-2200 |
| Wardrobe | 1500-2000 | 550-650 | 2000-2200 |
| TV console | 1500-2000 | 400-500 | 450-550 |
| Dresser | 1000-1400 | 450-550 | 800-1200 |
| Nightstand | 400-600 | 350-450 | 500-650 |
| Filing cabinet | 450-600 | 600-800 | 700-1400 |

### Bedroom

| Object | Width | Depth | Height |
|--------|-------|-------|--------|
| Bed (single) | 1000 | 2000 | 500-600 |
| Bed (double) | 1600 | 2000 | 500-600 |
| Bed (queen) | 1800 | 2000 | 500-600 |
| Bed (king) | 2000 | 2000 | 500-600 |
| Mattress (double) | 1400 | 1900 | 200-250 |

### Kitchen

| Object | Width | Depth | Height |
|--------|-------|-------|--------|
| Kitchen island | 1200-2000 | 600-1000 | 900-950 |
| Dining table (kitchen) | 1200-1800 | 700-900 | 750 |
| Bar counter | 1800-3000 | 400-600 | 1050-1100 |
| Kitchen stool | 350-400 | 350-400 | 900-1050 |

---

## Workflow for Unknown Objects

When user asks for something not in library or patterns:

### Step 1: Analyze the Object

Break down into geometric primitives:
- What 3D boxes/rectangles compose it?
- Are there flat faces for custom shapes?
- What materials/colors apply to each part?

### Step 2: Determine Dimensions

Based on typical proportions or user specifications:
- Ask user for specific dimensions if not provided
- Use common dimensions from reference table above
- Maintain realistic proportions

### Step 3: Create Individual Parts

```python
# Example: User wants "a custom planter box 600x300x400mm"

# 1. Create outer box
create_box(
  corner_x=0, corner_y=0, corner_z=0,
  width=600, depth=300, height=400,
  material_id="terracotta",
  layer="Decor"
)

# 2. Create inner hollow (another box slightly smaller, positioned inside)
create_box(
  corner_x=20, corner_y=20, corner_z=20,
  width=560, depth=260, height=380,
  material_id="soil",
  layer="Decor"
)
```

### Step 4: Apply Materials

```python
apply_material(entity_ids=["entity_planter_outer"], color="#CD853F")
apply_material(entity_ids=["entity_planter_inner"], color="#8B4513")
```

### Step 5: Group

```python
create_group(
  entity_ids=["entity_planter_outer", "entity_planter_inner"],
  name="planter_600x300x400"
)
```

### Step 6: Position

```python
# Move to desired location if not already correct
move_entity(
  entity_ids=["group_planter"],
  delta_x=1000, delta_y=2000, delta_z=0
)
```

---

## Tips for Realistic Results

### Chamfers and Bevels

For slightly angled edges (more realistic furniture):

```python
# Create a thin angled face for beveled edge
create_face(
  vertices=[[0, 0, 0], [10, 0, 0], [10, 500, 0], [0, 500, 10]],
  material_id="wood_oak",
  layer="Furniture"
)
```

### Group Organization

```python
# Always group related geometry
# This makes selection and manipulation easier
create_group(
  entity_ids=["entity_seat", "entity_back", "entity_legs_left", "entity_legs_right"],
  name="chair_simple"
)

# Nested groups for complex objects
create_group(
  entity_ids=["group_seat_cushion", "group_backrest", "group_base"],
  name="sofa_complete"
)
```

### Material Application Order

```python
# Apply materials BEFORE grouping for cleaner inheritance
apply_material(entity_ids=["entity_top"], color="#8B4513")
apply_material(entity_ids=["entity_leg_1"], color="#2A2A2A")
apply_material(entity_ids=["entity_leg_2"], color="#2A2A2A")

# Group after materials applied
create_group(entity_ids=["entity_top", "entity_leg_1", "entity_leg_2"])
```

### Complex Curves

Approximate curves with multiple flat faces:

```python
# Round table top approximated with octagon
create_face(
  vertices=[
    [0, 0, 0], [200, 0, 0], [400, 200, 0],
    [400, 400, 0], [200, 600, 0], [0, 600, 0],
    [-200, 400, 0], [-200, 200, 0]
  ],
  material_id="wood_oak"
)
```

### Stacking and Alignment

Always verify stacking order:
```python
# Tabletop should be ABOVE legs (higher Z)
# Seat cushion should be ABOVE chair base

# If parts overlap, later created entities render on top
# Use correct corner_z positioning to control visual stacking
```

---

## Summary: Composition Decision Tree

```
User asks for object
         |
         v
Is object in component library?
    |yes|         |no|
    v              v
place_component   Break down into primitives
                  (boxes, faces)
         |              |
         v              v
         |        Determine dimensions
         |        (from user or typical sizes)
         |              |
         v              v
         |        Create each part
         |        (create_box, create_face)
         |              |
         v              v
         |        Apply materials
         |        (apply_material)
         |              |
         v              v
         |        Group parts
         |        (create_group)
         |              |
         v              v
         |        Position in model
         |        (move_entity if needed)
         |
         v
    Done
```

