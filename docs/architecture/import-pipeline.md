# Import Pipeline

The import pipeline turns existing design material into a working
`design_model.json` and an editable SketchUp model.

The pipeline is autonomous-first: it should produce an initial model without
forcing designers through a long confirmation sequence. The source file remains
available for evidence, overlays, and later repair.

## Supported Source Classes

The architecture should handle these classes incrementally:

- CAD vector files: DWG and DXF
- document files: PDF pages with vector or raster content
- raster plans: PNG, JPEG, TIFF, and scanned floor-plan images
- photos: perspective or rotated photos of printed plans

Each source class may have a different extractor, but all extractors should
write the same import session shape.

## Pipeline Stages

### 1. Register Source

Copy or reference the source under `imports/<import_id>/source/`, compute file
hashes, and create `manifest.json`.

The registration step should not modify `design_model.json` except to add a
lightweight import session summary when the schema supports it.

### 2. Prepare Evidence

Create preview and evidence artifacts:

- page previews for PDFs
- normalized image previews for raster files
- raw vector summaries for CAD or vector PDF sources
- optional reference overlay assets for SketchUp

Evidence artifacts support later repair. They are not canonical project truth.

### 3. Interpret Source

Generate an internal interpretation from the source:

- candidate wall paths
- candidate openings
- room labels and footprints
- detected dimensions and scale clues
- warnings for unsupported layers, low contrast, missing scale, or ambiguity

The interpretation should be saved under `imports/<import_id>/extracted/`. It is
allowed to contain uncertainty because it is not the final public contract.

### 4. Generate Working Truth

Convert the best interpretation into `design_model.json` immediately.

Working truth should include provenance:

```json
{
  "source": {
    "import_id": "import_001",
    "source_file": "floorplan.pdf",
    "confidence": 0.82,
    "assumptions": ["Wall thickness inferred as 120 mm"]
  }
}
```

This result is editable and can be validated, versioned, executed, and repaired
like any other project truth.

### 5. Execute Or Stage In SketchUp

Build a bridge trace from the imported model:

- draw reference overlays when available
- create wall geometry from wall paths, using hosted opening operations for
  doors, windows, and other openings
- build sill/header wall pieces plus thin door/window marker geometry for
  hosted openings
- create floor faces from room footprints when practical
- tag imported entities separately from generated design additions

Execution should record entity IDs and operation metadata back into
`design_model.json`.

### 6. Summarize Quality

Return a compact import summary:

- generated wall, opening, and room counts
- scale source and confidence
- low-confidence regions
- unsupported source features
- next useful actions

The summary should inform the designer without turning import into an approval
workflow.

## Project Layout

```text
my-design-project/
  design_model.json
  imports/
    import_001/
      manifest.json
      source/
      previews/
      evidence/
      extracted/
```

## Design Model Extensions

The import pipeline should add fields in small, compatible steps.

### Import Sessions

`import_sessions` should summarize imported sources in the design model:

```json
{
  "import_sessions": {
    "import_001": {
      "source_file": "imports/import_001/source/floorplan.pdf",
      "source_type": "pdf",
      "status": "imported",
      "scale": {
        "source": "detected_dimension",
        "units": "mm",
        "confidence": 0.74
      },
      "quality_flags": ["ambiguous_kitchen_partition"]
    }
  }
}
```

### Walls

`walls` should represent building shell geometry that should not be modeled as
generic furniture components:

```json
{
  "walls": {
    "wall_001": {
      "path": [[0, 0, 0], [3600, 0, 0]],
      "height": 2800,
      "thickness": 120,
      "source": {
        "import_id": "import_001",
        "confidence": 0.86
      }
    }
  }
}
```

### Openings

`openings` should represent doors and windows attached to wall hosts:

```json
{
  "openings": {
    "door_001": {
      "type": "door",
      "host_wall": "wall_001",
      "offset": 1200,
      "width": 800,
      "height": 2100,
      "source": {
        "import_id": "import_001",
        "confidence": 0.79
      }
    }
  }
}
```

### Space Footprints

`spaces.<id>.footprint` should support non-rectangular rooms while preserving
the existing rectangular `bounds` field as a broad bounding box.

### Source Interpretation Gate

Raster/PDF/CAD extraction should produce a non-canonical
`source_interpretation.json` before writing working truth when the source
contains visible room labels, dimension chains, or outside/void regions. This
intermediate file is evidence, not canonical model state.

Useful interpretation fields:

- `dimension_chains`: axis-specific measured chains from the source, such as a
  bottom width chain that distinguishes interior rooms from outside white space.
- `negative_regions`: source areas that should not become rooms, walls, slabs,
  or exterior shell, such as blank outside-plan regions in a listing image.
- `space_candidates`: one or more candidate footprints per target space, with
  `label_area_m2`, `dimension_constraints`, and confidence.
- `walls` and `openings`: explicit structural candidates after the space
  candidates have been scored.
- `constraints`: source-scoped validation rules that must be checked after
  truth generation and clean replay. Use opening constraints for required
  source openings, intervals, anchors, host-wall orientation, and host-wall
  space references; use space constraints for footprint bounds and room-label
  areas; use adjacency constraints when the source shows two spaces connected
  through a door, window, or open passage; use exterior outline constraints for
  visible shell steps, notches, recesses, and wall-mass outline segments; use
  boundary closure constraints for source edges that must be covered by a wall
  or must contain a door/window/opening; use negative-region constraints with
  space-overlap limits when a blank or exterior source area must not become a
  room, balcony, platform, or other positive space; use alignment constraints
  when repeated exterior columns, stacked balconies, glazing runs, or other
  visible edges should stay on the same plan line.

`import_floorplan_to_model` can consume this interpretation with
`source_interpretation_path`. During generation it rejects space candidates
whose computed footprint area conflicts with a room label, whose dimensions
conflict with a source chain, or whose footprint overlaps a negative region.
After accepted spaces are selected, shell walls that extend outside all
accepted footprints are trimmed before the truth is saved. This catches errors
such as an imported balcony expanding into blank outside space instead of
matching its visible area label.

Clean SketchUp replay proves the bridge executed current truth, but it does not
prove the truth matches the source. Source fidelity is a separate gate:
`validate_import_source_constraints` should fail when a required source opening
is missing, an opening is hosted on a wall that does not connect the indicated
spaces or match the source wall orientation, a source anchor/interval moves,
visible exterior outline segments are simplified away, a required boundary edge
is not closed or lacks the source-indicated door/window/opening type, visible
aligned edges drift apart, a space footprint overlaps an outside/negative
region, or a required source adjacency disappears.

## MCP Tool Direction

The first tool set should be small and structured:

- `register_import_source`
- `import_floorplan_to_model`
- `get_import_summary`
- `rescale_imported_model`
- `normalize_imported_wall_alignment`
- `repair_imported_corner_notch`
- `review_imported_boundary_coverage`
- `repair_imported_boundary_coverage`
- `review_imported_wall_space_consistency`
- `repair_imported_shell_overreach`
- `review_model_against_import_source`
- `repair_imported_region`
- `list_import_sessions`

Mutating tools must return changed model IDs, warnings, and state feedback that
can be written into `design_model.json`.

SketchUp execution after import should use clean replay. The agent should call
`execute_project_model(clean_before_execute=True, clean_scope="all")` after a
successful `plan_project_execution` when the designer wants the import reflected
in SketchUp. This removes stale managed geometry, raw source overlays, and
template entities before the current `design_model.json` truth is replayed. A
full-scene clean replay must pass the post-execution clean-scene audit; leftover
top-level `Layer0` entities indicate stale SketchUp scene contamination, not
current import truth. Saving the live `.skp` after import should use the
clean-scene save option so the same audit runs before and after the save.
After replay, execution metadata should also represent only the current trace:
hosted openings should point at their `create_wall_with_openings` operation,
and old `opening_*` placeholder operations or split-wall `*_solid_*` operation
records should not remain in `execution.bridge_operations`.

## Runtime Skill Direction

Runtime skills should guide direct import and repair:

- "Import this floor plan and generate an editable model."
- "Use this wall as 3600 mm and rescale the imported model."
- "This door differs from the source; review and fix it."

They should not instruct the agent to ask for routine confirmation before
generating the first model.

They should also treat raster/CAD/PDF source material as evidence, not as the
final SketchUp scene object. Unless the designer explicitly requests an overlay
review, source images and previous import geometry should not remain in
SketchUp after normal import execution.

When a source dimension chain mixes outside and inside wall references, imported
outer walls can land on two nearly parallel boundary lines. The repair path for
that case is `normalize_imported_wall_alignment`: it snaps near-boundary imported
wall segments onto shared exterior lines, removes zero-length connector walls,
records the repair in the manifest, and marks project truth for clean replay.

When the first generated truth simplifies an exterior stepped corner into a
rectangle, the repair path is `repair_imported_corner_notch`: it splits the two
boundary walls at the selected corner, adds the vertical and horizontal return
walls, updates the affected imported space footprint when provided, records
source-backed repair history, and marks project truth for clean replay.

Imported space `footprint` edges are also a source of truth that can expose
missing wall segments. If an extracted model contains a footprint edge but the
explicit `walls` list does not cover a long segment of that edge, the review
path is `review_imported_boundary_coverage` and the repair path is
`repair_imported_boundary_coverage`. The repair fills high-confidence
missing-wall candidates: uncovered segments longer than normal door/opening
gaps and supported by nearby structural wall endpoints by default. Shorter
uncovered segments normally remain classified as possible openings or
intentional gaps unless source-backed wall-continuity evidence supports a
missing wall. Semantic room names alone are not enough to turn a short gap into
a wall, because that would overfit a single source's layout vocabulary instead
of using observable geometry, topology, and source evidence.

If one source needs a specific interpretation, such as a local symbol legend or
a correction learned from the designer, keep that information in the import
evidence and, when it should guide later turns, in a project/session dynamic
runtime skill generated inside the active design project. Do not promote that
source-specific content into shipped runtime skills or product code unless the
pattern has been generalized and tested across variants. Dynamic import skills
should point to `imports/<import_id>/constraints.json` for machine-checkable
source evidence. They should not rely on prose for geometry that can be
validated as outline segments, negative/outside regions, boundary closure,
opening intervals, or symbol legends.

Imported walls also need the inverse consistency check: every meaningful
imported wall segment should be explainable by at least one imported room,
balcony, or other space footprint edge. If a wall extends past all imported
space footprints, it can create a phantom enclosed area even when no footprint
claims that area. The review path is `review_imported_wall_space_consistency`
and the repair path is `repair_imported_shell_overreach`. The repair trims or
removes overreaching wall intervals, updates generated wall IDs, clears stale
execution metadata, records source-backed repair history, and can fill the
newly exposed high-confidence footprint boundary gaps. Its default minimum
segment length is larger than normal wall thickness so wall-continuity slivers
between adjacent footprints are not auto-trimmed as phantom spaces.

## Validation Direction

Validation should check import quality without blocking momentum:

- missing or weak scale
- unclosed room footprints
- impossible wall thickness
- openings without host walls
- overlapping duplicate walls
- unsupported source entities
- imported model too small or too large for likely residential scale

Validation reports should separate hard schema errors from quality flags.

## Current Implementation Slice

The current implementation avoids heavy external dependencies while accepting a
structured extraction produced by an agent vision pass, CAD/vector parser, OCR
tool, or future deterministic extractor. If no richer extraction is available,
it can still generate a low-confidence rectangular working model, but
source-checked image/PDF/CAD import requires a real registered source file plus
`source_interpretation.json` and source-scoped constraints.

1. Create `imports/<import_id>/` with `source/`, `previews/`, `evidence/`, and
   `extracted/`.
2. Register DWG, DXF, PDF, image, SketchUp, or unknown sources with hashes and
   source type.
3. Reject structured interpretations that are attached only to text notes,
   screenshots of prior output, or other unknown placeholder sources. Automatic
   image/PDF/CAD recognition must point at the actual source file.
4. Normalize raster/PDF Y-down source coordinates into model-space Y-up
   coordinates before writing truth. Host-wall source intervals are interpreted
   as wall-coordinate intervals unless explicitly marked as offset values.
5. Write a manifest and `extracted/interpretation.json` for retained evidence.
   If extracted constraints are not nested under `constraints`, copy supported
   top-level constraint lists and derive wall, opening, and negative-region
   constraints from extracted provenance.
6. Generate a deterministic editable rectangular shell as the first working
   model when richer extraction is unavailable.
7. Write imported `spaces`, `walls`, `openings`, `import_sessions`, and
   `quality_flags` into `design_model.json`.
8. Preserve project/source-specific runtime guidance through project-local
   dynamic skills when needed, without promoting those facts into shipped
   runtime skills.
9. Produce a headless bridge trace for imported walls and hosted opening
   operations that create wall pieces, sills, headers, and thin door/window
   markers.
10. Expose list, summary, rescale, wall-alignment normalization, corner-notch
   repair, boundary coverage review/repair, review, and repair tools through MCP
   and CLI.

Richer extractors should replace only the extraction stage. They must keep the
same manifest, generated truth, quality flag, source-fidelity constraint, and
repair contracts.
