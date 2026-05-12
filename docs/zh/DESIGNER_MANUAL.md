# 设计师使用手册

这份手册面向室内设计师和空间设计师，不面向程序员。正常使用时，你不需要
clone 这个源码仓库，也不需要打开代码编辑器。

当前产品是早期 1.0 版本，适合做项目初始化、SketchUp bridge 安装、简单空间
生成、卫生间规划、基于组件的摆放、规则检查，以及从户型图/图纸生成第一版
可编辑模型。

英文主文档：[../../DESIGNER_MANUAL.md](../../DESIGNER_MANUAL.md)

## 它能帮你做什么

你可以直接说：

```text
创建一个 2 米 x 1.8 米的卫生间，包含马桶、洗手台、门、镜子、基础照明，
并检查通行距离。
```

也可以说：

```text
这是我的户型图，把它导入到当前项目中，并生成一个可继续调整的 SketchUp 模型。
```

这个工具会在 SketchUp 模型旁边保留一份结构化设计记录。这样 agent 后续可以
检查、修改、验证和重建模型，而不是只看截图猜。

## macOS 一段命令安装

先安装：

- SketchUp
- Claude CLI 或 Codex CLI
- Python 3

先退出 SketchUp。然后把下面这段粘贴到终端里。你的 SketchUp 如果不是 2024
版，把命令里的 `2024` 改成你的版本。

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

然后用模型窗口启动 SketchUp：

```bash
sketchup-agent launch-bridge --sketchup-version 2024 --suppress-update-check
```

SketchUp 打开后，在这个设计项目目录里启动 agent：

```bash
codex
```

或：

```bash
claude
```

## 第一句话怎么说

可以先从一个明确任务开始：

```text
创建一个 4 米 x 5 米的客厅，层高 2.4 米。
```

当前比较稳定的卫生间切片：

```text
规划并执行一个 2 米 x 1.8 米的卫生间，包含马桶、洗手台、门、镜子、基础照明，
并检查通行距离。
```

如果已经有户型图：

```text
这是我的户型图。导入到当前项目中，并生成一个可编辑的 SketchUp 模型。
```

第一版导入模型是工作草稿，不是测绘级结果。你应该预期后续会继续修正比例、
开口、墙厚、房间边界和不明确的位置。

## 日常使用流程

1. 打开终端。
2. 进入你的设计项目目录。
3. 启动 SketchUp bridge。
4. 在同一个目录里启动 Codex 或 Claude。
5. 直接描述你想怎么改。

示例：

```bash
cd "$HOME/Design/sketchup-agent-projects/my-first-room"
sketchup-agent launch-bridge --sketchup-version 2024 --suppress-update-check
codex
```

然后自然表达：

```text
让客厅更通透。保留沙发区，但把去阳台的动线放宽。
```

或者：

```text
检查一下卫生间里的马桶和洗手台前方距离够不够。
```

## 导入户型图或图纸

可以导入：

- DWG
- DXF
- PDF
- 户型图图片
- 扫描件
- 照片

如果是图片或 PDF，最好提供一个大致尺寸：

```text
导入 ~/Downloads/floorplan.jpg。整张户型图大约 7200mm 宽。
先直接生成可编辑模型，然后告诉我哪些地方需要复查。
```

agent 应该：

- 把原始素材保存到 `imports/`
- 在 `design_model.json` 中生成工作真相
- 尽可能在 SketchUp 中生成墙、开口和空间
- 保存 source evidence，方便后续修复
- 不要在第一步就让你确认每个枯燥数字

如果有问题，直接用设计语言指出：

```text
卧室门应该在过道一侧，不应该跑到卧室墙里面。对照原始图重新检查这个区域，
只修这个区域。
```

或者：

```text
右下角那块是户型外部空间，不要把它封成室内空间。
```

这种纠正应该变成当前项目的局部记忆，而不是污染成所有项目的通用规则。

## 项目目录里有什么

正常情况下你不用手动改这些文件，但它们说明为什么模型可以持续编辑：

- `design_model.json`：当前结构化设计真相
- `design_rules.json`：项目规则和偏好
- `component_library.json`：项目可复用组件
- `assets.lock.json`：项目中实际使用的资产
- `imports/`：原始图纸、导入证据和解释
- `snapshots/`：截图、渲染和视觉审阅记录
- `.agents/skills/`：当前项目给 Codex 用的 runtime skills
- `.claude/skills/`：当前项目给 Claude 用的 runtime skills

不要随便把一个客户项目中生成的动态 skill 复制到另一个项目里，除非你明确想
复用那个项目的特定解释。

## 保存版本

重要节点可以让 agent 保存：

```text
把当前状态保存为第一版导入户型，之后开始重新设计。
```

之后可以说：

```text
对比当前方案和第一版导入户型。
```

或者：

```text
恢复到修改阳台之前的版本。
```

## 常见问题

### `sketchup-agent: command not found`

运行：

```bash
export PATH="$(python3 -m site --user-base)/bin:$PATH"
```

再试：

```bash
sketchup-agent --help
```

### SketchUp 打开了，但 agent 连不上

运行：

```bash
sketchup-agent doctor . --sketchup-version 2024
sketchup-agent launch-bridge --sketchup-version 2024 --suppress-update-check
```

确认 SketchUp 已经进入模型窗口，而不是停在欢迎页。

### 导入模型不准

第一版不准是正常的。你应该告诉 agent 哪个位置错了，并要求它对照原始素材
复查。好的修正方式是说明区域和原图关系：

```text
右上角房间的窗应该在外墙上。对照原始图复查并只修这个区域。
```

### 多次修正后项目行为变奇怪

让 agent 检查项目局部记忆：

```text
检查当前项目里的动态 runtime skill 和导入 evidence，告诉我现在有哪些
source-specific 假设在生效。
```

## 当前限制

- 图纸导入生成的是可编辑工作模型，不是测绘级结果。
- 部分几何体仍偏占位符。
- 真实组件库还需要继续积累。
- SketchUp 实时执行需要 bridge 已安装并加载。
- 最好一个设计项目对应一个文件夹。

## 隐私

导入的户型图和原始素材会保存在本地项目目录中。如果项目里包含客户图纸、
私人照片或项目动态 skill，不要直接公开分享整个项目文件夹。
