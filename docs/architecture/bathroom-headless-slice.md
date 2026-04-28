# Bathroom Headless Slice

The first product slice is a deterministic bathroom planner that runs without a
live SketchUp bridge.

## Input

The MCP tool is `plan_bathroom`.

Default dimensions:

- width: `2000` mm
- depth: `1800` mm
- ceiling height: `2400` mm

The planner uses the packaged seed component library and built-in
`design_rules.json` defaults.

## Output

The planner returns JSON with:

- `design_model`: canonical project state that can be written to
  `design_model.json`
- `design_rules`: the applied rules that can be written to `design_rules.json`
- `validation_report`: deterministic clearance checks with rule provenance
- `bridge_operations`: a SketchUp operation trace for P3 execution
- `written_files`: present only when `project_path` is provided

SketchUp is not the source of truth for this slice. The bridge operation trace is
an execution plan derived from `design_model`, not independent state.

## Seed Layout

The default room contains:

- four walls
- one 700 mm bathroom door
- one floor-mounted toilet
- one 600 mm wall vanity
- one wall mirror
- one basic ceiling light

The seed layout is intentionally plain. It proves spatial contracts,
clearances, component lookup, and deterministic bridge payloads before visual
style or rendering loops are added.
