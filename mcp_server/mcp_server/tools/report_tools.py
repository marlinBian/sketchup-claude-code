"""Design report generation tools."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_design_report(
    project_name: str,
    project_dir: str = "./designs",
    output_format: str = "markdown",
) -> dict[str, Any]:
    """Generate a design report from captured snapshots and project metadata.

    Args:
        project_name: Name of the project
        project_dir: Base directory for designs
        output_format: Format for report (markdown, html)

    Returns:
        Dict with report_path and summary
    """
    project_path = Path(project_dir) / project_name

    if not project_path.exists():
        raise FileNotFoundError(f"Project not found: {project_path}")

    # Find latest version
    versions = sorted([d for d in project_path.iterdir() if d.is_dir() and d.name.startswith("v")])
    if not versions:
        raise FileNotFoundError(f"No versions found in {project_path}")

    latest_version = versions[-1]

    # Load metadata if exists
    metadata_path = latest_version / "metadata.json"
    metadata = {}
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)

    # Find snapshots
    snapshots = list(latest_version.glob("*.png")) + list(latest_version.glob("*.jpg"))

    # Load component library for used items
    library_path = Path(__file__).parent.parent / "assets" / "library.json"
    with open(library_path) as f:
        library = json.load(f)

    used_components = metadata.get("components_used", [])

    # Generate report content
    report = build_report_content(
        project_name=project_name,
        version=latest_version.name,
        metadata=metadata,
        snapshots=snapshots,
        used_components=used_components,
        library=library,
        output_format=output_format,
    )

    # Write report
    report_filename = f"设计方案_{project_name}.md"
    report_path = latest_version / report_filename

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    return {
        "report_path": str(report_path),
        "version": latest_version.name,
        "snapshot_count": len(snapshots),
        "component_count": len(used_components),
    }


def build_report_content(
    project_name: str,
    version: str,
    metadata: dict[str, Any],
    snapshots: list[Path],
    used_components: list[str],
    library: dict[str, Any],
    output_format: str,
) -> str:
    """Build the report content in markdown format."""
    lines = []

    # Header
    lines.append(f"# {project_name}设计方案\n")
    lines.append(f"**版本**: {version}")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n")

    # Style
    style = metadata.get("style_preset", "未指定")
    lines.append(f"**设计风格**: {get_style_display_name(style)}\n")

    lines.append("---\n")

    # Overview
    lines.append("## 设计概览\n")
    room_size = metadata.get("room_size", "未知")
    lines.append(f"- **房间尺寸**: {room_size}")
    lines.append(f"- **元素数量**: {metadata.get('entity_count', '未知')}\n")

    # Requirements
    requirements = metadata.get("requirements", [])
    if requirements:
        lines.append("### 客户需求\n")
        for req in requirements:
            lines.append(f"- {req}")
        lines.append("")

    # Visual Preview
    if snapshots:
        lines.append("## 效果图\n")
        for snapshot in snapshots:
            # Relative path for display
            rel_path = snapshot.name
            lines.append(f"### {snapshot.stem}\n")
            lines.append(f"![{snapshot.stem}]({rel_path})\n")

    # Components List
    if used_components:
        lines.append("## 家具清单\n")
        lines.append("| 家具 | 名称 | 尺寸 (mm) |")
        lines.append("|------|------|----------|")

        component_map = {c["id"]: c for c in library.get("components", [])}

        for comp_id in used_components:
            if comp_id in component_map:
                comp = component_map[comp_id]
                dims = comp.get("default_dimensions", {})
                size_str = f"{dims.get('width', '-')} x {dims.get('depth', '-')} x {dims.get('height', '-')}"
                lines.append(f"| {comp.get('name', comp_id)} | {comp.get('name_en', '')} | {size_str} |")

        lines.append("")

    # Material & Colors
    style_colors = get_style_color_info(style)
    if style_colors:
        lines.append("## 材质与色彩\n")
        for name, hex_color in style_colors.items():
            lines.append(f"- **{name}**: {hex_color}")
        lines.append("")

    # Notes
    lines.append("---\n")
    lines.append("## 设计说明\n")
    lines.append("本方案由 AI 辅助设计系统生成。")
    lines.append("如需调整，请告诉我具体修改内容。\n")

    # Footer
    lines.append("---\n")
    lines.append("*本报告由 SketchUp-Claude-Code 系统自动生成*\n")

    return "\n".join(lines)


def get_style_display_name(style_id: str) -> str:
    """Get Chinese display name for style."""
    style_names = {
        "japandi_cream": "奶油风（日式+北欧融合）",
        "modern_industrial": "工业风",
        "scandinavian": "北欧极简",
        "mediterranean": "地中海",
        "bohemian": "波西米亚",
        "contemporary_minimalist": "现代极简",
    }
    return style_names.get(style_id, style_id)


def get_style_color_info(style_id: str) -> dict[str, str]:
    """Get main colors for a style."""
    style_colors = {
        "japandi_cream": {
            "墙面": "#F5F0E8 (暖奶油白)",
            "地板": "#C4A77D (橡木色)",
            "点缀": "#C67B5C (赤陶色)",
        },
        "modern_industrial": {
            "墙面": "#B8B5B0 (混凝土灰)",
            "金属": "#2A2A2A (炭黑色)",
            "木色": "#8B5A2B (深棕色)",
        },
        "scandinavian": {
            "墙面": "#FFFFFF (纯白)",
            "地板": "#E8DCC8 (浅橡木)",
            "布艺": "#D3D3D3 (浅灰色)",
        },
        "mediterranean": {
            "墙面": "#F8F4F0 (白灰泥)",
            "瓷砖": "#4A90A4 (爱琴海蓝)",
            "陶土": "#C67B5C (赤陶色)",
        },
        "bohemian": {
            "基调": "#F5F0E6 (奶油色)",
            "织物": "#1D6B6B (深青色)",
            "点缀": "#C9A227 (芥末黄)",
        },
        "contemporary_minimalist": {
            "墙面": "#FAFAF8 (暖白)",
            "石材": "#B5A99A (浅灰)",
            "金属": "#C9A86C (黄铜色)",
        },
    }
    return style_colors.get(style_id, {})


async def generate_and_save_report(
    project_name: str,
    project_dir: str = "./designs",
) -> dict[str, Any]:
    """Async wrapper for report generation.

    Returns path to generated report and summary.
    """
    result = generate_design_report(project_name, project_dir)
    return result
