---
name: import-floorplan
description: Import DWG, DXF, PDF, image, or floor-plan source material directly into editable project truth with source-backed repair.
---

# Import Floor Plan Skill

## Purpose

Turn existing source material into editable `design_model.json` truth and a
SketchUp-executable model. Import is autonomous-first: generate a useful working
model before asking the designer to inspect low-level candidates.

## When to Use

Use this skill when the designer asks to import:

- a DWG or DXF CAD file
- a PDF floor plan
- a scanned plan or drawing photo
- a PNG/JPEG/TIFF/WebP floor-plan image
- an existing plan that should become a SketchUp-editable model

Example user prompts:

```text
Import this floor plan and generate an editable model.
```

```text
导入这张户型图，生成可编辑模型。
```

## Default Workflow

1. Use `get_project_state` to confirm the current project path and whether
   existing imported model truth may be overwritten.
2. For raster/PDF/CAD sources where room labels, dimension chains, or outside
   blank regions are visible, create a project-local source interpretation JSON
   before import. Include `dimension_chains`, `negative_regions`,
   `space_candidates` with `label_area_m2` and `dimension_constraints`, and
   explicit wall/opening candidates when available. Then call
   `import_floorplan_to_model` with `source_interpretation_path`. If the user
   gives known dimensions, pass `width` and `depth` in millimeters. If not, let
   the tool estimate scale and write quality flags.
   When a room label includes an area, use it as positive evidence to test
   adjacent dimension-chain segments before marking any unlabeled strip as
   outside. For example, a `2.3m2` balcony beside a `1785mm` depth implies a
   width near `1289mm`, so a neighboring `1315mm` chain segment is a stronger
   balcony candidate than a visually adjacent `1180mm` strip. In ambiguous
   cases, emit competing `space_candidates` and avoid hard negative regions
   over any candidate that fits both the room label area and dimension chain.
   Do not draw continuous walls through visible circulation paths. If a hallway
   or passage visibly connects to a living/dining/kitchen area without a door
   arc, emit a hosted `opening` or let the import tool infer one from adjacent
   accepted space footprints. Use `door` only when the source shows a door leaf
   or swing arc, and set `swing_direction` from the hinge side along the host
   wall path. For private room doors, bind the door to the wall shared by the
   target room and hallway/passage when such an edge exists; include
   `open_to_space` so the door leaf opens toward the room rather than whichever
   side the wall path normal happens to face.
3. Call `plan_project_execution` to verify the imported walls can be compiled
   into hosted opening operations with sill/header wall pieces and thin
   door/window marker geometry.
4. If the designer wants SketchUp updated and the bridge is available, call
   `execute_project_model` with `clean_before_execute=true` and
   `clean_scope="all"`. Import replay should remove stale generated walls,
   openings, old source overlays, and template entities before writing the
   current truth into SketchUp. Treat a failed `post_execution_audit` as a
   scene-contamination failure; do not save or judge the SketchUp file until
   the live scene has no unexpected `Layer0` leftovers after clean replay.
5. Summarize the generated model IDs, wall/opening counts, scale source,
   quality flags, and assumptions.

Do not ask the designer to confirm every detected wall, door, window, or numeric
dimension before writing the first working model.

Do not patch `design_model.json` directly when a first import obviously expands
into outside blank source area or contradicts a visible room-area label. Treat
that as a source interpretation/generation issue: update the extracted
interpretation or rerun import with `source_interpretation_path` so candidate
spaces are rejected before truth is written.

For floor-plan images, treat the source image as an extraction aid, not as the
final SketchUp object. Unless the designer explicitly asks for an overlay review,
do not leave the original image in the SketchUp scene after import execution.
Normal top-view model truth uses positive Y upward on screen; if a raster source
was interpreted with image-space Y downward, repair the imported coordinates and
record that orientation repair in the import session.

## Source Registration

Use `register_import_source` only when the designer wants to register a source
without generating the model yet. Normal import requests should call
`import_floorplan_to_model` directly because it registers the source and writes
working truth in one step.

## Rescale After Import

When the designer later gives a better size, use `rescale_imported_model`.

Examples:

```text
The overall imported plan should be 8200 mm wide.
```

```text
这个户型整体宽度应该是 8200 毫米，重新缩放。
```

Pass `target_width`, `target_depth`, or `scale_factor` rather than asking the
designer to manually edit JSON.

## Source-Backed Repair

When the designer says a region differs from the original, do not restart the
whole import by default.

1. Call `review_model_against_import_source` with the import ID and target ID
   when available.
2. If the mismatch is a near-straight exterior wall that appears offset by a
   wall-thickness-sized step, call `normalize_imported_wall_alignment` with the
   import ID before using a broader repair. This snaps near-boundary wall
   segments onto shared exterior lines, removes zero-length connector walls, and
   marks the project for clean replay.
3. If the source shows an exterior corner notch or stepped corner that is
   missing from the generated model, call `repair_imported_corner_notch` with the
   corner, horizontal/vertical offsets in millimeters, and the affected imported
   space ID when known. This splits the boundary walls, adds the return walls,
   updates the space footprint, and records source-backed repair history.
4. If a space footprint edge exists in `design_model.json` but the explicit wall
   list missed a long segment, call `review_imported_boundary_coverage`, then
   `repair_imported_boundary_coverage`. The review also auto-classifies
   semantically unlikely short gaps, such as a short horizontal living-room to
   balcony edge with no explicit opening evidence, as false-opening candidates.
   The repair fills high-confidence long missing-wall gaps and those semantic
   false-opening gaps, records source-backed repair history, and marks the
   project for clean replay. Do not ask the designer to confirm those candidates
   one by one before the first repair pass.
5. If the generated shell encloses an extra pocket that is not part of any
   imported room or balcony footprint, call
   `review_imported_wall_space_consistency`, then
   `repair_imported_shell_overreach`. The repair trims or removes wall segments
   outside imported space footprints and can fill the resulting high-confidence
   footprint boundary gaps. The default overreach threshold is intentionally
   larger than wall thickness so normal wall-continuity slivers are not
   auto-trimmed.
6. Call `repair_imported_region` with the specific correction, such as target
   dimensions or wall thickness, when the issue is not an exterior alignment
   normalization case.
   If a designer reports that an imported window or door appears as a solid
   wall, first check `design_model.json` for an `openings.<id>` entry on that
   host wall. If the opening exists, the likely fault is the execution trace
   rather than the import classifier: `plan_project_execution` should emit
   `create_wall_with_openings`, not a continuous wall and not a `create_box`
   placeholder for the opening.
   If a designer reports that a passage or doorway disappeared, inspect the
   generated wall/opening trace before editing truth. Doorless passage
   connections should be hosted `opening` entries that cut the wall without
   producing a blocking marker; doors should render as a directional door leaf
   marker inside the hosted wall opening. If the door is present but attached
   to the wrong wall, repair the source interpretation/generation path so the
   host wall matches the intended adjacent spaces, such as
   `bedroom + hallway`, instead of patching only the current truth.
7. Call `plan_project_execution` again.
8. Execute the project with `clean_before_execute=true` and `clean_scope="all"`
   when the designer wants SketchUp updated, so stale geometry does not remain
   beside the repaired truth.

Example prompts:

```text
This wall is too thick compared with the source. Set imported walls to 180 mm.
```

```text
The top-left exterior corner has a missing notch. Restore it from the source.
```

```text
The living room boundary is missing a wall segment compared with the source.
```

```text
The balcony B boundary should be a solid wall, not an opening.
```

```text
The bottom-right import has an extra enclosed pocket that is not in the source.
```

```text
这个门和原图不一致，复查并修复。
```

## Reporting

After import or repair, report:

- `import_id`
- source file type
- generated space, wall, and opening IDs
- scale source and whether it was estimated
- non-blocking quality flags
- whether the project execution trace is ready
- whether SketchUp was refreshed with clean replay

Keep the response short. The source material and extracted evidence are retained
under `imports/<import_id>/`; `design_model.json` remains the editable working
truth.

## Guardrails

- Do not promise 100 percent accurate conversion.
- Do not treat pixels, raw CAD entities, or extracted evidence as canonical
  truth.
- Do not block initial import on routine confirmation prompts.
- Ask before destructive overwrite of unrelated existing project truth.
- Use millimeters for all dimensions.
- Do not leave duplicate old import geometry or raw source images in SketchUp
  after a normal import/re-import.
