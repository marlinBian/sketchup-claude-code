# Component Search Skill

## Purpose

Search and place semantic components from the packaged component registry.

Use this skill when the designer asks for furniture, fixtures, lighting, or
other reusable objects by name, style, room type, or Chinese/English alias.

## Current Registry

The packaged registry lives at:

```text
mcp_server/mcp_server/assets/library.json
```

Treat this registry as the first source for supported components. It contains
component IDs, display names, categories, dimensions, anchors, clearances,
assets, licenses, aliases, and tags.

Chinese aliases are deliberate search data. For example, the user can ask for
`马桶`, and the registry can resolve it to `toilet_floor_mounted_basic`.

## Tool Flow

### 1. Search Before Placing

Use `search_components` first when the agent needs dimensions, anchors,
clearances, or license metadata:

```python
search_components(query="toilet", category="fixture", limit=5)
```

Use `get_component_manifest` when the component ID is known and the full
manifest is needed for placement or validation:

```python
get_component_manifest(component_id="toilet_floor_mounted_basic")
```

When the designer has a project-specific reusable object, register it before
searching or placing it:

```python
register_project_component(
    project_path="<project-path>",
    component_id="project_display_plinth",
    name="Project display plinth",
    category="furniture",
    width=900,
    depth=450,
    height=750,
    aliases_en=["display stand"]
)
```

After registration, pass `project_path` to `search_components`,
`get_component_manifest`, `add_component_instance`, and
`execute_component_instance` so project-local metadata is included.

`search_local_library` remains available for simple human-readable result
summaries:

```python
search_local_library(query="toilet", category="fixture", limit=5)
```

For Chinese user prompts, pass the user's natural words directly first:

```python
search_local_library(query="马桶", category="fixture", limit=5)
```

If the result is weak, retry with an English design term such as `toilet`,
`vanity`, `mirror`, `sofa`, or `ceiling light`.

### 2. Place a Supported Component

When a project path is available, write the component into project truth first:

```python
add_component_instance(
    project_path="<project-path>",
    component_id="toilet_floor_mounted_basic",
    position_x=500,
    position_y=700,
    position_z=0
)
```

This updates `design_model.json` and `assets.lock.json`.

Use `place_component` only when the designer wants direct SketchUp execution
and the bridge is running. If the component was already recorded in
`design_model.json`, prefer `execute_component_instance` so SketchUp execution
uses project truth and can save the returned entity ID:

```python
execute_component_instance(
    project_path="<project-path>",
    instance_id="toilet_001"
)
```

Use direct `place_component` only for ad hoc execution without a project
instance:

```python
place_component(
    component_name="Modern 2-Seat Sofa",
    position_x=3000,
    position_y=2000,
    position_z=0,
    rotation=0,
    scale=1
)
```

The current tool places by component display name, not by arbitrary external
asset path. It does not replace `add_component_instance` as the project source
of truth.

### 3. Prefer Slice Tools for Bathroom Layouts

When the user asks for a complete small bathroom, prefer the bathroom planning
slice instead of manually placing every object:

```python
plan_bathroom(project_path="<project-path>")
```

Use `execute_bathroom_plan` only when the user wants SketchUp updated and the
Ruby bridge is running.

## Result Handling

When reporting search results:

- Use the canonical component name and ID from the returned result.
- Mention key dimensions when placement depends on fit.
- Mention clearance requirements when they affect usability.
- Use machine-readable `search_components` results for actual reasoning; do not
  parse formatted summary text when JSON results are available.
- Do not claim legal code compliance from component metadata.

When reporting placement:

- Say whether SketchUp execution succeeded or failed.
- Say whether project files were updated when `add_component_instance` was used.
- Say whether `entity_id` was saved when `execute_component_instance` succeeded.
- If SketchUp is unavailable, keep the selected component and intended position
  clear so the user can retry after starting the bridge.
- Do not describe placeholder geometry as a final production model.

## External Sources

External search tools may exist for discovery:

- `search_sketchfab_models`
- `get_sketchfab_model`
- `download_sketchfab_model`
- `search_and_download_sketchfab`
- `search_warehouse`

Use them only when the packaged registry cannot satisfy the request. Current
external downloads are discovery/import assistance, not a guaranteed automatic
SketchUp placement path. If an external asset is needed, explain the import gap
plainly and keep the design model source of truth separate from downloaded
files.

## Component Metadata

When adding or reviewing registry entries, preserve these fields where possible:

```json
{
  "id": "toilet_floor_mounted_basic",
  "name": "Basic Floor-Mounted Toilet",
  "category": "fixture",
  "subcategory": "toilet",
  "dimensions": {
    "width": 380,
    "depth": 700,
    "height": 760
  },
  "anchors": {
    "bottom": "floor",
    "back": "wall"
  },
  "clearance": {
    "front": 600,
    "left": 250,
    "right": 250
  },
  "assets": {
    "skp_path": "${SKETCHUP_ASSETS}/fixtures/toilet_floor_mounted_basic.skp",
    "procedural_fallback": "box_component"
  },
  "aliases": {
    "en": ["toilet", "wc"],
    "zh-CN": ["马桶", "坐便器"]
  }
}
```

## Guardrails

- Search the packaged registry before using external model sources.
- Do not promise automatic import of arbitrary downloaded assets.
- Do not add unlicensed third-party model files to the registry.
- Do not ignore dimensions, anchors, or clearance metadata during placement.
- Do not place into SketchUp directly when the user expects the project source
  of truth to be updated.
- Keep user-facing examples bilingual where useful, but keep implementation
  instructions English-first.
