# Quickstart

This project is not yet a finished designer product. The current quickstart is
for validating the local development build.

## 1. Start SketchUp Bridge

Install the Ruby bridge into SketchUp, then run this in the SketchUp Ruby
Console:

```ruby
load 'su_bridge/lib/su_bridge.rb'
SuBridge.start
```

The bridge is ready when `/tmp/su_bridge.sock` exists.

## 2. Start an Agent CLI

Open a design project directory, not the source repository:

```bash
mkdir -p ~/Design/my-room
cd ~/Design/my-room
claude
```

or:

```bash
mkdir -p ~/Design/my-room
cd ~/Design/my-room
codex
```

## 3. Try a Simple Prompt

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

The next product milestone is a bathroom workflow:

```text
Create a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light,
and clearance check.
```

The harness should generate structured project state, validate clearances, send
operations to SketchUp, and keep `design_model.json` as the source of truth.
