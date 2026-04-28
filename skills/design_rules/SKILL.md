# Design Rules Skill

## Purpose

Read and update project-local design preferences in `design_rules.json`.

Use this skill when the designer wants future planning to follow a preferred
clearance, dimension, or ergonomic convention.

Built-in rules may be merged with a designer profile when
`SKETCHUP_AGENT_DESIGN_RULES` points to a reusable design rules file. Project
`design_rules.json` has higher precedence than that profile.

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
- say that future planning uses the project rule
- rerun the relevant planner when the user wants geometry regenerated
- report validation failures instead of silently relaxing the rule

## Guardrails

- Do not present ergonomic preferences as legal code compliance.
- Do not write global user preferences into project files unless the user asked
  for this project to adopt them.
- Keep schema keys and rule names English-first.
- Store open-ended preferences as project preferences, not as schema keys.
