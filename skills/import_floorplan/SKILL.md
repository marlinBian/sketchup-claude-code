---
name: import_floorplan
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
2. Call `import_floorplan_to_model` with the source path. If the user gives
   known dimensions, pass `width` and `depth` in millimeters. If not, let the
   tool estimate scale and write quality flags.
3. Call `plan_project_execution` to verify the imported walls and opening
   placeholders can produce a bridge trace.
4. If the designer wants SketchUp updated and the bridge is available, call
   `execute_project_model` with `clean_before_execute=true` and
   `clean_scope="all"`. Import replay should remove stale generated walls,
   openings, old source overlays, and template entities before writing the
   current truth into SketchUp.
5. Summarize the generated model IDs, wall/opening counts, scale source,
   quality flags, and assumptions.

Do not ask the designer to confirm every detected wall, door, window, or numeric
dimension before writing the first working model.

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
   `repair_imported_boundary_coverage`. The repair fills high-confidence gaps
   that are longer than normal door/opening candidates and have structural wall
   endpoints, records source-backed repair history, and marks the project for
   clean replay.
5. Call `repair_imported_region` with the specific correction, such as target
   dimensions or wall thickness, when the issue is not an exterior alignment
   normalization case.
6. Call `plan_project_execution` again.
7. Execute the project with `clean_before_execute=true` and `clean_scope="all"`
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
