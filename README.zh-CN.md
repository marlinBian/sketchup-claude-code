# SketchUp Agent Harness

让室内设计师使用 Claude CLI 或 Codex CLI 通过自然语言在 SketchUp 中创建、检查和迭代 3D 模型。

---

## 项目定位

这个项目原名 `sketchup-claude-code`，正在迁移为 `sketchup-agent-harness`。
Claude 和 Codex 都只是入口，核心是共享的 MCP Server、SketchUp Ruby bridge、设计模型 JSON、组件规则和设计 workflow skills。

设计师不需要 clone 本仓库。正常使用路径应该是安装插件，然后在自己的设计项目目录中启动 Claude 或 Codex。

## 设计师安装（推荐方式）

### Claude CLI

```bash
# 1. 通过 Claude Code 安装插件
/plugin marketplace add https://github.com/marlinBian/sketchup-agent-harness
/plugin install sketchup-agent-harness

# 2. 复制 SketchUp 插件（一次性操作）
cp -r ~/.claude/plugins/sketchup-agent-harness/su_bridge ~/Library/Application\ Support/SketchUp/SketchUp\ 2024/SketchUp/Plugins/

# 3. 在 SketchUp Ruby 控制台运行一次
load '~/Library/Application Support/SketchUp/SketchUp 2024/SketchUp/Plugins/su_bridge/lib/su_bridge.rb'
SuBridge.start

# 4. 创建设计项目目录并开始
mkdir ~/Design/my-room && cd ~/Design/my-room
claude

# 5. 开始设计！
# "创建一个 4米 x 5米的客厅，层高 2.4米"
```

### Codex CLI

```bash
# 1. 添加插件 marketplace
codex plugin marketplace add marlinBian/sketchup-agent-harness

# 2. 进入设计项目目录
mkdir ~/Design/my-room && cd ~/Design/my-room
codex

# 3. 开始设计
# "创建一个 4米 x 5米的客厅，层高 2.4米"
```

---

## 快速开始

### 在 SketchUp 中加载插件

1. 确保 `su_bridge` 已复制到 SketchUp 插件目录
2. 重启 SketchUp
3. 在 SketchUp Ruby 控制台中运行：
   ```ruby
   SuBridge.start
   ```

### 开始设计

在 Claude CLI 或 Codex CLI 中切换到项目目录，然后说：
- "创建一个 4米 x 5米的客厅，层高 2.4米"
- "添加一套北欧风格的沙发"
- "在餐桌上方 1.2米 放置吊灯"

---

## 常用指令

| 指令 | 功能 |
|------|------|
| 开始新项目 | 初始化新设计 |
| 添加 [家具类型] | 放置家具 |
| 移动 [物体] 到 [位置] | 调整布局 |
| 应用 [风格名称] | 应用设计风格 |
| 帮我拍几张照 | 多角度截图 |

---

## 设计风格

- 奶油风（日式+北欧）
- 北欧风
- 工业风
- 地中海风
- 波西米亚风
- 现代极简

---

## 系统要求

- SketchUp 2021+
- Python 3.11+
- Ruby 3.2+

---

## 更多信息

- [设计师快速上手](./QUICKSTART.md) - 更详细的操作指南
- [完整安装指南](./INSTALLATION.md) - 开发者贡献指南
- [开发文档](./DEVELOPMENT.md) - 项目架构和技术细节
