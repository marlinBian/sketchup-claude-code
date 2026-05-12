# Designer Manual

This manual is for interior designers and spatial designers who want to use
SketchUp through natural language. You do not need to clone this repository or
open a code editor for normal design work.

The current product is an early 1.0 release. It is useful for structured project
setup, SketchUp bridge installation, simple room generation, bathroom planning,
component-aware placement, validation, and first-pass floor-plan import.

Chinese manual: [docs/zh/DESIGNER_MANUAL.md](docs/zh/DESIGNER_MANUAL.md)

## What You Use It For

Use SketchUp Agent Harness when you want to say things like:

```text
Create a 2m x 1.8m bathroom with a toilet, sink, door, mirror, basic light,
and clearance check.
```

or:

```text
Import this floor plan image into the project and build an editable SketchUp
model from it.
```

The harness keeps a structured design record beside your SketchUp model. That
record lets the agent inspect, revise, validate, and rebuild the model instead
of only guessing from a screenshot.

## One-Paste Setup On macOS

Before running this, install:

- SketchUp
- Claude CLI or Codex CLI
- Python 3

Quit SketchUp first. Then paste this into Terminal. Change `2024` if your
SketchUp version is different.

```bash
python3 -m pip install --user --upgrade \
  "https://github.com/marlinBian/sketchup-agent-harness/releases/download/v1.0.0/sketchup_agent_harness_mcp-1.0.0-py3-none-any.whl"
export PATH="$(python3 -m site --user-base)/bin:$PATH"
sketchup-agent profile-init
sketchup-agent install-bridge --sketchup-version 2024 --force
mkdir -p "$HOME/Design/sketchup-agent-projects/my-first-room"
sketchup-agent init "$HOME/Design/sketchup-agent-projects/my-first-room" \
  --template empty --force
cd "$HOME/Design/sketchup-agent-projects/my-first-room"
```

Then launch SketchUp through a model window:

```bash
sketchup-agent launch-bridge --sketchup-version 2024 --suppress-update-check
```

When SketchUp opens, start your agent CLI in the design project folder:

```bash
codex
```

or:

```bash
claude
```

## First Conversation

Start with one clear design request:

```text
Create a 4m x 5m living room with a 2.4m ceiling height.
```

For the current bathroom slice:

```text
Plan and execute a 2m x 1.8m bathroom with toilet, sink, door, mirror, basic
light, and clearance check.
```

For an existing plan:

```text
This is my floor plan. Import it into this project and build an editable
SketchUp model from it.
```

The first imported model is a working draft, not a verified survey. You should
expect to correct scale, openings, wall thickness, room boundaries, and ambiguous
areas during design.

## Daily Workflow

1. Open Terminal.
2. Go to your design project folder.
3. Launch the SketchUp bridge.
4. Start Codex or Claude in that same folder.
5. Describe what you want changed.

Example:

```bash
cd "$HOME/Design/sketchup-agent-projects/my-first-room"
sketchup-agent launch-bridge --sketchup-version 2024 --suppress-update-check
codex
```

Then talk naturally:

```text
Make the living room feel more open. Keep the sofa area, but widen the path to
the balcony.
```

or:

```text
Check whether the bathroom fixtures have enough front clearance.
```

## Importing A Floor Plan

You can import:

- DWG
- DXF
- PDF
- image floor plan
- scan
- photo

For image or PDF imports, give the agent the file and any useful approximate
size:

```text
Import ~/Downloads/floorplan.jpg. The full plan is about 7200mm wide.
Generate an editable model directly, then show me what needs review.
```

The agent should:

- save the source under `imports/`
- generate working truth in `design_model.json`
- create SketchUp walls, openings, and spaces where possible
- keep source evidence for later repair
- avoid asking you to approve every detected number before it creates the first
  model

If something is wrong, correct the result in normal design language:

```text
The bedroom door should be on the corridor side, not inside the bedroom wall.
Recheck that area against the source image and repair the model.
```

or:

```text
The lower-right area is outside the apartment boundary. Do not enclose it as an
interior space.
```

The correction should become project-local memory for this design project, not a
global product rule.

## What The Project Folder Contains

You normally do not need to edit these files, but they explain how the project
stays editable:

- `design_model.json`: current structured design truth
- `design_rules.json`: project rules and preferences
- `component_library.json`: reusable project components
- `assets.lock.json`: assets used by the project
- `imports/`: source files and import evidence
- `snapshots/`: review screenshots and rendering records
- `.agents/skills/`: Codex runtime skills for this project
- `.claude/skills/`: Claude runtime skills for this project

Do not copy dynamic skills from one client project into another project unless
you intentionally want to reuse that project-specific interpretation.

## Saving Versions

Ask the agent to save important milestones:

```text
Save this as the first imported layout before we start redesigning.
```

Then later:

```text
Compare the current layout with the first imported layout.
```

or:

```text
Restore the version before we changed the balcony.
```

## Common Problems

### `sketchup-agent: command not found`

Run:

```bash
export PATH="$(python3 -m site --user-base)/bin:$PATH"
```

Then try:

```bash
sketchup-agent --help
```

### SketchUp opens but the agent cannot connect

Use:

```bash
sketchup-agent doctor . --sketchup-version 2024
sketchup-agent launch-bridge --sketchup-version 2024 --suppress-update-check
```

Make sure SketchUp is in a model window, not only the welcome screen.

### The imported model is not accurate

That is expected for the first pass. Tell the agent exactly what is wrong and
ask it to recheck against the source. Good corrections mention the area and the
source relationship:

```text
In the top-right room, the window should be on the exterior wall. Recheck the
source and repair only that area.
```

### A project starts behaving strangely after many corrections

Ask the agent to inspect project memory:

```text
Review the project-local dynamic skills and import evidence. Tell me which
source-specific assumptions are currently active.
```

## Current Limits

- Imported drawings produce editable working models, not survey-grade results.
- Some generated geometry is still placeholder-like.
- Rich component libraries are not bundled yet.
- Live SketchUp execution requires the bridge to be installed and loaded.
- The tool works best when you keep one design project per folder.

## Privacy

Imported plans and source files are stored in your local project folder. Do not
share a project folder publicly if it contains client drawings, private photos,
or project-specific dynamic runtime skills.
