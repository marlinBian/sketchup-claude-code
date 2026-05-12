# SketchUp Agent Harness

让设计师通过 Claude CLI 或 Codex CLI，用自然语言控制 SketchUp，创建、检查、
导入和迭代可编辑的设计模型。

## 项目定位

SketchUp Agent Harness 不是单一的 Claude 插件。Claude 和 Codex 都只是入口；
共享核心是 MCP server、SketchUp Ruby bridge、结构化设计模型、组件元数据、
设计规则和 runtime skills。

设计师正常使用时不需要 clone 本仓库，也不需要编辑源码。推荐方式是在自己的
设计项目目录中运行 Claude 或 Codex，让 agent 通过本工具连接 SketchUp。

## 快速入口

面向设计师的完整中文手册：

- [设计师使用手册](./docs/zh/DESIGNER_MANUAL.md)

英文主文档：

- [Designer Manual](./DESIGNER_MANUAL.md)

## 当前能力

- 初始化独立设计项目目录
- 安装 SketchUp Ruby bridge
- 在项目中安装 Claude / Codex runtime skills
- 通过自然语言生成简单空间和卫生间布局
- 导入 DWG、DXF、PDF、图片、扫描件或照片作为第一版可编辑模型
- 在 `design_model.json` 中保存结构化设计 truth
- 保存 source evidence、截图、版本和项目规则

## 更多文档

- [安装说明](./INSTALLATION.md)
- [快速开始](./QUICKSTART.md)
- [设计师指南](./DESIGNER_GUIDE.md)
- [能力地图](./docs/product/capability-map.md)
- [开发文档](./DEVELOPMENT.md)

## 当前限制

1.0 版本仍是早期版本。图纸导入生成的是可编辑工作模型，不是测绘级结果；
真实组件库、复杂碰撞检查和更稳定的图纸识别仍在迭代中。
