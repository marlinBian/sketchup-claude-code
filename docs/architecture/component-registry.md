# Component Registry

The component registry is not a model download website. It is a machine-readable
index that lets an agent understand, place, validate, and cite 3D components.

## Minimum Component Manifest

Each component entry should eventually provide:

```json
{
  "id": "toilet_floor_mounted_basic",
  "name": "Basic floor mounted toilet",
  "category": "fixture",
  "subcategory": "toilet",
  "dimensions": {
    "width": 380,
    "depth": 700,
    "height": 760
  },
  "bounds": {
    "min": [0, 0, 0],
    "max": [380, 700, 760]
  },
  "insertion_point": {
    "offset": [190, 0, 0],
    "description": "Back center on floor"
  },
  "anchors": {
    "back": "wall",
    "bottom": "floor"
  },
  "clearance": {
    "front": 600,
    "left": 250,
    "right": 250
  },
  "placement_rules": [
    "back_against_wall",
    "floor_mounted"
  ],
  "assets": {
    "skp_path": "${SKETCHUP_ASSETS}/fixtures/toilet_floor_mounted_basic.skp",
    "thumbnail": "${SKETCHUP_ASSETS}/thumbnails/toilet_floor_mounted_basic.png",
    "procedural_fallback": "box_fixture"
  },
  "license": {
    "type": "unknown",
    "source": "seed",
    "redistribution": "Placeholder metadata for procedural seed geometry."
  },
  "aliases": {
    "en": ["toilet", "water closet"],
    "zh-CN": ["马桶", "坐便器"]
  }
}
```

The canonical `name` field is English. Localized display strings and search
terms belong in `aliases` or a later explicit localization structure.

The packaged seed library lives at `mcp_server/mcp_server/assets/library.json`.
The older root-level `mcp_server/assets/library.json` path is not canonical.

## First Milestone

The first useful registry should support only a small bathroom scenario:

- door
- wall-mounted or floor-mounted toilet
- vanity or sink
- mirror
- basic light

This is enough to validate component search, placement, clearance rules, and
SketchUp synchronization without building a large asset marketplace.
