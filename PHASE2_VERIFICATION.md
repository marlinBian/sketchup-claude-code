# Phase 2 Verification Guide

## Python Socket Bridge (`mcp_server/bridge/socket_bridge.py`)

### Features Implemented
- `BridgeConfig`: Configuration dataclass with socket path, timeouts, retries
- `PingResult`: Result dataclass for ping operations
- `ConnectionState`: Enum for connection lifecycle (DISCONNECTED → CONNECTING → HANDSHAKE → CONNECTED)
- `SocketBridge`: Main client class with:
  - `connect()` with retry logic (3 attempts, 0.5s delay)
  - `disconnect()` for cleanup
  - `send()` for JSON-RPC request/response
  - `ping()` for connectivity check
  - `wait_for_connection()` to wait for server ready
- `SyncSocketBridge`: Synchronous variant
- `create_bridge()`: Factory function

### Verification
```bash
cd /path/to/sketchup-agent-harness/mcp_server
python3 -c "
from mcp_server.bridge.socket_bridge import SocketBridge, BridgeConfig, PingResult, ConnectionState, create_bridge

# Test instantiation
config = BridgeConfig(socket_path='/tmp/su_bridge.sock')
bridge = SocketBridge(config)
print('Bridge state:', bridge.state)
print('Is connected:', bridge.is_connected)

# Test factory
bridge2 = create_bridge('/tmp/su_bridge.sock')
print('Factory works:', bridge2.state)

print('Python socket bridge OK')
"
```

---

## Ruby Server Listener (`su_bridge/lib/su_bridge/server_listener.rb`)

### Features Implemented
- `ServerListener`: Non-blocking socket server using `UI.start_timer`
- `SOCKET_PATH`: `/tmp/su_bridge.sock`
- `TIMER_INTERVAL`: 0.1 seconds for polling
- `PROTOCOL_VERSION`: "1.0", `SERVER_VERSION`: "0.1.0"
- `start()`: Sets up socket and schedules polling
- `stop()`: Clean shutdown
- `running?`: Status check
- `schedule_polling()`: Uses `UI.start_timer` for non-blocking polls
- `handle_ping()`: Responds with pong + version info
- `handle_handshake()`: Protocol negotiation
- `handle_execute_operation()`: Delegates to CommandDispatcher

### Syntax Check
```bash
cd /path/to/sketchup-agent-harness/su_bridge
ruby -c lib/su_bridge/server_listener.rb
ruby -c lib/su_bridge/command_dispatcher.rb
ruby -c lib/su_bridge/undo_manager.rb
```

---

## SketchUp Ruby Loading Instructions

### Manual Load in SketchUp Ruby Console

1. **Open SketchUp Ruby Console**
   - Window → Ruby Console (or press `Ctrl+~`)

2. **Load the su_bridge plugin**
   ```ruby
   load '/path/to/sketchup-agent-harness/su_bridge/lib/su_bridge.rb'
   ```

3. **Start the server listener**
   ```ruby
   SuBridge::ServerListener.new.start
   ```

4. **Verify server is running**
   ```ruby
   SuBridge::ServerListener.new.running?
   # => true
   ```

5. **Test ping (from Ruby console)**
   ```ruby
   # Create a mock client test
   require 'socket'
   sock = UNIXSocket.new('/tmp/su_bridge.sock')
   sock.write('{"jsonrpc":"2.0","method":"ping","params":{"timestamp":0},"id":1}' + "\n")
   puts sock.read
   sock.close
   ```

6. **Stop the server**
   ```ruby
   SuBridge::ServerListener.new.stop
   ```

### Alternative: Load via SketchUp Plugin Folder

Copy the `su_bridge` folder to your SketchUp plugins directory:
- **Windows**: `C:\Users\<you>\AppData\Roaming\SketchUp\SketchUp <year>\SketchUp\Plugins\`
- **macOS**: `~/Library/Application Support/SketchUp/SketchUp <year>/SketchUp/Plugins/`

Then su_bridge loads automatically on SketchUp startup.

---

## UndoManager Transaction Wrapping

The `undo_manager.rb` wraps all operations in `SketchUp::UndoManager.begin_operation`:

```ruby
def self.with_transaction(name:, rollback_on_failure: true)
  SketchUp::UndoManager.begin_operation(name, true)

  begin
    result = yield
    SketchUp::UndoManager.commit_operation
    result
  rescue => e
    if rollback_on_failure
      begin
        SketchUp::UndoManager.undo
        SketchUp::UndoManager.clear
      rescue => rollback_error
        raise RollbackError, "Original: #{e.message}, Rollback: #{rollback_error.message}"
      end
    end
    raise e
  ensure
    # Observers disabled during undo operations
  end
end
```

### Error Classes
- `UndoManager::ValidationError` (-32001): Invalid parameters/geometry
- `UndoManager::EntityNotFoundError` (-32004): Entity doesn't exist
- `UndoManager::PermissionError` (-32005): Operation not allowed
- `UndoManager::RollbackError` (-32002): Rollback itself failed

---

## Next Steps (Phase 3)

1. Connect Python MCP server to Ruby socket server
2. Implement actual `create_face`, `create_box`, `create_group` operations
3. Wire up `query_entities`, `query_model_info` resources
4. Add glTF export functionality
