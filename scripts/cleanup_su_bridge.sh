#!/bin/bash
# Cleanup script for su_bridge - removes socket and resets Ruby state

SOCKET_PATH="/tmp/su_bridge.sock"

echo "=== su_bridge Cleanup Script ==="

# Remove socket file
if [ -e "$SOCKET_PATH" ]; then
    echo "Removing socket: $SOCKET_PATH"
    rm -f "$SOCKET_PATH"
else
    echo "Socket not found (OK if not running)"
fi

# For SketchUp plugin cache clearing, user needs to run the Ruby script
# inside SketchUp's Ruby Console
echo ""
echo "To fully reset su_bridge in SketchUp:"
echo "1. Open SketchUp Ruby Console"
echo "2. Run:"
echo "   load '/Users/avenir/Code/personal/sketchup-claude-code/scripts/cleanup_su_bridge.rb'"
echo ""
echo "This will:"
echo "  - Stop the running server"
echo "  - Remove all SuBridge constants (allow clean reload)"
echo "  - Delete the socket file"
echo ""
echo "Then restart with:"
echo "   SuBridge.start"
