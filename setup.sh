#!/bin/bash
# SCC (SketchUp-Claude-Code) Setup Script
# Run this once after cloning or pulling updates
#
# Usage:
#   ./setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "SCC Setup - SketchUp-Claude-Code Plugin"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check and install uv
echo "Step 1: Checking for uv (Python package manager)..."
UV_BIN=""

# Check common uv locations
for path in /opt/homebrew/bin/uv ~/.local/bin/uv ~/.cargo/bin/uv /usr/local/bin/uv /usr/bin/uv; do
    if [ -f "$path" ]; then
        UV_BIN="$path"
        break
    fi
done

# Check if uv is in PATH
if [ -z "$UV_BIN" ] && command -v uv &> /dev/null; then
    UV_BIN="$(which uv)"
fi

if [ -n "$UV_BIN" ]; then
    echo -e "${GREEN}✓ uv found at $UV_BIN${NC}"
else
    echo -e "${YELLOW}uv not found. Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Determine installed location
    if [ -f "$HOME/.local/bin/uv" ]; then
        UV_BIN="$HOME/.local/bin/uv"
    elif [ -f "$HOME/.cargo/bin/uv" ]; then
        UV_BIN="$HOME/.cargo/bin/uv"
    fi

    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    echo -e "${GREEN}✓ uv installed at $UV_BIN${NC}"
fi

# Export uv path for subsequent uses in this session
export PATH="$(dirname "$UV_BIN"):$PATH"

# Step 2: Install Python dependencies
echo ""
echo "Step 2: Installing Python dependencies..."
cd "$PROJECT_ROOT/mcp_server"
uv sync
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Step 3: Verify installation
echo ""
echo "Step 3: Verifying installation..."
uv run python -c "import mcp_server; print('✓ MCP server module loads correctly')"

# Step 4: Ruby plugin installation guidance
echo ""
echo "=========================================="
echo "Step 4: Ruby SketchUp Plugin Installation"
echo "=========================================="
echo ""
echo "The Ruby SketchUp plugin needs to be installed manually."
echo ""
echo "1. Find SketchUp's Plugins folder:"
echo "   - macOS: ~/Library/Application Support/SketchUp/SketchUp 2024/SketchUp/Plugins/"
echo "   - Windows: C:\\Users\\YourName\\AppData\\Roaming\\SketchUp\\SketchUp 2024\\SketchUp\\Plugins\\"
echo ""
echo "2. Copy the 'su_bridge' folder to the Plugins folder:"
echo "   cp -r $PROJECT_ROOT/su_bridge ~/Library/Application\\ Support/SketchUp/SketchUp\\ 2024/SketchUp/Plugins/"
echo ""
echo "3. Restart SketchUp"
echo ""
echo "4. In SketchUp Ruby Console, run:"
echo "   load '$PROJECT_ROOT/su_bridge/lib/su_bridge.rb'"
echo "   SuBridge.start"
echo ""

# Step 5: Summary
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "To use the plugin in Claude Code:"
echo "1. Open Claude Code in this project directory"
echo "2. The MCP server will start automatically"
echo "3. In SketchUp, make sure SuBridge is running"
echo ""
echo "To update in the future:"
echo "   git pull && ./setup.sh"
echo ""
echo "NOTE: If MCP server fails to start in Claude Code, try:"
echo "   - Restart Claude Code"
echo "   - Ensure 'uv' is in your shell PATH (add to ~/.zshrc if needed)"
echo ""
