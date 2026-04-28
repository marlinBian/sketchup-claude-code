# Bridge Trace Execution

Bridge execution is intentionally separated from design planning.

`plan_bathroom` returns a deterministic operation trace without requiring
SketchUp. `execute_bathroom_plan` creates the same plan and sends each operation
to the SketchUp Ruby bridge through JSON-RPC.

## Operation Shape

Each operation contains:

- `operation_id`
- `operation_type`
- `payload`
- `rollback_on_failure`

The Python trace executor converts each entry to:

```json
{
  "jsonrpc": "2.0",
  "method": "execute_operation",
  "params": {
    "operation_id": "place_toilet_001",
    "operation_type": "place_component",
    "payload": {},
    "rollback_on_failure": true
  }
}
```

## Procedural Fallback

The component registry may point to `.skp` files that are not installed yet.
For the first vertical slice, the Ruby bridge supports procedural fallback for
`place_component` when the payload includes:

- `procedural_fallback`
- `dimensions`
- `position`
- `component_id`
- `instance_id`

If the `.skp` file is missing, the bridge creates a box-shaped placeholder using
the supplied dimensions and returns normal placement metadata. This keeps the
slice executable before a real component asset pipeline exists.

## Failure Behavior

The trace executor runs operations in order. By default it stops on the first
bridge error and returns a structured execution report with request and response
records for each attempted operation.

## Project State Feedback

When project-backed execution succeeds, the harness syncs bridge feedback back
into `design_model.json`:

- `execution.bridge_operations` records each successful operation, returned
  `entity_ids`, status, and spatial delta.
- component and lighting instances receive the first returned SketchUp
  `entity_id`.
- instance `execution.operation_id` records the bridge operation that created or
  last updated that instance.

SketchUp remains the live execution view. `design_model.json` remains the
project truth that later agent calls must read.
