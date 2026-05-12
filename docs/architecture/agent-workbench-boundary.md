# Agent Workbench Boundary

SketchUp Agent Harness supports multiple agent runtimes, but the product core
must stay tool-independent.

This document defines where new behavior belongs when Claude Code, Codex CLI,
or a future workbench such as Pi or OpenCode needs a better designer
experience.

## Layer Model

### Core Product

Core product behavior is shared across every agent runtime:

- `design_model.json` and related schemas
- Python CLI and MCP tools
- SketchUp Ruby bridge execution
- import evidence and structured repair records
- deterministic validation, planning, and execution logic

If a capability mutates project truth, validates project truth, or must behave
the same no matter which agent runtime is used, it belongs here.

### Portable Guidance

Portable guidance describes how an agent should use existing product
capabilities:

- shipped runtime skills under `skills/`
- project docs such as `README.md`, `QUICKSTART.md`, and `DESIGNER_GUIDE.md`
- project-scoped dynamic runtime skills generated inside an active design
  project

Portable guidance may shape workflow, review order, and failure recovery, but
it must not replace deterministic product behavior. A runtime skill can require
an agent to call `review_import_stages`, but the actual review result belongs in
the MCP response and saved evidence, not in prompt-only memory.

### Agent Adapters

Adapters are runtime-specific packaging or invocation layers:

- `.claude-plugin/`
- `.codex-plugin/`
- `.agents/plugins/`
- tool-specific startup manifests, install hooks, and command registration

Adapters may decide how the harness is installed, discovered, or launched inside
one agent runtime. They must not become the owner of model truth, import
evidence, component metadata, or designer corrections.

### Optional Workbench Experiments

Workbench layers are optional runtime shells built on top of the product core:

- demo runners
- timing dashboards
- progress/status views
- guarded execution flows
- correction wizards
- packaged session exports

These are allowed to improve the experience for one runtime, but they are not
the product core. If a workbench feature disappears, the design project and its
truth must still remain valid and usable through the CLI and MCP surfaces.

## Decision Rules

Use these rules before adding a feature:

### Add To CLI Or MCP

Add behavior to the product core when any of the following is true:

- it creates, mutates, validates, compares, or restores project truth
- it changes import interpretation or source-backed repair semantics
- it must be replayable without one specific agent runtime
- it needs deterministic tests
- it affects SketchUp bridge execution or command payloads

Examples:

- new import review stages
- structured correction recording
- project state inspection
- guarded clean replay flags

### Add To A Shipped Runtime Skill

Add behavior to a shipped runtime skill when:

- the core tool already exists
- designers need generic guidance on when to call it
- the workflow is reusable across many projects
- the rule can stay source-independent

Examples:

- import review sequence
- generic source-fidelity warnings
- when to create project-local dynamic runtime memory

Do not put sample-floor-plan facts, room labels, dimensions, or source-specific
answers here.

### Add To A Dynamic Runtime Skill

Add behavior to a project/session dynamic runtime skill when:

- the guidance is tied to one imported source, one project, or one designer
- the fact came from evidence extraction, designer correction, or repeated local
  runtime use
- the guidance should shape later turns in the same project only

Examples:

- one floor plan's symbol legend
- a source-specific exterior closure interpretation
- project-local naming preferences

Dynamic runtime skills are scoped memory, not published product logic.

### Add To An Agent Adapter Or Workbench Layer

Add behavior to an adapter or optional workbench when:

- the feature is about install UX, command discovery, hooks, menus, status UI,
  or packaging
- the feature is useful in one runtime but not required for all runtimes
- the feature orchestrates existing CLI/MCP capabilities rather than changing
  model semantics

Examples:

- one-command demo flow
- runtime-specific status panel
- tool-specific command aliases
- session export for one workbench

## Source Of Truth Rule

Agent adapter state and workbench state are never canonical truth.

The following remain canonical or product-owned:

- `design_model.json`
- project rules and manifests
- import evidence under `imports/`
- persisted correction records
- bridge execution traces derived from the current model

The following are non-canonical helper state:

- workbench UI cache
- runtime-specific command history
- plugin-local session state
- temporary status artifacts
- demo orchestration metadata that can be regenerated from project truth

If deleting one runtime's plugin cache would lose design intent, the design data
is stored in the wrong layer.

## Maintainer Checklist

Before implementing a new feature, ask:

1. If Claude, Codex, Pi, and OpenCode all disappeared tomorrow except raw CLI
   and MCP access, would this feature still be required?
2. If yes, put it in the product core.
3. If no, does it still change truth semantics or import semantics?
4. If yes, put the semantics in the core and only the presentation in the
   adapter.
5. If no, keep it in the adapter or optional workbench layer.

## Relationship To Skill Layers

- Shipped runtime skills define generic designer workflows.
- Dynamic runtime skills preserve project-local or source-local memory.
- Maintainer development skills live outside the product repository and govern
  how the product is developed.

None of those skill layers should be used to smuggle adapter-only state into
product truth.
