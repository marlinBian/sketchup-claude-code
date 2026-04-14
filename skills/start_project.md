# Start Project - Interactive Design Initiation

## Purpose

When user says "开始新项目" (start new project), Claude should initiate an interactive guided workflow to understand the design requirements before creating anything.

## Trigger

- "开始新项目"
- "新项目"
- "start a new design"
- "我想开始一个新设计"

---

## Interactive Flow

### Step 1: Project Name

**Ask**: "你的项目叫什么名字？" (What should we call this project?)

**Options**:
- If user provides a name → use it
- If user says "随便" or doesn't know → suggest "我的新家" or ask for context

**Example response**: "叫'老公房改造'吧"

---

### Step 2: Room Dimensions

**Ask**: "房间有多大？长和宽各是多少？" (What are the room dimensions?)

**Parse**:
- "5米 x 4米" → [5000, 4000, 0] in mm
- "5米长，4米宽" → [5000, 4000, 0]
- "大概20平米" → estimate reasonable proportions, ask for clarification

**If user is unsure**: "一般卧室15-20平米，客厅20-30平米，你的房间是什么用途？"

---

### Step 3: Style Preference

**Ask**: "喜欢什么风格？让我给你介绍几种：" (What style do you prefer? Let me show you some options:)

**Show style options** (reference skills/styles.md):

| 风格 | 中文名 | 描述 | 适合 |
|------|--------|------|------|
| Japandi | 奶油风 | 暖暖的奶油色+浅木色，温馨舒适 | 小户型、喜欢温暖感 |
| Industrial | 工业风 | 混凝土+黑色金属，个性酷感 | 年轻人、Loft |
| Scandinavian | 北欧风 | 纯白+木色，简约干净 | 喜欢简洁 |
| Mediterranean | 地中海 | 白墙+蓝色点缀，清爽度假 | 热带地区 |
| Bohemian | 波西米亚 | 彩色+异域图案，自由随性 | 追求个性 |
| Minimalist | 现代极简 | 高级灰+黄铜，高雅品质 | 追求品质 |

**If user can't decide**: "要不我先按奶油风来，后面可以随时换？"

**Example response**: "奶油风吧，暖暖的比较舒服"

---

### Step 4: Primary Requirements

**Ask**: "有什么特别的需求吗？" (Any special requirements?)

**Common responses to recognize**:

| User says | Interpret as |
|-----------|-------------|
| "要能坐6个人" | Large dining table needed |
| "需要很多收纳" | Add storage cabinets/shelves |
| "光线要好" | Large windows, good lighting placement |
| "养宠物" | Pet-friendly materials, durable flooring |
| "有小孩" | Child-safe, durable materials |
| "工作需求" | Home office setup, desk area |

**Record all requirements** for later fulfillment.

---

### Step 5: Create Project Structure

After gathering info, automatically:

1. **Create directory structure**:
```
designs/{project_name}/
├── v0.1_draft/
│   ├── metadata.json
│   └── snapshots/
└── exports/
```

2. **Initialize model**:
   - Create room bounds from dimensions
   - Create walls with standard height (2400mm)
   - Apply default floor and wall colors based on style

3. **Report back**:
   "项目初始化完成！已经帮你画好了 [尺寸] 的房间，墙面色调是 [风格色]。现在可以开始添置家具了！"

---

## Implementation Notes

### For Claude

When user triggers start-project:

1. **Do NOT immediately start creating walls**
2. **Ask questions one by one** in natural conversation flow
3. **Wait for user response** after each question
4. **Remember the context** across all questions
5. **Provide suggestions** if user seems uncertain

### Parameter Collection

Collect these parameters:
- `project_name`: string
- `room_width`: number (mm)
- `room_depth`: number (mm)
- `room_height`: number (mm, default 2400)
- `style`: string (from style presets)
- `requirements`: string[] (list of requirements)

### Error Handling

| Situation | Response |
|-----------|----------|
| User provides unclear dimensions | "能告诉我大概几米吗？比如'5米长4米宽'" |
| User doesn't know style | Show visual examples, ask "更喜欢暖暖的感觉还是酷酷的？" |
| User changes mind mid-flow | "没问题，我们重新开始" - restart flow |

---

## Example Conversation

**User**: 开始新项目

**Claude**: 好的！让我们开始一个新设计。首先，**你的项目叫什么名字？** (比如"老公房改造"、"新家设计"等)

**User**: 老公房改造

**Claude**: 好的，"老公房改造"！接下来，**房间有多大？** 长和宽各是多少？可以说"5米 x 4米"这样。

**User**: 5米长4米宽，层高2米8

**Claude**: 明白了！5米 x 4米，2米8的层高。现在，**喜欢什么风格吗？** 让我给你介绍几种：
- 🧈 **奶油风** — 暖暖的，很温馨
- 🏭 **工业风** — 酷酷的混凝土+金属
- ❄️ **北欧风** — 干净简约的白+木
- 🌊 **地中海** — 白色+蓝色点缀
- 🎨 **波西米亚** — 彩色异域风
- ✨ **现代极简** — 高级灰+黄铜

**User**: 喜欢奶油风，暖暖的比较舒服

**Claude**: 很好的选择！最后，**有什么特别需求吗？** 比如"要坐6人"、"需要很多收纳"之类的。

**User**: 餐桌要能坐6个人，我在家办公需要书桌

**Claude**: 收到！老公房改造，5x4米，奶油风，需要6人餐桌和办公区。

正在初始化项目...

✅ **项目初始化完成！**
- 房间尺寸：5米 x 4米 x 2.8米
- 风格：奶油风（暖白色墙面 + 浅木地板）
- 已记录需求：6人餐桌、办公区

现在可以说"放一个6人餐桌"或"帮我加个书桌"，开始布置吧！

---

## Skills Integration

This guide should be loaded when user initiates a project. It references:
- `skills/styles.md` for style descriptions
- `skills/natural_commands.md` for follow-up command parsing
- `designs/` directory structure for project organization
