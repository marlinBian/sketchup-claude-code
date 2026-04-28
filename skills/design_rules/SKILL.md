# Design Rules Skill

## Purpose

Read and update project-local design preferences in `design_rules.json`.

Use this skill when the designer wants future planning to follow a preferred
clearance, dimension, or ergonomic convention.

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

## User Prompt Examples

English:

```text
Use 700 mm as the minimum front clearance for toilets in this project.
```

Chinese:

```text
这个项目里马桶前方最小通行距离按 700 毫米来。
```

## Result Handling

After changing a rule:

- confirm the rule set, clearance name, and millimeter value
- say that future planning uses the project rule
- rerun the relevant planner when the user wants geometry regenerated
- report validation failures instead of silently relaxing the rule

## Guardrails

- Do not present ergonomic preferences as legal code compliance.
- Do not write global user preferences into project files unless the user asked
  for this project to adopt them.
- Keep schema keys and rule names English-first.
