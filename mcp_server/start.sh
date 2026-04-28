#!/usr/bin/env bash
set -euo pipefail

# Start the SketchUp MCP server from the packaged plugin directory.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if command -v uv >/dev/null 2>&1; then
  if [[ "${1:-}" == "--startup-check" ]]; then
    exec uv run python -c "import mcp; import mcp_server.server"
  fi
  exec uv run python -m mcp_server.server
fi

PYTHON_BIN="${PYTHON:-python3}"
if [[ "${1:-}" == "--startup-check" ]]; then
  exec "$PYTHON_BIN" -c "import mcp; import mcp_server.server"
fi

exec "$PYTHON_BIN" -m mcp_server.server
