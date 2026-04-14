# Undo Semantics Specification

## Atomic Operations with Rollback

Every `execute_operation` request is atomic. On failure, the entire operation is rolled back and a structured error returned.

---

## Undo Transaction Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│                    Request Received                       │
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  1. Validate Request Parameters                         │
│     - Check operation_type is valid                      │
│     - Validate payload structure                        │
│     - Validate geometry (if applicable)                 │
└─────────────────────────┬───────────────────────────────┘
                          ▼ Valid?
                   ┌──────┴──────┐
                   │             │
              Pass │             │ Fail
                   │             │
                   ▼             ▼
┌────────────────────────┐  ┌─────────────────────────┐
│  2. Begin Undo          │  │  Return VALIDATION_ERROR │
│     SketchUp::UndoManager│ │  (no rollback needed)   │
│     .begin_operation    │  └─────────────────────────┘
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│  3. Execute Operation                                   │
│     - Create/modify entities                             │
│     - Apply materials                                    │
│     - Update layers                                      │
└─────────────────────────┬───────────────────────────────┘
                          ▼
                   ┌──────┴──────┐
                   │             │
              Success           Exception
                   │             │
                   ▼             ▼
┌────────────────────────┐  ┌─────────────────────────┐
│  4. Commit              │  │  5. Rollback            │
│  SketchUp::UndoManager  │  │  SketchUp::UndoManager  │
│  .commit_operation      │  │  .undo                   │
│                         │  │                         │
│  Return success with    │  │  Return error with      │
│  entity_ids, delta      │  │  UNDO_FAILED if rollback │
└─────────────────────────┘  │  fails                   │
                              └─────────────────────────┘
```

---

## Ruby Implementation

### UndoManager Wrapper

```ruby
module SuBridge
  class UndoManager
    def self.with_transaction(name:, rollback_on_failure: true)
      SketchUp::UndoManager.observer = nil  # Disable observers during undo
      SketchUp::UndoManager.begin_operation(name, true)

      begin
        yield
        SketchUp::UndoManager.commit_operation
        return :success
      rescue => e
        SketchUp::UndoManager.undo if rollback_on_failure
        SketchUp::UndoManager.clear
        raise e
      ensure
        SketchUp::UndoManager.observer = nil
      end
    end
  end
end
```

---

## Rollback Rules

### When Rollback Executes

| Scenario | Rollback? | Error Code |
|----------|-----------|------------|
| Invalid parameters | No | `VALIDATION_ERROR` |
| Geometry validation fails | No | `VALIDATION_ERROR` |
| Entity not found | No | `ENTITY_NOT_FOUND` |
| Operation succeeds | No | N/A |
| Operation raises exception | Yes | `UNDO_FAILED` or original error |
| Rollback itself fails | N/A | `UNDO_FAILED` |

### When Rollback Does NOT Execute

1. **Validation errors** - Operation never started, nothing to undo
2. **Read-only operations** - No changes made
3. `rollback_on_failure: false` - Caller explicitly opts out

---

## Error Handling

### Partial Success Not Allowed

If any part of an operation fails, the entire operation is rolled back.

```ruby
# WRONG - partial success allowed
def create_wall_with_window(params)
  wall = create_face(params[:wall_vertices])
  window = create_window_opening(params[:window])  # Could fail
  return { wall: wall, window: window }
end

# RIGHT - atomic
def create_wall_with_window(params)
  UndoManager.with_transaction(name: "Create wall with window") do
    wall = create_face(params[:wall_vertices])
    window = create_window_opening(params[:window])
    { wall: wall, window: window }
  end
end
```

### Exception Preservation

When rolling back, preserve the original exception:

```ruby
begin
  yield
rescue => e
  begin
    SketchUp::UndoManager.undo
  rescue => rollback_error
    raise RollbackError.new(
      "Original: #{e.message}, Rollback: #{rollback_error.message}"
    )
  end
  raise e
end
```

---

## Nested Transactions

Not supported in v1.0. Only one active transaction at a time.

---

## Undo Manager Observer

Disable observers during rollback to prevent side effects:

```ruby
# Before rollback
Sketchup::UndoManager.observer = nil

# Rollback
Sketchup::UndoManager.undo

# After rollback
Sketchup::UndoManager.observer = nil  # Re-enable if needed
```

---

## Progress Updates During Long Operations

For operations that take > 1 second, send progress notifications:

```json
{
  "jsonrpc": "2.0",
  "method": "progress",
  "params": {
    "operation_id": "op_abc123",
    "status": "in_progress",
    "percent": 50,
    "message": "Creating 500 faces..."
  }
}
```

Progress notifications do NOT affect rollback state.

---

## Model Revision Tracking

The model revision increments on each successful commit:

```json
{
  "result": {
    "operation_id": "op_abc123",
    "status": "success",
    "model_revision": 17
  }
}
```

On rollback, the model_revision remains at the pre-operation value.

---

## Error Response Structure

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Face creation failed: points are collinear",
    "data": {
      "operation_id": "op_abc123",
      "rollback_status": "completed",
      "model_revision": 16
    }
  },
  "id": 42
}
```

| Field | Description |
|-------|-------------|
| `code` | Error code from Error Codes table |
| `message` | Human-readable description |
| `data.operation_id` | The failed operation ID |
| `data.rollback_status` | `"completed"` if rollback succeeded, `"failed"` if rollback itself failed |
| `data.model_revision` | Model revision after rollback (unchanged from before operation) |

---

## Verification Checklist

- [ ] Every mutating operation wrapped in `UndoManager.with_transaction`
- [ ] Validation errors return immediately without transaction
- [ ] Exceptions trigger rollback
- [ ] Rollback failures return `UNDO_FAILED` error
- [ ] `model_revision` unchanged after rollback
- [ ] Progress notifications sent for long operations
- [ ] No nested transactions
- [ ] Observers disabled during rollback
