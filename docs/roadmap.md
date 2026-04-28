# Roadmap

This roadmap is ordered by engineering risk. Do not build higher-level design
automation before the repository baseline and contracts are stable.

## P0: Baseline Cleanup

Goal: make the repository maintainable and CI-reproducible.

- remove generated files from git tracking
- keep public repository docs English-first
- move Chinese docs into explicit localization paths
- install Python test dependencies consistently
- separate live SketchUp integration tests from default unit tests
- make Ruby specs runnable without writing to system gems
- make CI reflect the real local baseline

Acceptance:

```bash
cd mcp_server && uv run --extra dev pytest tests/ -m "not integration" -v --tb=short
cd su_bridge && bundle exec rspec spec/ --format progress
npx markdownlint-cli2
```

## P1: Contract Lockdown

Goal: lock the minimum machine-readable contract for the first useful design
slice.

- decide the canonical design model filename and migration path
- define the bathroom slice fields in `design_model.json`
- define seed `design_rules.json` for bathroom clearances
- normalize component manifest fields: dimensions, bounds, anchors, clearance,
  assets, license, and aliases
- add fixtures for a tiny bathroom project
- add validation tests for valid and invalid examples

Acceptance:

```bash
cd mcp_server && uv run --extra dev pytest \
  tests/test_project_files.py \
  tests/test_design_model_schema.py \
  tests/test_design_rules_schema.py \
  tests/test_component_manifest_schema.py \
  tests/test_local_library_search.py \
  tests/test_placement_tools.py -q
```

## P2: Bathroom Headless Vertical Slice

Goal: complete the design logic without requiring SketchUp UI.

Target prompt:

> Create a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light,
> and clearance check.

Required behavior:

- generate structured project state
- select seed bathroom components
- place fixtures deterministically
- validate clearances before mutation
- produce a bridge operation list or mock bridge trace
- return a structured validation report

Acceptance:

```bash
cd mcp_server && uv run --extra dev pytest \
  tests/test_bathroom_planner.py \
  tests/test_bathroom_mcp_tool.py -q
```

## P3: SketchUp Bridge Execution

Goal: execute the bathroom slice in SketchUp.

- support the required Ruby bridge operations
- return entity IDs, bounds, and spatial deltas
- support procedural fallback geometry when a `.skp` asset is unavailable
- capture scene info after execution
- keep `design_model.json` synchronized with SketchUp results
- make the Ruby bridge write canonical `design_model.json` while retaining
  legacy `.design_model.json` read fallback
- sync bathroom execution entity IDs and operation results back into
  `design_model.json`

Acceptance:

```bash
cd mcp_server && uv run --extra dev pytest \
  tests/test_trace_executor.py \
  tests/test_bathroom_mcp_tool.py -q
cd su_bridge && bundle exec rspec spec/ --format progress
```

## P4: Install Flow

Goal: make normal designer use independent of the source checkout.

- add `sketchup-agent init`
- create a clean designer project directory
- configure Claude and Codex MCP entries from one source
- expose installed MCP startup through `sketchup-agent-mcp`
- expose runtime skills through supported plugin/skill mechanisms
- install packaged runtime skills into project-local Claude and Codex skill
  directories
- let `doctor` report missing, stale, or locally modified project runtime skills
- install or update the SketchUp Ruby bridge
- add `sketchup-agent install-bridge` with a SketchUp startup loader
- package the Ruby bridge runtime with the MCP wheel so designers do not need a
  source checkout to install the bridge
- document cleanup and rollback

Acceptance:

```bash
cd mcp_server && uv run --extra dev pytest tests/test_project_init.py -q
cd mcp_server && uv run --extra dev sketchup-agent init /tmp/sah-bathroom \
  --template bathroom --force
```

## P5: Runtime Skill UX

Goal: make designer-facing natural-language workflows match implemented
capabilities.

- keep runtime skill implementation instructions English-first
- add Chinese user prompt examples only as deliberate localization
- align runtime skill promises with real MCP tools
- cover project start, component search, semantic placement, validation, and
  style workflows

## P6: Component Registry

Goal: turn seed components into a maintainable semantic component system.

- expose `search_components` for JSON component search results
- expose `get_component_manifest` for canonical component ID lookup
- expose `register_project_component` for project-local semantic components
- expose `add_component_instance` for source-of-truth component insertion
- expose `execute_component_instance` for project-backed SketchUp execution
- validate component manifests and project asset locks
- add project-local cache shape at `assets/components/`
- populate `assets.lock.json` from used `component_ref` values
- expose `refresh_project_asset_lock` for cache-status refreshes
- track source URL, author, license, and redistribution notes
- improve search ranking
- defer a public website until contribution and storage needs are proven

## P7: Visual Loop

Goal: use screenshots and image generation as advisory design feedback.

- capture SketchUp camera views through `capture_project_snapshot`
- store snapshots with provenance in `snapshots/manifest.json`
- pass screenshots or line views to rendering/image tools
- map accepted visual feedback back into structured model changes
- keep generated visuals advisory; `design_model.json` remains the source of
  truth

## P8: Local Smoke And Doctoring

Goal: make maintainers and early users verify the harness without remembering
scattered commands.

- add `sketchup-agent validate <project-path>`
- add `sketchup-agent state <project-path>`
- add `sketchup-agent doctor [project-path]`
- add `sketchup-agent smoke [project-path] --force`
- add plugin startup smoke for `mcp_server/start.sh`
- keep the default smoke headless so it works without SketchUp
- add optional bridge execution with `--with-bridge`
- validate project files, asset locks, snapshot manifests, and headless planning
- probe live bridge runtime capabilities so stale loaded plugins are visible
- expose live bridge version and supported operation metadata
- make release checks use the same smoke path

## P9: Project Rule Overrides

Goal: make project-local design knowledge active instead of static
documentation.

- expose `get_design_rules`
- expose `set_design_clearance`
- expose `set_fixture_dimension`
- expose `set_design_preference`
- load `design_rules.json` when planning into an existing project
- merge configured designer profile rules from `SKETCHUP_AGENT_DESIGN_RULES`
  before project-local rules
- use project rules in `plan_bathroom`
- use project rules in `execute_bathroom_plan`
- use fixture dimension overrides during deterministic placement
- keep validation reports explicit about failed rule checks
- avoid overwriting designer preferences with built-in defaults unless creating
  a new project

## P10: Project State Inspection

Goal: make CLI agents inspect project truth without parsing files manually.

- expose `get_project_state`
- include effective design-rules, asset-lock, and visual-feedback summaries in
  project state inspection
- expose the same project-state reader through `sketchup-agent state`
- include saved version summaries in project state inspection
- expose `list_project_components`
- expose `validate_design_project`
- keep validation behavior shared with `sketchup-agent validate`
- use inspection tools in runtime skills before planning, placement, or visual
  review
- generate English-first project reports from the same project-state reader
- save and list project-local structured truth versions under `versions/`
- restore structured truth versions with explicit overwrite intent
