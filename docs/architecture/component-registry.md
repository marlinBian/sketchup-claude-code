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

Designer projects may also define project-local components in
`component_library.json`. Search and placement tools merge the packaged seed
library with this project-local library when `project_path` is provided.
Project-local component IDs should not collide with packaged component IDs.

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
initialization; it does not yet download external assets automatically. When a
referenced `.skp` already exists in the project cache, regenerated asset locks
mark that component as `cached`.

## Project-Local Components

`register_project_component` writes one semantic component entry into the
project's `component_library.json`. This supports early workflows where a
designer creates or imports a SketchUp object and wants the agent to reuse it as
a structured component later.

The first supported project-local registration path records metadata only:
dimensions, bounds, insertion point, anchors, clearances, asset path,
procedural fallback, aliases, tags, and license/provenance fields. It does not
yet extract a selected SketchUp entity into a `.skp` asset automatically.

`register_selected_component` is the first bridge-assisted registration path.
It reads the current SketchUp selection, infers dimensions from the selected
entity bounds, and writes a project-local component manifest. When
`export_asset` is enabled, it also asks the SketchUp bridge to save the selected
group or component definition into `assets/components/<component_id>.skp`.
When asset export is disabled or unavailable, the manifest can still point at
the expected project-local asset path and keep a procedural fallback.

`get_selection_info` remains the bridge-side inspection primitive for cases
where an agent needs to choose between multiple selected entities or explain why
selection-based registration cannot proceed. It returns selected SketchUp entity
IDs, names, layers, types, and bounds.

## Search Ranking

Search should prefer exact component IDs, names, and aliases before fuzzy or
tag-only matches. Category filters use canonical manifest category names such as
`fixture`, but plural user input such as `fixtures` is normalized for CLI use.

Agents should use machine-readable registry tools for reasoning:

- `search_components` returns matching component manifests with dimensions,
  anchors, clearance data, asset metadata, license data, and match scores.
- `get_component_manifest` returns one manifest entry by canonical component ID.
- `register_project_component` adds a project-local manifest entry.
- `register_selected_component` infers one project-local manifest entry from
  the current SketchUp selection.
- `add_component_instance` writes a selected registry component into
  `design_model.json` and refreshes `assets.lock.json`.
- `execute_component_instance` sends a project-backed component instance to the
  SketchUp bridge and records the returned entity ID when available.

`search_local_library` remains a human-readable summary path for short display
responses, not the preferred reasoning contract.
