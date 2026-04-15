#!/bin/bash
# Restart su_bridge - cleans up and restarts the server

SOCKET_PATH="/tmp/su_bridge.sock"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== su_bridge Restart Script ==="

# Remove socket
if [ -e "$SOCKET_PATH" ]; then
    echo "Removing socket: $SOCKET_PATH"
    rm -f "$SOCKET_PATH"
fi

echo ""
echo "To restart su_bridge in SketchUp Ruby Console:"
echo ""
echo "  # First cleanup (removes cached constants):"
echo "  load '$SCRIPT_DIR/cleanup_su_bridge.rb'"
echo ""
echo "  # Then start fresh:"
echo "  load '$SCRIPT_DIR/../su_bridge/lib/su_bridge.rb'"
echo "  SuBridge.start"
echo ""
echo "Or run all in one:"
echo "  load '$SCRIPT_DIR/cleanup_su_bridge.rb'; load '$SCRIPT_DIR/../su_bridge/lib/su_bridge.rb'; SuBridge.start"
