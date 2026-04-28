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

## Project Asset Lock

Each designer project gets an `assets.lock.json` file. It records the registry
components actually referenced by that project, not the entire packaged library.

The lock shape is:

```json
{
  "version": "1.0",
  "cache": {
    "root": "assets/components",
    "mode": "on_demand"
  },
  "assets": [
    {
      "component_id": "toilet_floor_mounted_basic",
      "component_name": "Basic floor mounted toilet",
      "category": "fixture",
      "used_by": ["toilet_001"],
      "source": {
        "kind": "seed",
        "license": "unknown",
        "redistribution": "Placeholder metadata for procedural seed geometry."
      },
      "paths": {
        "skp": "${SKETCHUP_ASSETS}/fixtures/toilet_floor_mounted_basic.skp"
      },
      "cache": {
        "status": "referenced",
        "path": "assets/components/toilet_floor_mounted_basic.skp"
      },
      "procedural_fallback": "box_fixture"
    }
  ]
}
```

`assets/components/` is the project-local cache root. The current implementation
defines the cache contract and writes the directory during project
initialization; it does not yet download external assets automatically.

## Search Ranking

Search should prefer exact component IDs, names, and aliases before fuzzy or
tag-only matches. Category filters use canonical manifest category names such as
`fixture`, but plural user input such as `fixtures` is normalized for CLI use.

Agents should use machine-readable registry tools for reasoning:

- `search_components` returns matching component manifests with dimensions,
  anchors, clearance data, asset metadata, license data, and match scores.
- `get_component_manifest` returns one manifest entry by canonical component ID.
- `add_component_instance` writes a selected registry component into
  `design_model.json` and refreshes `assets.lock.json`.

`search_local_library` remains a human-readable summary path for short display
responses, not the preferred reasoning contract.
