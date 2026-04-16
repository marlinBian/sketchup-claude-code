# 快速入门指南

欢迎使用 SCC (SketchUp-Claude-Code)！本指南帮助你快速开始室内设计。

---

## 第一步：安装 SCC 插件

### 1.1 添加插件市场

在 Claude Code 中执行：

```
/plugin marketplace add https://github.com/marlinBian/sketchup-claude-code
```

### 1.2 安装插件

```
/plugin install sketchup-claude-code
```

### 1.3 重启 Claude Code

关闭并重新打开 Claude Code，使插件生效。

### 1.4 验证安装

输入 `/mcp`，确认看到 `sketchup-mcp · ✔ connected`。

---

## 第二步：安装 SketchUp 插件

### 2.1 安装 SketchUp 插件（仅需一次）

在终端执行：

```bash
# 创建插件目录（如果不存在）
mkdir -p ~/Library/Application\ Support/SketchUp/SketchUp\ 2024/SketchUp/Plugins/

# 复制插件
cp -r ~/.claude-model/.claude-doubao/plugins/marketplaces/sketchup-claude-code/su_bridge ~/Library/Application\ Support/SketchUp/SketchUp\ 2024/SketchUp/Plugins/
```

### 2.2 启动 SketchUp

打开 SketchUp 应用程序。

### 2.3 启动 su_bridge 插件

在 SketchUp 的 **Ruby Console** 中输入：

```ruby
load "/Users/xu/Library/Application Support/SketchUp/SketchUp 2024/SketchUp/Plugins/su_bridge/lib/su_bridge.rb"
SuBridge.start
```

看到类似输出表示成功：
```
[su_bridge] Socket ready on /tmp/su_bridge.sock
[su_bridge] Server started on /tmp/su_bridge.sock
```

---

## 第三步：开始设计

在 Claude Code 中用自然语言描述你的设计需求：

### 创建房间

| 你说的话 | 系统做的 |
|---------|---------|
| "创建一个 5 米 x 4 米的客厅" | 绘制墙体 |
| "用北欧风格" | 应用北欧风配色和材质 |
| "放一个三人沙发在客厅中央" | 搜索并放置沙发 |
| "餐桌放在北墙边" | 自动对齐到北墙 |

### 常用指令

| 你说的话 | 系统做的 |
|---------|---------|
| "创建一面 4m x 3m 的墙" | 绘制墙体 |
| "把墙涂成白色" | 应用白色涂料 |
| "放一盏吊灯在餐桌上方" | 放置灯具 |
| "帮我拍张全景图" | 拍摄俯瞰图 |
| "把餐桌往左移 50 厘米" | 调整位置 |
| "删除这把椅子" | 移除物品 |
| "应用现代极简风格" | 整体风格变换 |

### 风格选项

- **奶油风 (Japandi)** - 温暖的米色和木色
- **工业风 (Industrial)** - 深色金属和混凝土
- **北欧风 (Scandinavian)** - 浅木色和白色
- **地中海风 (Mediterranean)** - 蓝色和陶土色
- **波西米亚风 (Bohemian)** - 丰富纹理和色彩
- **现代极简 (Contemporary)** - 黑白灰为主

---

## 撤销操作

所有操作都可以撤销：

- 告诉 Claude "撤销" 来撤销上一步
- 连续撤销可以回到之前的状态

---

## 查看帮助

| 指令 | 功能 |
|------|------|
| `/mcp` | 查看 MCP 服务器状态 |
| `有什么风格可选？` | 查看可用风格 |
| `帮我生成汇报` | 创建客户报告 |

---

## 故障排查

### MCP 显示 ✘ failed

1. 重启 Claude Code
2. 检查 `/mcp` 确认 sketchup-mcp 显示 ✔ connected

### SketchUp 操作失败

1. 确认 SketchUp 已打开
2. 确认 Ruby Console 中 su_bridge 已启动
3. 确认看到 `[su_bridge] Server started` 消息

### 其他问题

重启 SketchUp 和 Claude Code 通常可以解决大部分问题。
