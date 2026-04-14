#!/bin/bash
# Start the SketchUp MCP server
cd "$(dirname "$0")"
exec uv run python -m mcp_server.server
