# Designer Guide

SketchUp Agent Harness is intended to let designers work with SketchUp through
natural-language agent CLIs.

## Core Idea

You describe design intent. The harness turns that intent into structured
project state and SketchUp operations.

The important project files are expected to live in your design project
directory:

```text
my-design-project/
  design_model.json
  design_rules.json
  assets.lock.json
  model.skp
  snapshots/
```

## Example Requests

English:

```text
Create a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light,
and clearance check.
```

Chinese:

```text
创建一个 2 米 x 1.8 米的卫生间，包含马桶、洗手台、门、镜子、基础照明，并检查通行距离。
```

## Design Rules

Project-specific design rules should live in `design_rules.json`. These rules
can capture preferred clearances, fixture sizes, material preferences, or local
workflow conventions.

Rule precedence is:

1. built-in harness defaults
2. installed designer profile
3. project `design_rules.json`
4. explicit instruction in the current agent session

## Visual Output

Screenshots and generated renderings are review artifacts. They can guide design
decisions, but `design_model.json` remains the source of truth for the model.
