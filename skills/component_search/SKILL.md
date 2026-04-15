# Component Search Skill

## Purpose

Guide LLM through searching and placing 3D components from various sources.

## Component Sources

| Source | Access Method | Use Case |
|--------|--------------|----------|
| Local Library | `place_component` | User's custom .skp files |
| Sketchfab | `search_sketchfab_models` | CC licensed models |
| SketchUp 3D Warehouse | `search_warehouse` (future) | Official SU models |

## Local Library Workflow

### 1. Search Local Library
```python
# Components are defined in mcp_server/assets/library.json
# LLM can read this file directly to find components
```

### 2. Place from Library
```python
# "Place a modern double sofa from the library"
place_component(
    component_name="现代双人沙发",
    position_x=3000, position_y=2000, position_z=0
)
```

### Local Library Structure
```
SKETCHUP_ASSETS/
├── furniture/
│   ├── sofa_modern_double.skp
│   ├── dining_table_rect.skp
│   └── bed_double.skp
├── fixtures/
│   └── lamp_floor.skp
├── lighting/
│   ├── spotlight.skp
│   ├── chandelier.skp
│   └── floor_lamp.skp
└── structural/
    └── column.skp
```

## Sketchfab Workflow

### 1. Search
```python
# "Find a modern grey sofa on Sketchfab"
results = search_sketchfab_models(
    query="modern grey sofa",
    count=10,
    sort="likes"  # Options: relevance, newest, likes, views
)
```

### 2. Review Results
```python
# Results include:
# - name: Model name
# - view_count: Popularity indicator
# - like_count: User preference
# - description: Model details
# - download_format: Available formats (obj, gltf, etc)
```

### 3. Download
```python
# "Download the top result as OBJ"
download_sketchfab_model(
    model_uid="abc123...",  # From search results
    format_hint="obj"  # Best for SketchUp
)
```

### 4. Import to SketchUp
```
# After download, user must manually:
# 1. Open SketchUp
# 2. File > Import
# 3. Select downloaded .obj file
# 4. Position the imported model
```

### 5. Position (Manual)
```python
# Once imported, LLM can help position:
move_entity(entity_ids=["entity_imported_001"], delta_x=1000, delta_y=0, delta_z=0)
```

## Search Decision Tree

```
User Request: "Add a [type] to [location]"
    │
    ├─► Check local library
    │       └─► Found → place_component
    │
    ├─► Not found → Check Sketchfab
    │       └─► Found → download → inform user to import
    │
    └─► Not found → Compose using geometry_composition
            └─► Create from primitives
```

## Example Workflows

### Adding a Known Furniture Piece
```
User: "Add a北欧风格餐桌 to the dining room"

1. Search local library for "北欧风格餐桌" or "dining table"
2. Found "dining_table_rect" → place_component
3. Update design_model.json
4. Confirm placement
```

### Adding an Unknown Piece
```
User: "Add a vintage brass floor lamp next to the sofa"

1. Search local library → Not found
2. Search Sketchfab: search_sketchfab_models("vintage brass floor lamp")
3. Found several options, download top result
4. Inform user: "Please import the downloaded model into SketchUp"
5. After import, help position with move_entity
```

### Creating Custom Piece
```
User: "Create an L-shaped sofa that's not in the library"

1. Check library → Not found
2. Check Sketchfab → May have L-shaped sofa
   - If found → download and import
   - If not found → use geometry_composition skill
3. Compose L-shape from boxes and faces
```

## Component Metadata

When adding new components to local library:

```json
{
  "id": "dining_table_oak_1400x800",
  "name": "Oak Dining Table 1400x800",
  "name_en": "Oak Dining Table",
  "category": "furniture",
  "skp_path": "${SKETCHUP_ASSETS}/furniture/dining_table_oak.skp",
  "default_dimensions": {
    "width": 1400,
    "depth": 800,
    "height": 750
  },
  "insertion_point": {
    "description": "Center of table",
    "offset": [0, 0, 0],
    "face_direction": "+y"
  },
  "bounds": {
    "min": [0, 0, 0],
    "max": [1400, 800, 750]
  },
  "style_tags": ["nordic", "oak", "dining"]
}
```

## Sketchfab Search Tips

### Good Queries
- `"modern grey sofa"` - Specific color + type
- `"scandinavian dining chair"` - Style + item
- `"floor lamp brass"` - Material + item
- `"minimalist coffee table"` - Style + item

### Poor Queries
- `"stuff for living room"` - Too vague
- `"nice"` - No useful criteria
- `"3d model"` - No specific item

### Filtering by Format
```python
# Only OBJ models (best for SketchUp)
search_sketchfab_models(query="sofa", format="obj")
```

## Post-Import Checklist

After user imports Sketchfab model:

1. ✅ Verify entity created in SketchUp
2. ✅ Get entity ID
3. ✅ Position using semantic rules
4. ✅ Apply appropriate material
5. ✅ Add to design_model.json
6. ✅ Set layer (Furniture, Lighting, etc)
