---
name: project-runtime-memory
description: Create and maintain project-local dynamic runtime skills for source-specific import knowledge, designer corrections, and scoped project preferences.
---

# Project Runtime Memory Skill

## Purpose

Use project-local dynamic runtime skills to preserve guidance that is useful
inside one design project but is too specific to ship as product behavior.

This skill is a baseline product skill. It defines how to create and update the
third skill layer:

- baseline product runtime skills live in the product `skills/` directory and
  must stay generic
- project/session dynamic runtime skills live inside the active design project
  and may be project-specific
- development skills live outside the product repository and are for
  maintainers only

## When to Use

Create or update a project/session dynamic runtime skill when runtime work
discovers guidance that should affect future turns in the same project, such as:

- an import source uses a local symbol convention
- the designer corrects the same source interpretation more than once
- a room naming convention matters for later natural-language commands
- a project has a durable preference that is not a general product rule
- a source-backed repair should guide future checks for the same import source

Do not create a dynamic skill for one trivial action that is already captured in
`design_model.json`, `design_rules.json`, a component manifest, or an import
manifest.

## Storage

Store dynamic runtime skills in the active design project, not in the product
repository and not in maintainer skill directories.

Preferred locations when supported:

```text
<project>/.agents/skills/<skill-name>/SKILL.md
<project>/.claude/skills/<skill-name>/SKILL.md
```

For import-specific guidance, prefer a stable name based on the import ID:

```text
import-source-<import_id>
```

For project-wide preferences, prefer:

```text
project-memory
```

## Dynamic Skill Format

Every dynamic `SKILL.md` must be loadable by agent CLIs:

```markdown
---
name: import-source-import_001
description: Project-local guidance for import source import_001.
---

# Import Source import_001

## Scope

This skill applies only to this design project and import source.
`design_model.json` remains canonical truth.

## Provenance

- import_id: import_001
- source_path: imports/import_001/source/...
- source_hash: ...

## Guidance

- ...

## Repair History

- ...
```

Keep the content concise, source-backed, and easy to delete if the project is
archived.

For import sources, pair the dynamic skill with structured constraints whenever
the guidance should affect generated geometry:

```text
imports/<import_id>/constraints.json
```

The dynamic skill should reference the constraints file; the constraints file
should contain machine-checkable assertions such as:

- exterior outline evidence, including expected steps, notches, recesses, or
  wall-mass outline segments that should not be simplified away
- negative/outside region evidence, including explicit `forbid_spaces` or
  overlap limits when a source blank area must not become an imported room,
  balcony, platform, or other positive space
- boundary closure evidence, including source edges that must be covered by
  wall geometry and source edges that must contain a door, window, or generic
  opening
- opening evidence, including host candidates, interval/anchor, target space,
  access-from space, hinge/swing evidence, and exterior/entry markers
- window or glazing evidence, including host candidates and interval/anchor
- room-label and dimension-chain evidence used to accept or reject candidates

Use prose in the dynamic skill to explain scope and provenance. Use structured
constraints to control final output.

Structured constraints must distinguish extracted evidence from manually added
guidance. Use provenance such as `vision_extracted`, `ocr_extracted`,
`cad_extracted`, or `tool_extracted` only when the constraint came from the
source file extraction process. Use explicit non-extracted provenance such as
`designer_correction`, `manual_validation`, or `maintainer_debug` for scoped
runtime corrections or E2E diagnosis. Non-extracted constraints may guide future
turns in this same project, but they must not be treated as proof that automatic
floor-plan recognition worked.

Dynamic runtime skills must not become an answer-injection layer for import
E2E. They may summarize where source constraints live, record designer
corrections, or preserve project-specific interpretation history. They must not
be the primary store for geometry, opening, boundary, or outside-region answers
that the importer claims to have recognized automatically. Automatic
recognition requires a fresh source extraction pass and structured constraints
with extracted provenance.

## Import Use

During floor-plan import, keep raw source evidence and extracted interpretation
under `imports/<import_id>/`. Use a dynamic import skill only for guidance that
should influence future runtime turns, such as:

- source-specific symbol legend
- known false positives or false negatives for that source
- designer-confirmed corrections
- room-label interpretation notes
- scale/orientation assumptions that should be reused
- source-specific door/opening corrections, such as which room a door opens
  into, which adjacent space it is accessed from, or which wall segment a
  visible door symbol belongs to

Do not put source-specific facts into shipped skills like `import-floorplan`.
If the same failure appears across unrelated sources, generalize it as geometry,
topology, scale, provenance, or evidence-scoring logic, then update product
code or baseline runtime skills with tests.

If a dynamic skill is created during development, debugging, E2E validation, or
issue reproduction, mark its lifecycle clearly as `temporary-validation`,
`persistent-project-memory`, or `candidate-generalization`. Temporary validation
skills should be removed or ignored after the validation run; retained project
memory should point to structured import evidence rather than embedding
unchecked answers in prose.

Example import guidance that belongs in a project-local dynamic skill:

```markdown
## Guidance

- For this import only, `bedroom_door_001` uses the visible swing arc on the
  source image; keep the host on the source-indicated bedroom threshold and set
  `open_to_space` to the bedroom.
- For this import only, `space_access_001` is accessed from the visible
  adjacent circulation side, not from the exterior side; prefer the shared wall
  indicated by extracted source evidence if the source interpretation is
  regenerated.
```

This kind of guidance is valid only inside the active project. It should not be
copied into product runtime skills, maintainer development skills, or generic
import heuristics.

## Update Rules

When a designer reports that the generated model differs from the source:

1. Review the source evidence and current `design_model.json`.
2. Repair truth with the narrowest supported MCP/tool path.
3. Update the import evidence and manifest.
4. Update the project-local dynamic skill only if the correction should guide
   future turns for that project/source.
5. If the correction should constrain geometry, update the import source
   constraints file and rerun the import/generation flow from source evidence
   before clean replay.
6. Re-run execution planning or clean SketchUp replay when needed.

## Guardrails

- Do not treat dynamic skills as canonical truth.
- Do not rely on dynamic-skill prose alone for source fidelity when a
  machine-checkable constraint can be recorded.
- Do not use dynamic skills to hide schema or MCP tool gaps.
- Do not use dynamic skills or hand-authored constraints to fake automatic
  source recognition during validation.
- Do not copy dynamic skills into the product repository.
- Do not copy dynamic skills into maintainer development skill directories.
- Do not create source-specific product rules from one project-local dynamic
  skill without generalizing and testing the pattern.
