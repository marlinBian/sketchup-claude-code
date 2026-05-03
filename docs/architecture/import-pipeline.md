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
- create wall geometry from wall paths
- cut or represent hosted openings
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

## MCP Tool Direction

The first tool set should be small and structured:

- `register_import_source`
- `import_floorplan_to_model`
- `get_import_summary`
- `rescale_imported_model`
- `review_model_against_import_source`
- `repair_imported_region`
- `list_import_sessions`

Mutating tools must return changed model IDs, warnings, and state feedback that
can be written into `design_model.json`.

## Runtime Skill Direction

Runtime skills should guide direct import and repair:

- "Import this floor plan and generate an editable model."
- "Use this wall as 3600 mm and rescale the imported model."
- "This door differs from the source; review and fix it."

They should not instruct the agent to ask for routine confirmation before
generating the first model.

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

## First Implementation Slice

The first implementation should avoid heavy external dependencies:

1. Add import project directories and manifest schema.
2. Register image/PDF/DWG sources and hash them.
3. Generate a reference overlay entry and import session summary.
4. Add a simple manual-scale or detected-scale field.
5. Create a deterministic sample imported room from a fixture.
6. Write it into `design_model.json`.
7. Produce a bridge trace that can render the imported room headlessly.

This establishes the contract before adding real OCR, CAD parsing, or image
interpretation.
