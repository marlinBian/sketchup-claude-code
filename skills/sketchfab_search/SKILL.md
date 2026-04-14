---
description: Search Sketchfab for 3D models and download them for use in SketchUp
---

# Sketchfab 3D Model Search

Search Sketchfab's library of Creative Commons licensed 3D models to find furniture, fixtures, and decorative objects for interior design.

## How to Use

### Step 1: Search for Models

When the user wants to find a 3D model:

```
search_sketchfab_models(query: "modern sofa", count: 10)
search_sketchfab_models(query: "floor lamp", count: 5)
search_sketchfab_models(query: "potted plant", count: 8)
```

### Step 2: Review Results

The search returns:
- Model name and description
- Download availability
- Like and view counts
- Direct links to view on Sketchfab

### Step 3: Download the Model

When user selects a model:

```
download_sketchfab_model(model_uid: "<uid_from_search>", format_hint: "obj")
```

### Step 4: Import into SketchUp

After download, models can be imported into SketchUp using File > Import.

## Example Workflows

### Adding a Sofa

User: "Add a modern gray sofa to the living room"

1. First search: `search_sketchfab_models(query: "modern gray sofa")`
2. Review results and pick one
3. Download: `download_sketchfab_model(model_uid: "xxx", format_hint: "obj")`
4. Place manually in SketchUp or use `place_component` if it's in the library

### Adding a Floor Lamp

User: "I need a floor lamp next to the sofa"

1. Search: `search_sketchfab_models(query: "floor lamp minimalist")`
2. Download the top result
3. Import into SketchUp

## Supported Search Queries

| Category | Example Queries |
|----------|-----------------|
| Seating | "sofa", "armchair", "dining chair", "office chair" |
| Tables | "coffee table", "dining table", "side table", "desk" |
| Lighting | "floor lamp", "pendant light", "table lamp", "chandelier" |
| Storage | "bookshelf", "wardrobe", "cabinet", "shelving" |
| Decor | "potted plant", "rug", "mirror", "wall art" |
| Bedroom | "bed", "nightstand", "dresser", "wardrobe" |
| Kitchen | "dining table", "stool", "kitchen island" |
| Bathroom | "vanity", "bathtub", "toilet", "shower" |

## Tips

- Use specific queries for better results: "mid-century modern sofa" vs just "sofa"
-OBJ format is recommended for SketchUp compatibility
- Models must be Creative Commons licensed to be downloadable
- Check the model polygon count for performance in SketchUp
