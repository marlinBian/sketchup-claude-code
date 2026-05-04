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
2. For raster/PDF/CAD sources where room labels, dimension chains, openings,
   exterior shell steps, or outside blank regions are visible, run a vision or
   vector extraction pass before import. Start from the source file itself, not
   from an old `design_model.json`, old `source_interpretation.json`, dynamic
   skill notes, or prior failed truth. Create a project-local
   `source_interpretation.json` with the extracted geometry and source
   constraints.

   The import source must be the actual file being interpreted. For a chat or
   CLI-attached image, first use the attachment's real local path or copy the
   raster file into the project; never register a `.txt` note, prose
   description, old screenshot, or placeholder file as the source for automatic
   image recognition. If no real source file path is available, stop and ask the
   designer for the original image/PDF/CAD file path before claiming import
   recognition.

   For raster floor-plan images, use the agent's vision capability to inspect
   the source image and extract a structured interpretation. The extraction
   must include:

   - visible dimension chains and the resulting scale/orientation assumptions
   - room/space candidates with footprints, room-label areas when visible, and
     dimension constraints where available
   - wall candidates and exterior outline segments, including notches, recesses,
     and stepped corners
   - door, window, glazing, and generic passage candidates with source anchors
     or source intervals
   - negative/outside regions for visible blank areas that must not become
     rooms, balconies, platforms, or enclosed pockets
   - boundary closure constraints for positive spaces whose source edge is
     visibly closed by wall, railing, facade, glazing, or a window/door/opening
   - adjacency and alignment constraints when the source shows connected spaces,
     repeated facade lines, stacked openings, or shared boundaries

   Every extracted constraint must carry provenance. Use
   `vision_extracted` for image/PDF vision extraction, `ocr_extracted` for
   OCR-only text/dimension extraction, `cad_extracted` for CAD/vector layer
   extraction, and `tool_extracted` for deterministic extractor output. Include
   enough local evidence fields, such as `source_bbox`, `source_anchor`,
   `source_interval`, `visual_cue`, and `confidence`, so later repair can trace
   why the constraint exists. Do not use extracted provenance for constraints
   copied from user corrections, dynamic skills, or maintainer debugging.
   Do not emit placeholder evidence. If the source provides an interval but no
   reliable point anchor, include `source_interval` or `interval` only; do not
   write fake anchors such as `[0, 0, 0]` just to satisfy a schema.

   Include `dimension_chains`, `negative_regions`, `space_candidates` with
   `label_area_m2` and `dimension_constraints`, and explicit wall/opening
   candidates when available. Then call
   `import_floorplan_to_model` with `source_interpretation_path`. If the user
   gives known dimensions, pass `width` and `depth` in millimeters. If not, let
   the tool estimate scale and write quality flags.
   For raster/PDF extraction, state the source coordinate system explicitly. If
   coordinates come from image space, use a `scale.coordinate_system` such as
   `x east, y south, origin at north-west source corner` and include
   `scale.depth` or enough geometry for the import tool to transform the
   extraction into model-space Y-up coordinates before writing truth.
   Opening intervals should be explicit about semantics. Use
   `source_interval` for the visible coordinate interval along the host wall in
   the source/model plan coordinate system, and set `source_interval_mode` to
   `wall_coordinate` when known. Use `offset` and `width`, or
   `source_interval_mode: offset`, only when the values are already measured as
   distance from the host wall start. This matters on vertical walls in raster
   images because Y-down source intervals must be reversed into model Y-up
   coordinates before the opening offset is computed.
   When a room label includes an area, use it as positive evidence to test
   adjacent dimension-chain segments before marking any unlabeled strip as
   outside. In ambiguous cases, emit competing `space_candidates` and avoid hard
   negative regions over any candidate that fits both the room label area and
   dimension chain.
   Do not draw continuous walls through visible circulation paths. If a hallway
   or passage visibly connects to a living/dining/kitchen area without a door
   arc, emit a hosted `opening` or let the import tool infer one from adjacent
   accepted space footprints. Use `door` only when the source shows a door leaf
   or swing arc, and set `swing_direction` from the hinge side along the host
   wall path. For private room doors, bind the door to the wall shared by the
   target room and hallway/passage when such an edge exists; include
   `open_to_space` so the door leaf opens toward the room rather than whichever
   side the wall path normal happens to face. When the source makes it
   inferable, also include `access_from_space`, source-side anchor or interval
   evidence, and whether the door is explicitly an exterior/entry door. A
   balcony or interior access door should prefer the shared boundary between
   the target space and the access space over an exterior-only target boundary;
   reserve exterior-only single-space hosts for doors marked as entry/exterior
   access.
   If the import source has repeated ambiguity, a local symbol legend, or
   corrections that should guide later turns in the same project, create or
   update a project/session dynamic runtime skill in the active design project
   using normal skill frontmatter. Prefer names like
   `import-source-<import_id>`. Keep it project-local, for example under
   `.agents/skills/` and `.claude/skills/` when those runtime locations are
   supported. The dynamic skill may record source-specific interpretation and
   repair guidance, but `design_model.json` remains canonical truth and the
   source evidence remains under `imports/<import_id>/`. Follow the
   `project-runtime-memory` skill for dynamic skill scope, format, and
   guardrails. When source-specific guidance should constrain final output,
   store it as structured import constraints under `imports/<import_id>/` and
   have the dynamic skill point to those constraints. Do not rely on prose alone
   when the correction needs to be checked.
   Source constraints should cover visible source fidelity, not just execution:
   use opening constraints for required doors/windows, source intervals, source
   anchors, source host-wall orientation, and host-wall space references; use
   space constraints for footprint bounds and room-label areas; use adjacency
   constraints when the source shows that two spaces are connected through a
   door, window, or open passage; use exterior outline constraints when the
   source has a visible shell step, notch, recess, or wall-mass outline that
   must not be simplified into a rectangle; use boundary closure constraints
   when a visible source edge must be closed by a wall or must contain a
   window/door/opening; use negative-region constraints with `forbid_spaces`
   when a blank or exterior source area must not become an imported room,
   balcony, platform, or other positive space. Also use negative-region
   boundary-enclosure constraints when that blank area must remain outside or
   open; do not turn visible lines around a blank area into full-height wall
   constraints if doing so would close the blank area into a room-like pocket.
   Visible facade, railing, or glazing evidence around a blank area should be
   represented as non-enclosing source evidence or checked with explicit
   boundary type constraints, not treated as proof that the blank region is a
   positive space. When an accepted positive space such as a balcony or room
   borders a negative/outside region, separately encode the positive space edge
   as a boundary closure constraint, and require a wall/window/opening type when
   the source shows one. This closes the positive space without enclosing the
   outside blank region. Use alignment constraints when repeated exterior
   columns, stacked balconies, glazing runs, or other visible edges should stay
   on the same plan line.
   Source constraints must also record extraction provenance. If a constraint
   was written from a designer correction or temporary validation note, mark it
   that way and do not claim automatic recognition passed. Use extracted
   origins such as `vision_extracted`, `ocr_extracted`, `cad_extracted`, or
   `tool_extracted` only when the constraint was produced by source extraction
   from the uploaded file.
   For visible doors, do not rely only on a selected host wall ID and interval.
   Extract and store the source host axis or wall orientation, source anchor or
   interval, `open_to_space`, `access_from_space` when inferable, and
   `require_host_space_refs` when both spaces are known. If a generated door
   leaf or marker overlaps a nearby passage, adjacent door, or circulation path
   in top view, treat that as a door host/leaf-clearance source-fidelity
   failure. Regenerate or repair the source interpretation; do not make it pass
   by moving the door in a dynamic skill note.
3. Call `plan_project_execution` to verify the imported walls can be compiled
   into hosted opening operations with sill/header wall pieces and thin
   door/window marker geometry.
   Then call `validate_import_source_constraints` with
   `require_extracted_evidence=true` for E2E/source-recognition validation. If
   this fails because constraints are missing extracted provenance, do not claim
   the importer recognized the source. Rerun the extraction from the source
   image or classify the constraints as project-local manual correction.
   For image/PDF E2E, also check the import manifest and import session before
   execution: `source.source_type` must be `image`, `pdf`, `dwg`, `dxf`, or
   `sketchup`, and a recognition-driven import should have a
   `source_constraints_path`. If the source type is `unknown` or constraints
   are missing despite visible extracted evidence, rerun the source extraction
   and import rather than replaying a stale truth file into SketchUp.
4. If the designer wants SketchUp updated and the bridge is available, call
   `execute_project_model` with `clean_before_execute=true` and
   `clean_scope="all"`. Import replay should remove stale generated walls,
   openings, old source overlays, and template entities before writing the
   current truth into SketchUp. Treat a failed `post_execution_audit` as a
   scene-contamination failure; do not save or judge the SketchUp file until
   the live scene has no unexpected `Layer0` leftovers after clean replay.
   If saving the live SketchUp file after import, use `save_sketchup_model`
   with `require_clean_scene=true` or the CLI equivalent
   `save-skp --require-clean-scene`.
5. Summarize the generated model IDs, wall/opening counts, scale source,
   quality flags, and assumptions.

Do not ask the designer to confirm every detected wall, door, window, or numeric
dimension before writing the first working model.

Do not patch `design_model.json` directly when a first import obviously expands
into outside blank source area or contradicts a visible room-area label. Treat
that as a source interpretation/generation issue: update the extracted
interpretation or rerun import with `source_interpretation_path` so candidate
spaces are rejected before truth is written.

Do not put source-specific interpretation into this shipped skill. Source facts
such as "this drawing's thin double line means a window" or "this import source
uses a special balcony symbol" belong in import evidence and, if useful for
future turns, a project/session dynamic runtime skill generated inside the
active design project.

Do not treat normal project validation or clean SketchUp replay as proof that
the model matches the source. They prove the structured model and live scene are
internally executable. Source-specific fidelity requires source-scoped evidence
checks: boundary steps or notches, opening intervals, window/glazing intervals,
opening host-wall orientation, exterior outline segments, boundary closure and
boundary opening type, edge alignments, outside/negative regions, room-label
areas, and symbol legends should be represented as import evidence and checked
by supported review/validation tools before reporting the import as
source-checked. If a visual mismatch is obvious but no source-fidelity validator
can express it yet, treat that as a product capability gap instead of hiding the
case in prose.

Do not treat hand-authored project evidence or dynamic-skill notes as automatic
floor-plan recognition. They can diagnose a mismatch or preserve a correction
for the same project, but automatic import E2E should run source-fidelity
validation with extracted-evidence provenance required.

When running E2E import validation or retrying after a visible mismatch, follow
this source-first loop:

1. Regenerate extraction from the original source file, not from previous truth,
   a previous `.skp`, a previous failed interpretation, or dynamic skill prose.
2. Write source constraints with extracted provenance only when they were
   produced by the source extraction pass. Designer corrections, maintainer
   notes, and dynamic-skill guidance must use non-extracted provenance.
3. Validate with `require_extracted_evidence=true` before claiming automatic
   recognition. If the validator cannot express a visible mismatch yet, treat
   that as a product capability gap.
4. Run a full clean SketchUp replay and capture a top-view screenshot before
   reporting the generated `.skp` as visually checked.
5. If the top-view comparison exposes a mismatch, classify the generic failure
   class and improve the extractor, validator, import generation, or bridge
   execution path. Do not make E2E pass by writing the expected answer into a
   project/session dynamic skill.

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
   `repair_imported_boundary_coverage`. The repair fills high-confidence
   missing-wall gaps, records source-backed repair history, and marks the
   project for clean replay. Short gaps should stay candidates unless there is
   source-backed wall-continuity evidence; do not infer a wall from room names
   alone.
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
   `bedroom + hallway`, instead of patching only the current truth. If the
   mismatch is specific to one imported source, store the correction in
   `imports/<import_id>/` evidence and, when it should guide future turns for
   this same project, the project/session dynamic runtime skill. Do not promote
   that source-specific correction into this shipped skill.
7. If the repair teaches a project-specific interpretation, update the import
   evidence and the project/session dynamic runtime skill for that import
   source. When the correction affects future output, encode it as a structured
   source constraint as well as dynamic-skill guidance, then rerun import from
   source evidence. Do not update the shipped runtime skill with source-specific
   facts.
8. Call `plan_project_execution` again.
9. Execute the project with `clean_before_execute=true` and `clean_scope="all"`
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
- Do not overfit import extraction or repair to one source image. Regression
  examples may preserve a bug, but reusable behavior must be based on general
  geometry, topology, scale, provenance, or source-evidence rules.
- Do not confuse project/session dynamic runtime skills with shipped runtime
  skills. Dynamic skills may be specific to one project or import source;
  shipped skills must remain generic product behavior.
