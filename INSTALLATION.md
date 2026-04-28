# 完整安装指南

本文档面向需要自定义配置或为项目做贡献的开发者。

## 系统要求

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| SketchUp | 2021+ | 用于 3D 建模 |
| Python | 3.11+ | MCP 服务器运行环境 |
| Ruby | 3.2+ | SketchUp 插件运行环境 |
| Git | 任意版本 | 代码版本管理 |

## 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/marlinBian/sketchup-agent-harness.git
cd sketchup-agent-harness
```

### 2. 运行安装脚本

```bash
./setup.sh
```

脚本会自动：
- 检查并安装 `uv` (Python 包管理器)
- 安装 Python 依赖
- 验证安装

### 3. 安装 SketchUp 插件

**macOS:**

```bash
# 创建插件目录（如果不存在）
mkdir -p ~/Library/Application\ Support/SketchUp/SketchUp\ 2024/SketchUp/Plugins/

# 复制插件
cp -r su_bridge ~/Library/Application\ Support/SketchUp/SketchUp\ 2024/SketchUp/Plugins/
```

**Windows:**

```powershell
# 复制插件到 AppData
cp -r su_bridge "$env:APPDATA\SketchUp\SketchUp 2024\SketchUp\Plugins\"
```

### 4. 启动 SketchUp 插件

1. 重启 SketchUp
2. 打开 Ruby 控制台 (Window > Ruby Console)
3. 输入：

```ruby
load 'su_bridge/lib/su_bridge.rb'
SuBridge.start
```

### 5. 启动 MCP 服务器

```bash
cd mcp_server
uv run python -m mcp_server.server
```

---

## 目录结构

```
sketchup-agent-harness/
├── mcp_server/            # Python MCP 服务器
│   ├── mcp_server/
│   │   ├── server.py     # FastMCP 入口
│   │   ├── tools/        # MCP 工具
│   │   └── resources/     # 资源定义
│   └── tests/            # 测试
├── su_bridge/            # Ruby SketchUp 插件
│   ├── lib/su_bridge/   # 核心代码
│   └── spec/             # 测试
├── skills/               # LLM 指令集
├── specs/                # 协议定义
└── designs/              # 设计项目（用户数据）
```

---

## 开发测试

### Python 测试

```bash
cd mcp_server
uv run pytest tests/ -v
```

### Ruby 测试

```bash
cd su_bridge
bundle exec rspec spec/
```

### 语法检查

```bash
# Ruby
ruby -c su_bridge/lib/su_bridge.rb

# Python
python3 -m py_compile mcp_server/mcp_server/server.py
```

---

## 故障排查

### MCP 服务器无法启动

```bash
# 检查 uv 是否可用
which uv

# 手动安装依赖
cd mcp_server
uv sync
uv run python -m mcp_server.server
```

### SketchUp 插件加载失败

```ruby
# 在 Ruby 控制台中检查错误
load 'su_bridge/lib/su_bridge.rb'

# 查看版本
SuBridge::VERSION
```

### Socket 连接被拒绝

- 确保 SketchUp 中的 `SuBridge.start` 已执行
- 检查 `/tmp/su_bridge.sock` 是否存在

---

## 更新插件

```bash
git pull
./setup.sh
```

重启 SketchUp 和 MCP 服务器。
