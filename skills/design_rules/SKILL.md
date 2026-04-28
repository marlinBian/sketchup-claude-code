# Design Rules Skill

## Purpose

Read and update project-local design preferences in `design_rules.json`.

Use this skill when the designer wants future planning to follow a preferred
clearance, dimension, or ergonomic convention.

Built-in rules may be merged with a designer profile when
`SKETCHUP_AGENT_DESIGN_RULES` points to a reusable design rules file. Project
`design_rules.json` has higher precedence than that profile.

Use project-local tools for preferences that should affect only the current
design project. Use designer-profile tools only when the designer explicitly
asks for a rule to become a reusable personal default for future projects.

## Tools

Read current rules:

```python
get_design_rules(project_path="<project-path>")
```

Set one clearance value in millimeters:

```python
set_design_clearance(
    project_path="<project-path>",
    rule_set="bathroom",
    clearance_name="toilet_front_clearance",
    value=700
)
```

Set one fixture dimension in millimeters:

```python
set_fixture_dimension(
    project_path="<project-path>",
    rule_set="bathroom",
    fixture_name="vanity_wall_600",
    width=500,
    depth=420,
    height=850
)
```

Set one free-form project preference:

```python
set_design_preference(
    project_path="<project-path>",
    preference_name="lighting_temperature",
    value="3000K"
)
```

Check or create the reusable designer profile:

```python
get_designer_profile_status()
init_designer_profile()
```

Set one reusable designer-profile value for future projects:

```python
set_designer_profile_clearance(
    rule_set="bathroom",
    clearance_name="toilet_front_clearance",
    value=700
)
```

```python
set_designer_profile_fixture_dimension(
    rule_set="bathroom",
    fixture_name="compact_vanity",
    width=500,
    depth=420,
    height=850
)
```

```python
set_designer_profile_preference(
    preference_name="lighting_temperature",
    value="3000K"
)
```

## User Prompt Examples

English:

```text
Use 700 mm as the minimum front clearance for toilets in this project.
```

```text
Use a 500 mm wide vanity as my default for this bathroom project.
```

Chinese:

```text
这个项目里马桶前方最小通行距离按 700 毫米来。
```

```text
这个卫生间项目默认使用 500 毫米宽的洗手台。
```

## Result Handling

After changing a rule:

- confirm the rule set, changed field, and millimeter value when spatial
  dimensions are involved
- say whether future planning uses the project rule or the reusable designer
  profile
- rerun the relevant planner when the user wants geometry regenerated
- report validation failures instead of silently relaxing the rule

## Guardrails

- Do not present ergonomic preferences as legal code compliance.
- Do not write reusable designer-profile preferences unless the designer clearly
  asked for a future-project default.
- Keep schema keys and rule names English-first.
- Store open-ended preferences as project preferences, not as schema keys.
