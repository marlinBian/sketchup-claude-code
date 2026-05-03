# ADR 0003: Import Pipeline

Status: accepted
Date: 2026-05-03

## Context

Designers often begin from existing materials instead of an empty model:

- CAD drawings such as DWG or DXF
- floor-plan PDFs
- scanned drawings
- photos of printed plans
- existing floor-plan images

The harness needs to turn these inputs into the shared project truth so the
designer can keep working in SketchUp with natural language. The goal is not
perfect forensic conversion of the original file. The goal is a useful editable
working model that can be improved through normal design iteration.

## Decision

Add an autonomous-first import pipeline.

By default, import should interpret the source material, write a best-effort
result into `design_model.json`, and synchronize that result to SketchUp. The
pipeline should keep source provenance, confidence, assumptions, and reference
artifacts, but it must not block the initial workflow on repeated user
confirmation.

The designer-facing import behavior should be:

1. Accept a source file or image.
2. Infer or estimate scale when possible.
3. Generate a working model directly in `design_model.json`.
4. Execute or stage the generated model in SketchUp.
5. Report a short import summary with quality flags and assumptions.
6. Support source-backed repair when the user later points out a mismatch.

## Rationale

Designers are not good served by reviewing a long list of raw import candidates
before anything useful appears. Many numeric confirmations are low-signal:
designers may not have enough context to verify them, and saying yes does not
mean they inspected the evidence.

The harness should therefore optimize for momentum:

- create the first editable model quickly
- preserve enough provenance to debug it
- make correction cheap and localized
- keep the source drawing available as a reference overlay

## Project Files

Designer projects should include import state under `imports/`:

```text
imports/
  import_001/
    manifest.json
    source/
      floorplan.pdf
    previews/
      page_1.png
    evidence/
      page_1_region_kitchen.png
    extracted/
      raw_vectors.json
      interpretation.json
```

`manifest.json` records source metadata, file hashes, detected format, scale
assumptions, processing steps, generated model references, and quality flags.

`interpretation.json` records the internal import interpretation. It is evidence
and debugging context, not a user approval gate. Confirmed or inferred geometry
is promoted automatically into `design_model.json` unless the import cannot
produce a useful working model.

## Design Model Contract Direction

The current `design_model.json` supports rectangular spaces and placed
components. Import requires richer additive fields:

- `import_sessions`: source files, assumptions, scale, and processing metadata
- `walls`: wall paths, height, thickness, source provenance, and execution
  metadata
- `openings`: doors and windows hosted by walls
- `spaces.<id>.footprint`: non-rectangular floor-plan polygons
- `quality_flags`: low-confidence regions, missing scale, ambiguous openings,
  and unsupported source entities

These additions must be backward-compatible. Existing rectangular bathroom and
component workflows should keep working while richer imported models are added.

## User Interaction Policy

Import should not ask the user to confirm every wall, door, room, or numeric
dimension before writing a model.

Allowed confirmation points:

- the user explicitly asks for a review-only import
- the source has no usable scale and there is no reasonable fallback
- the requested operation would overwrite existing project truth
- the user asks to repair a mismatch against the source
- the tool is about to discard or replace previous imported model work

Otherwise, the import path should proceed automatically and report assumptions
after the model exists.

## Repair Workflow

Source-backed repair is a first-class requirement. If the user says the imported
model differs from the original, the harness should:

1. Find affected model entities by provenance.
2. Retrieve the relevant source evidence or drawing region.
3. Reinterpret that region or entity class.
4. Patch `design_model.json`.
5. Re-execute the affected SketchUp trace.
6. Report the specific change.

## Consequences

- Import results are working truth, not immutable measurements.
- Source evidence must be kept so local repairs are possible.
- Validation should flag import quality risks without blocking normal design
  progress.
- Runtime skills must describe import as direct generation plus repair, not as a
  manual preflight approval workflow.
- MCP tools should return structured import summaries and changed model IDs.
- The Ruby bridge needs reference overlay and imported wall/opening execution
  support before live SketchUp import can be considered complete.

## Non-goals

- Do not promise perfect DWG, PDF, or photo conversion.
- Do not make pixels or raw CAD entities the canonical source of truth.
- Do not require designers to use an editor or inspect JSON.
- Do not build a public import service before the local pipeline is proven.
