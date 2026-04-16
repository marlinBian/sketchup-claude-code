#!/bin/bash
# Start the SketchUp MCP server
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m mcp_server.server
