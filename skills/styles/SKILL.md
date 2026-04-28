# Design Style Presets

## Purpose

Map designer style language to supported `apply_style` presets and simple color
guidance. Style presets affect presentation; they do not change room geometry or
validate layout.

## Supported Style IDs

| Style ID | English Alias | Chinese Alias |
| --- | --- | --- |
| `japandi_cream` | Japandi cream | 奶油风 |
| `modern_industrial` | modern industrial | 工业风 |
| `scandinavian` | Scandinavian | 北欧风 |
| `mediterranean` | Mediterranean | 地中海风 |
| `bohemian` | Bohemian | 波西米亚 |
| `contemporary_minimalist` | contemporary minimalist | 现代极简 |

## Tool Use

Apply a full style preset:

```python
apply_style(style_name="scandinavian")
```

Apply a direct material color to known entities:

```python
apply_material(entity_ids=["entity_wall_001"], color="#F5F0E8")
```

## Color Guidance

| Style ID | Base Color | Accent Direction |
| --- | --- | --- |
| `japandi_cream` | warm cream | light wood, linen, terracotta |
| `modern_industrial` | concrete gray | black metal, dark wood |
| `scandinavian` | pure white | pale gray, light oak |
| `mediterranean` | whitewash | terracotta, blue, olive |
| `bohemian` | cream | teal, mustard, patterned textiles |
| `contemporary_minimalist` | warm white | greige, charcoal, brass |

## Chinese Prompt Examples

```text
把这个方案换成北欧风。
```

```text
墙面用奶油风的暖白色。
```

## Guardrails

- Do not invent new style IDs without updating the implementation.
- Do not claim that style application chooses furniture automatically.
- Do not use style as a substitute for clearance or component validation.
- Keep public style IDs and implementation names English-first.
