---
name: import-floorplan
description: Import DWG, DXF, PDF, image, or floor-plan source material into editable project truth with staged evidence and repair.
---

# Import Floor Plan Skill

## Purpose

Turn an existing plan source into editable `design_model.json` truth and,
when requested, a SketchUp model. Import is autonomous-first: create a useful
first working model before asking the designer to inspect low-level candidates.

This skill does not promise survey-grade conversion or full visual CAD parsing.
It guides the agent through short observable stages, honest quality flags, and
source-backed repair when better evidence or designer corrections arrive.

## When to Use

Use this skill when the designer asks to import:

- DWG or DXF CAD files
- PDF floor plans
- scanned drawings or drawing photos
- PNG, JPEG, TIFF, WebP, or other raster floor-plan images
- existing plans that should become SketchUp-editable models

Example prompts:

```text
Import this floor plan and generate an editable model.
```

```text
导入这张户型图，生成可编辑模型。
```

The Chinese example is deliberate bilingual prompt support. Keep instructions,
tool names, schema keys, and generated product artifacts English-first.

## Capability Contract

Use the strongest path that the current source and tools can support:

- **Fast coarse import**: when rich geometry extraction is unavailable, create a
  coarse editable model with explicit assumptions and quality flags.
- **Evidence-backed import**: when vector/CAD/OCR/vision extraction is available,
  write structured source interpretation and constraints before generating
  working truth.
- **Source-fidelity validation**: only claim source checking when structured
  constraints exist and carry extracted provenance such as `vision_extracted`,
  `ocr_extracted`, `cad_extracted`, or `tool_extracted`.
- **Designer correction loop**: when the designer points out a mismatch, repair
  the import evidence or generation path and replay from current truth.

Do not hide manual corrections or maintainer debugging notes behind automatic
recognition language. Manual evidence can guide the same project, but it is not
proof that the importer recognized the source automatically.

## Default Workflow

1. **Read project state**
   - Call `get_project_state`.
   - Ask before destructive overwrite of unrelated existing project truth.
   - Do not ask the designer to confirm routine walls, doors, windows, or
     numeric candidates before creating the first model.

2. **Register and prepare the source**
   - For a real file path, call `prepare_import_source`.
   - For a chat or CLI image attachment without a local file path, use an
     explicit `source_reference` and `source_reference_type:
     chat_image_attachment`. Do not invent a `.txt` or `.md` source placeholder.
   - Call `extract_floorplan_source` to write `raw_extraction.json`.

3. **Choose the import path**
   - If extraction is weak, use `generate_source_interpretation` and then
     `import_floorplan_to_model`, or use `import_source_pipeline` for the fast
     coarse path.
   - If the source visibly supports richer interpretation, create or update
     `source_interpretation.json` from the original source, then call
     `import_floorplan_to_model` with `source_interpretation_path`.
   - If semantic/vision/CAD/OCR work happens outside the MCP server, call
     `record_import_stage_timing` so the manifest shows the real stage cost.

4. **Generate working truth**
   - `design_model.json` remains canonical editable truth.
   - Raw source data, extracted evidence, assumptions, quality flags, and
     source constraints stay under `imports/<import_id>/`.
   - Never reuse a prior failed `design_model.json`, old `.skp`, old dynamic
     skill note, or old interpretation as if it were a fresh extraction.

5. **Validate what is actually supported**
   - Call `plan_project_execution` to check that the model can compile into
     bridge operations.
   - Call `validate_import_source_constraints` only when source constraints
     exist. Use `require_extracted_evidence=true` when validating automatic
     recognition.
   - If a visible mismatch has no validator, report it as a product capability
     gap instead of writing the expected answer into a skill.

6. **Update SketchUp when requested**
   - If the bridge is available, call `execute_project_model` with
     `clean_before_execute=true` and `clean_scope="all"`.
   - Normal import/re-import should remove stale generated geometry, old source
     overlays, and template entities unless the designer explicitly requested
     an overlay review.
   - If saving the live model, use `save_sketchup_model` with
     `require_clean_scene=true` or the CLI equivalent.

7. **Report briefly**
   - Include `import_id`, source type, generated space/wall/opening counts,
     scale source, quality flags, assumptions, and whether SketchUp was
     refreshed.
   - Keep the response short. The designer will continue editing the model.

## Source Interpretation Guidance

Only write source facts that were actually extracted or supplied. Partial
evidence is acceptable; fake anchors, dimensions, or symbol claims are not.

Useful interpretation fields include:

- `scale` and `dimension_chains`
- `space_candidates`, footprints, and visible room-label areas
- `walls` and exterior outline segments
- `openings` for doors, windows, glazing, and generic passages
- `negative_regions` for outside or blank source areas that must not become
  positive spaces
- `constraints` for boundary closure, exterior outline preservation, opening
  host/interval/type, adjacency, alignment, negative-region overlap, and
  room-label area checks

For raster/PDF images, record the source coordinate system. Image coordinates
are commonly Y-down, while SketchUp top-view model truth is Y-up. Transform the
interpretation deliberately and record any orientation assumption or repair in
the import session.

When coordinates are uncertain, store intervals and confidence instead of
inventing point anchors. When space candidates conflict, preserve competing
candidates and let the import generator or validator reject weak candidates
using general geometry, topology, area, dimension, and negative-region rules.

## Dynamic Runtime Memory

Project/session dynamic runtime skills are allowed only inside the active
designer project, such as:

```text
<project>/.agents/skills/import-source-<import-id>/SKILL.md
<project>/.claude/skills/import-source-<import-id>/SKILL.md
```

Use the tool-generated dynamic skill when the import uses
`source_interpretation_path` or an unfiled `source_reference`. The dynamic skill
may summarize project-local source guidance and link to structured evidence, but
it must not become the geometry source of truth or an answer-injection layer.

Source-specific facts belong in:

```text
imports/<import_id>/
```

and, when future turns in the same project need the guidance, in the
project-local dynamic skill. Do not put source-specific facts into this shipped
runtime skill.

## Source-Backed Repair

When the designer reports a mismatch with the original source:

1. Inspect current `design_model.json`, import evidence, and the latest bridge
   trace before editing truth.
2. Use the narrowest supported review or repair tool, such as:
   - `review_model_against_import_source`
   - `review_imported_boundary_coverage`
   - `repair_imported_boundary_coverage`
   - `review_imported_wall_space_consistency`
   - `repair_imported_shell_overreach`
   - `normalize_imported_wall_alignment`
   - `repair_imported_corner_notch`
   - `repair_imported_region`
3. If the correction should affect future turns for the same source, store it as
   structured import evidence and update the project-local dynamic skill.
4. Re-run planning and clean SketchUp replay when the designer wants the live
   model updated.

Do not patch `design_model.json` directly to make a single screenshot look
right if the same result should come from source interpretation or import
generation.

## E2E Validation Loop

When validating an import end to end:

1. Start from the original source file or explicit source reference.
2. Regenerate extraction and interpretation; do not reuse previous failed truth.
3. Generate `design_model.json`.
4. Run source-constraint validation only for constraints with honest provenance.
5. Clean-replay into SketchUp.
6. Capture a top-view screenshot and compare it against the source.
7. If a mismatch appears, classify the generic failure class before changing
   code or skills: exterior outline/topology, negative/outside region polarity,
   boundary closure, opening host/interval/type, space footprint/area,
   alignment, clean replay contamination, or bridge execution.

Do not make validation pass by writing the expected answer into a shipped skill
or a project-local dynamic skill. Dynamic skills can preserve scoped evidence;
product correctness must come from general import logic and validators.

## Guardrails

- Do not promise 100 percent accurate conversion.
- Do not treat pixels, raw CAD entities, or extracted evidence as canonical
  truth.
- Do not block initial import on routine confirmation prompts.
- Ask before destructive overwrite of unrelated existing project truth.
- Use millimeters for dimensions.
- Do not leave duplicate old import geometry or raw source images in SketchUp
  after normal import/re-import.
- Do not overfit import extraction or repair to one source image.
- Do not confuse project/session dynamic runtime skills with shipped runtime
  skills.
