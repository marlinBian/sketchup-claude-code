# Quickstart

This project is not yet a finished designer product. The current quickstart is
for validating the local development build.

## 1. Create a Design Project

From an installed package:

```bash
sketchup-agent init ~/Design/my-bathroom --template bathroom
cd ~/Design/my-bathroom
```

From a source checkout while developing:

```bash
cd mcp_server
uv run --extra dev sketchup-agent init ~/Design/my-bathroom \
  --template bathroom --force
cd ~/Design/my-bathroom
```

The project directory now owns `design_model.json` and `design_rules.json`.

## 2. Start SketchUp Bridge

Install the Ruby bridge into SketchUp, then run this in the SketchUp Ruby
Console:

```ruby
load 'su_bridge/lib/su_bridge.rb'
SuBridge.start
```

The bridge is ready when `/tmp/su_bridge.sock` exists.

## 3. Start an Agent CLI

Open the design project directory, not the source repository:

```bash
claude
```

or:

```bash
codex
```

## 4. Try the Bathroom Slice

```text
Plan and execute a 2m x 1.8m bathroom with toilet, sink, door, mirror, basic
light, and clearance check.
```

Current MCP tools for this slice:

- `plan_bathroom`: creates structured project state and a bridge operation trace
  without requiring SketchUp.
- `execute_bathroom_plan`: plans the same bathroom and sends the trace to the
  SketchUp bridge.

## 5. Try a Simple Prompt

English:

```text
Create a 4m x 5m living room with 2.4m ceiling height.
```

Chinese sample prompt:

```text
创建一个 4 米 x 5 米的客厅，层高 2.4 米。
```

Chinese prompts are supported as user input examples, while product code and
public repository instructions remain English-first.

## Current Target Slice

The current product milestone is a bathroom workflow:

```text
Create a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light,
and clearance check.
```

The harness now generates structured project state, validates clearances, sends
operations to SketchUp, and keeps `design_model.json` as the source of truth.
