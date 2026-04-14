# Natural Command Mapping

## Purpose

This guide helps Claude understand natural, spoken Chinese commands and translate them into tool calls. It handles ambiguity, colloquialisms, and partial instructions.

---

## Color & Material Commands

### Wall/Floor Coloring

| Spoken Command | Interpretation | Tool Call |
|----------------|---------------|-----------|
| "把墙涂成白色" | Apply white paint to all walls | `apply_material(entity_ids: all_walls, color: "#FFFFFF")` |
| "墙换成米色" | Apply beige to walls | `apply_material(entity_ids: all_walls, color: matching_beige_from_style)` |
| "把这里涂白" | Apply white to selected/hovered area | `apply_material(entity_ids: context_selected, color: "#FFFFFF")` |
| "地板换成木色" | Apply wood tone to floor | `apply_material(entity_ids: floor, color: style_wood_color)` |
| "墙面刷新一下" | Refresh wall color to default style color | `apply_material(entity_ids: all_walls, color: style_default_wall)` |
| "沙发要灰色的" | Change sofa color to gray | `apply_material(entity_ids: selected_sofa, color: "#808080")` |

### Style Color Matching

When user says "用这个风格的颜色":

| User specifies | Action |
|----------------|--------|
| "奶油风的白色" | Use `#F5F0E8` from Japandi preset |
| "工业风的黑" | Use `#2A2A2A` from Industrial preset |
| "北欧风的白" | Use `#FFFFFF` from Scandinavian preset |
| "地中海的蓝" | Use `#4A90A4` from Mediterranean preset |

---

## Furniture Placement

### Basic Placement

| Spoken Command | Interpretation | Tool Call |
|----------------|---------------|-----------|
| "放一个沙发" | Place default sofa | `place_component("沙发", position: auto_center)` |
| "放一个双人沙发" | Place double sofa | `place_component("双人沙发")` |
| "帮我放个餐桌" | Place dining table | `place_component("餐桌")` |
| "加一把椅子" | Add a chair | `place_component("餐椅")` |

### Positioned Placement

| Spoken Command | Interpretation | Tool Call |
|----------------|---------------|-----------|
| "把餐桌放北墙边" | Place table against north wall | `place_component("餐桌", position: north_wall_aligned)` |
| "沙发靠窗放" | Sofa near window | `place_component("沙发", position: near_window)` |
| "书桌放角落" | Desk in corner | `place_component("书桌", position: corner)` |
| "床头柜放床右边" | Nightstand to right of bed | `place_component("床头柜", position: bed_right)` |

### Alignment Keywords

| Keyword | Meaning | Behavior |
|---------|---------|----------|
| "贴着" / "靠" | Against | Align to wall with min clearance |
| "中间" | Center | Place at room center |
| "角落" | Corner | Place at nearest corner |
| "窗边" | Near window | Position based on window location |

---

## View & Capture Commands

### Simple Capture

| Spoken Command | Interpretation | Tool Call |
|----------------|---------------|-----------|
| "帮我拍几张照" | Capture from multiple presets | Capture all views |
| "拍个照" | Single capture current view | `capture_design()` |
| "截图" | Screenshot | `capture_design()` |

### Specific Views

| Spoken Command | View Preset |
|----------------|-------------|
| "来个全景" | `panoramic` |
| "看看客厅" | `living_room_birdseye` |
| "主卧什么样子" | `master_bedroom` |
| "餐厅视角" | `dining_area` |
| "从门口看" | `front_entrance` |

### Multi-Capture

"帮我拍几张照" triggers:
```
capture_design(view_preset: "panoramic")
capture_design(view_preset: "living_room_birdseye")
capture_design(view_preset: "dining_area")
```

---

## Undo & Modification

| Spoken Command | Interpretation |
|----------------|----------------|
| "撤销" | Undo last operation |
| "取消" / "算了" | Undo and cancel current action |
| "重做" | Redo last undone operation |
| "删掉这个" | Delete selected entity |
| "往左一点" | Move entity -100mm in X |
| "转一下" | Rotate entity 90° |
| "大一点" | Scale entity 1.1x |
| "小一点" | Scale entity 0.9x |

---

## Project Flow Commands

| Spoken Command | Interpretation |
|----------------|----------------|
| "开始新项目" | Trigger start_project guide |
| "换个风格" | Re-apply style with new preset |
| "帮我生成汇报" | Generate client report |
| "导出方案" | Export to PDF/image |
| "保存一下" | Save version snapshot |

---

## Ambiguity Handling

### When Command is Unclear

**Ask for clarification**:
- "你想把这个墙涂成什么颜色？" (What color for the wall?)
- "沙发放哪里？靠墙还是中间？" (Where to place the sofa?)
- "你说的是哪个区域？" (Which area do you mean?)

### Context Tracking

Remember:
- Current project style
- Recently mentioned items
- Last placed furniture

If user says "换这个颜色" but didn't specify what, apply to most recently mentioned/modified entity.

### Fallback Behavior

If command cannot be understood:
1. Ask one clarifying question
2. Offer two most likely interpretations
3. If still unclear, describe what the system understands and ask "对吗？"

---

## Chinese Color Names Mapping

| Spoken | Hex | Context |
|--------|-----|---------|
| "白色" | `#FFFFFF` | Walls, ceilings |
| "米色" | `#F5F0E8` | Warm off-white |
| "灰色" | `#808080` | Neutral gray |
| "浅灰" | `#D3D3D3` | Soft gray |
| "木色" | `#C4A77D` | Oak wood |
| "黑色" | `#1A1A1A` | Accents |
| "蓝色" | `#4A90A4` | Mediterranean |
| "绿色" | `#9CAF88` | Sage/plants |
| "粉色" | `#D4A5A5` | Dusty rose |
| "棕色" | `#8B5A2B` | Wood/dark |
| "黄色" | `#C9A27` | Mustard |

---

## Style Application

### Applying Full Style

"把这个方案换成北欧风"

1. Query current entities
2. Apply style colors to:
   - Walls → scandi_white
   - Floor → scandi_oak_light
   - Furniture materials → style default
3. Keep layout intact

### Partial Style Change

"墙面色调保留，只换地板"

1. Apply only floor material change
2. Keep wall colors unchanged
