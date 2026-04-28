"""FastMCP entry point for SketchUp Agent Harness MCP server."""

import json
from typing import Any
from mcp.server import Server
from mcp.types import Tool, Resource, TextContent
from mcp.server.fastmcp import FastMCP

from mcp_server.tools import model_tools, query_tools, placement_tools
from mcp_server.bridge.socket_bridge import SocketBridge
from mcp_server.protocol.jsonrpc import JsonRpcRequest
from mcp_server.resources import design_model_mcp
from mcp_server.tools.local_library_search import search_library, get_categories, format_search_results
from mcp_server.tools.bathroom_planner import plan_bathroom_project, save_bathroom_plan

# Create FastMCP server
mcp = FastMCP("sketchup-mcp")


@mcp.tool()
async def get_scene_info() -> TextContent:
    """Get current SketchUp scene information.

    Returns model bounding box, entity counts by type, and layer list.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"query_{id(get_scene_info)}",
                "operation_type": "get_scene_info",
                "payload": {},
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        result = response.get("result", {})
        return TextContent(type="text", text=str(result.get("scene_info", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_wall(
    start_x: float,
    start_y: float,
    start_z: float,
    end_x: float,
    end_y: float,
    end_z: float,
    height: float,
    thickness: float,
    alignment: str = "center",
) -> TextContent:
    """Create a wall in SketchUp.

    Args:
        start_x, start_y, start_z: Start point coordinates in mm
        end_x, end_y, end_z: End point coordinates in mm
        height: Wall height in mm
        thickness: Wall thickness in mm
        alignment: Wall alignment - "center", "inner", or "outer"

    Returns:
        JSON string with entity_id and spatial_delta of created wall.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"wall_{id(create_wall)}",
                "operation_type": "create_wall",
                "payload": {
                    "start": [start_x, start_y, start_z],
                    "end": [end_x, end_y, end_z],
                    "height": height,
                    "thickness": thickness,
                    "alignment": alignment,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_face(vertices: list[list[float]], layer: str | None = None) -> TextContent:
    """Create a face from vertices."""
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"face_{id(create_face)}",
                "operation_type": "create_face",
                "payload": {"vertices": vertices, "layer": layer},
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_box(
    corner_x: float,
    corner_y: float,
    corner_z: float,
    width: float,
    depth: float,
    height: float,
) -> TextContent:
    """Create a 3D box."""
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"box_{id(create_box)}",
                "operation_type": "create_box",
                "payload": {
                    "corner": [corner_x, corner_y, corner_z],
                    "width": width,
                    "depth": depth,
                    "height": height,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def place_component(
    component_name: str,
    position_x: float = 0,
    position_y: float = 0,
    position_z: float = 0,
    rotation: float = 0,
    scale: float = 1,
) -> TextContent:
    """Place a furniture component from the component library.

    Args:
        component_name: Name of component (e.g., "现代双人沙发")
        position_x, position_y, position_z: Position in mm
        rotation: Rotation angle in degrees
        scale: Scale factor (1.0 = default size)
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        # First find the component in library
        component = placement_tools.find_component_by_name(component_name)
        if not component:
            return TextContent(type="text", text=f"Error: Component not found: {component_name}")

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"place_{id(place_component)}",
                "operation_type": "place_component",
                "payload": {
                    "skp_path": placement_tools.resolve_skp_path(
                        placement_tools.component_skp_path(component)
                    ),
                    "position": [position_x, position_y, position_z],
                    "rotation": rotation,
                    "scale": scale,
                    "component_id": component["id"],
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def apply_material(
    entity_ids: list[str],
    color: str | None = None,
    material_id: str | None = None,
    texture_scale_x: int | None = None,
    texture_scale_y: int | None = None,
) -> TextContent:
    """Apply material to entities.

    Args:
        entity_ids: List of entity IDs to apply material to
        color: Hex color (e.g., "#C67B5C") or RGB array [r, g, b]
        material_id: Optional SketchUp material name
        texture_scale_x: Texture scale X in mm
        texture_scale_y: Texture scale Y in mm
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        texture_scale = None
        if texture_scale_x and texture_scale_y:
            texture_scale = [texture_scale_x, texture_scale_y]

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"material_{id(apply_material)}",
                "operation_type": "apply_material",
                "payload": {
                    "entity_ids": entity_ids,
                    "color": color,
                    "material_id": material_id,
                    "texture_scale": texture_scale,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def apply_style(
    style_name: str,
    entity_ids: list[str] | None = None,
) -> TextContent:
    """Apply a complete style preset to the model or specific entities.

    Args:
        style_name: Style preset name.
                    Options: "japandi_cream", "modern_industrial", "scandinavian",
                             "mediterranean", "bohemian", "contemporary_minimalist"
        entity_ids: Optional list of entity IDs to apply style to.
                    If None, applies to all faces in the model.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"style_{id(apply_style)}",
                "operation_type": "apply_style",
                "payload": {
                    "style_name": style_name,
                    "entity_ids": entity_ids,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def place_lighting(
    lighting_type: str,
    position_x: float,
    position_y: float,
    position_z: float = 0,
    ceiling_height: float = 2400,
    mount_height: float = 2000,
    rotation: float = 0,
) -> TextContent:
    """Place a lighting fixture.

    Args:
        lighting_type: Type - "spotlight", "chandelier", "floor_lamp"
        position_x, position_y, position_z: Position in mm
        ceiling_height: Ceiling height for spotlight placement
        mount_height: Mount height for chandelier
        rotation: Rotation angle in degrees
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"light_{id(place_lighting)}",
                "operation_type": "place_lighting",
                "payload": {
                    "lighting_type": lighting_type,
                    "position": [position_x, position_y, position_z],
                    "ceiling_height": ceiling_height,
                    "mount_height": mount_height,
                    "rotation": rotation,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def set_camera_view(
    view_preset: str | None = None,
    eye_x: float | None = None,
    eye_y: float | None = None,
    eye_z: float | None = None,
    target_x: float | None = None,
    target_y: float | None = None,
    target_z: float | None = None,
) -> TextContent:
    """Set the camera view position.

    Args:
        view_preset: Preset name - "panoramic", "living_room_birdseye",
                     "master_bedroom", "dining_area", "front_entrance"
        eye_x/y/z: Custom camera eye position (required for custom view)
        target_x/y/z: Custom camera target position
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        payload = {"view_preset": view_preset}

        if view_preset is None and eye_x is not None:
            payload["eye"] = [eye_x, eye_y or 0, eye_z or 0]
            payload["target"] = [target_x or 0, target_y or 0, target_z or 0]

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"camera_{id(set_camera_view)}",
                "operation_type": "set_camera_view",
                "payload": payload,
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {}).get("view_info", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def capture_design(
    output_path: str,
    view_preset: str | None = None,
    width: int = 1920,
    height: int = 1080,
    return_base64: bool = False,
) -> TextContent:
    """Capture the current design view to an image file.

    Args:
        output_path: Full path to output image file
        view_preset: Optional view preset to set before capture
        width: Image width in pixels
        height: Image height in pixels
        return_base64: If True, return base64 encoded image for Claude vision

    Returns:
        Capture info including base64 image if requested.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"capture_{id(capture_design)}",
                "operation_type": "capture_design",
                "payload": {
                    "output_path": output_path,
                    "view_preset": view_preset,
                    "width": width,
                    "height": height,
                    "return_base64": return_base64,
                },
                "rollback_on_failure": False,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")

        result = response.get("result", {})
        capture_info = result.get("capture_info", {})

        # If base64 requested, read the file and encode
        if return_base64:
            import base64
            try:
                with open(output_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                capture_info["image_base64"] = img_data
            except Exception as e:
                capture_info["image_base64_error"] = str(e)

        return TextContent(type="text", text=str(capture_info))
    finally:
        bridge.disconnect()


@mcp.tool()
async def cleanup_model(
    layer_names: list[str] | None = None,
    tag: str | None = None,
) -> TextContent:
    """Clean up AI-generated content from the model.

    Args:
        layer_names: Specific layer names to clean. If None, cleans all AI layers.
                     Options: "Walls", "Furniture", "Fixtures", "Lighting", "Materials"
        tag: Alternative cleanup by component definition name containing tag.

    Returns:
        Cleanup summary with deleted count and entity IDs.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"cleanup_{id(cleanup_model)}",
                "operation_type": "cleanup_model",
                "payload": {
                    "layer_names": layer_names,
                    "tag": tag,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")

        result = response.get("result", {})
        cleanup_info = result.get("cleanup_info", {})

        return TextContent(type="text", text=str(cleanup_info))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_door(
    wall_id: str,
    position_x: float,
    position_y: float = 0,
    width: float = 900,
    height: float = 2100,
    swing_direction: str = "left",
) -> TextContent:
    """Create a door in a SketchUp wall with frame and swing panel.

    Args:
        wall_id: Entity ID of the wall to place door in
        position_x: Position along the wall from start in mm
        position_y: Position from wall face in mm (default 0)
        width: Door width in mm (default 900mm)
        height: Door height in mm (default 2100mm)
        swing_direction: "left" or "right" swing

    Returns:
        JSON string with entity_id and spatial_delta of created door.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"door_{id(create_door)}",
                "operation_type": "create_door",
                "payload": {
                    "wall_id": wall_id,
                    "position_x": position_x,
                    "position_y": position_y,
                    "width": width,
                    "height": height,
                    "swing_direction": swing_direction,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_window(
    wall_id: str,
    position_x: float,
    position_y: float = 0,
    width: float = 1200,
    height: float = 1000,
    sill_height: float = 900,
) -> TextContent:
    """Create a window in a SketchUp wall with frame and glass.

    Args:
        wall_id: Entity ID of the wall to place window in
        position_x: Position along the wall from start in mm
        position_y: Position from wall face in mm (default 0)
        width: Window width in mm (default 1200mm)
        height: Window height in mm (default 1000mm)
        sill_height: Height from floor to windowsill in mm (default 900mm)

    Returns:
        JSON string with entity_id and spatial_delta of created window.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"window_{id(create_window)}",
                "operation_type": "create_window",
                "payload": {
                    "wall_id": wall_id,
                    "position_x": position_x,
                    "position_y": position_y,
                    "width": width,
                    "height": height,
                    "sill_height": sill_height,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def create_stairs(
    start_x: float,
    start_y: float,
    start_z: float,
    end_x: float,
    end_y: float,
    end_z: float,
    width: float = 1000,
    num_steps: int | None = None,
) -> TextContent:
    """Create a staircase between two levels in SketchUp.

    Args:
        start_x, start_y, start_z: Start position (bottom of stairs) in mm
        end_x, end_y, end_z: End position (top of stairs) in mm
        width: Stair width in mm (default 1000mm)
        num_steps: Number of steps (calculated from rise if not provided)

    Returns:
        JSON string with entity_id, spatial_delta, and stairs_info of created stairs.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"stairs_{id(create_stairs)}",
                "operation_type": "create_stairs",
                "payload": {
                    "start_x": start_x,
                    "start_y": start_y,
                    "start_z": start_z,
                    "end_x": end_x,
                    "end_y": end_y,
                    "end_z": end_z,
                    "width": width,
                    "num_steps": num_steps,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def search_local_library(
    query: str,
    category: str | None = None,
    limit: int = 10,
) -> TextContent:
    """Search local component library for matching components.

    Use this to find furniture, fixtures, and lighting from the user's
    local SketchUp component library before using place_component.

    Args:
        query: Search query (e.g., "sofa", "dining table", "北欧风格")
        category: Optional category filter - "furniture", "fixtures", "lighting"
        limit: Maximum number of results (default 10)

    Returns:
        List of matching components with IDs and paths for place_component.
    """
    try:
        results = search_library(query, category=category, limit=limit)
        formatted = format_search_results(results)
        return TextContent(type="text", text=formatted)
    except Exception as e:
        return TextContent(type="text", text=f"Search failed: {str(e)}")


@mcp.tool()
async def list_local_library_categories() -> TextContent:
    """List all available categories in the local component library.

    Returns:
        List of categories like "furniture", "fixtures", "lighting".
    """
    try:
        categories = get_categories()
        if not categories:
            return TextContent(type="text", text="No categories found in library.")
        return TextContent(type="text", text="Available categories:\n- " + "\n- ".join(categories))
    except Exception as e:
        return TextContent(type="text", text=f"Failed to load categories: {str(e)}")


@mcp.tool()
async def plan_bathroom(
    project_name: str = "bathroom_mvp",
    width: float = 2000,
    depth: float = 1800,
    ceiling_height: float = 2400,
    project_path: str | None = None,
) -> TextContent:
    """Plan a small bathroom without requiring a live SketchUp bridge.

    Generates a design_model, design_rules, validation report, and bridge
    operation trace for the first vertical slice. If project_path is provided,
    design_model.json and design_rules.json are written into that directory.
    """
    try:
        plan = plan_bathroom_project(
            project_name=project_name,
            width=width,
            depth=depth,
            ceiling_height=ceiling_height,
        )
        if project_path:
            plan["written_files"] = save_bathroom_plan(project_path, plan)
        return TextContent(
            type="text",
            text=json.dumps(plan, ensure_ascii=False, indent=2),
        )
    except Exception as e:
        return TextContent(type="text", text=f"Bathroom planning failed: {str(e)}")

@mcp.tool()
async def generate_report(project_name: str, project_dir: str = "./designs") -> TextContent:
    """Generate a design report with snapshots and component list.

    Args:
        project_name: Name of the project
        project_dir: Base directory for designs

    Returns:
        Path to generated report and summary.
    """
    try:
        from mcp_server.tools.report_tools import generate_design_report

        result = generate_design_report(project_name, project_dir)
        return TextContent(type="text", text=str(result))
    except Exception as e:
        return TextContent(type="text", text=f"Error generating report: {str(e)}")


@mcp.tool()
async def save_version(
    project_name: str,
    version_tag: str,
    description: str = "",
    project_dir: str = "./designs",
) -> TextContent:
    """Save current model state as a versioned snapshot.

    Args:
        project_name: Name of the project
        version_tag: Version identifier (e.g., "v1.0", "draft_2")
        description: Brief description of this version
        project_dir: Base directory for designs

    Returns:
        Path to saved version.
    """
    import json
    from datetime import datetime
    from pathlib import Path

    project_path = Path(project_dir) / project_name
    project_path.mkdir(parents=True, exist_ok=True)

    version_path = project_path / version_tag
    version_path.mkdir(exist_ok=True)

    # Capture snapshot of current state
    bridge = SocketBridge()
    try:
        bridge.connect()
        snapshot_path = version_path / f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"save_{id(save_version)}",
                "operation_type": "capture_design",
                "payload": {
                    "output_path": str(snapshot_path),
                    "view_preset": "panoramic",
                    "width": 1920,
                    "height": 1080,
                },
                "rollback_on_failure": False,
            }
        )
        bridge.send(request.to_dict())
    finally:
        bridge.disconnect()

    # Create metadata
    metadata = {
        "version": version_tag,
        "created_at": datetime.now().isoformat(),
        "description": description,
        "snapshot": snapshot_path.name,
    }

    metadata_path = version_path / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return TextContent(type="text", text=f"Version saved: {version_path}")


@mcp.tool()
async def list_versions(project_name: str, project_dir: str = "./designs") -> TextContent:
    """List all versions of a project.

    Args:
        project_name: Name of the project
        project_dir: Base directory for designs

    Returns:
        List of versions with descriptions.
    """
    import json
    from pathlib import Path

    project_path = Path(project_dir) / project_name
    if not project_path.exists():
        return TextContent(type="text", text="No project found")

    versions = []
    for v_dir in sorted(project_path.iterdir()):
        if v_dir.is_dir() and v_dir.name.startswith("v"):
            metadata_path = v_dir / "metadata.json"
            info = {"version": v_dir.name, "path": str(v_dir)}

            if metadata_path.exists():
                with open(metadata_path) as f:
                    info.update(json.load(f))

            versions.append(info)

    return TextContent(type="text", text=str(versions))


@mcp.tool()
async def search_sketchfab_models(
    query: str,
    count: int = 10,
    sort: str = "relevance",
) -> TextContent:
    """Search Sketchfab for 3D models.

    Use this to find furniture, fixtures, and decorative objects from
    Sketchfab's library of Creative Commons licensed 3D models.

    Args:
        query: Search query (e.g., "modern sofa", "floor lamp", "potted plant")
        count: Number of results to return (max 50)
        sort: Sort order - "relevance", "newest", "likes", "views"

    Returns:
        List of matching 3D models with download links and metadata.
    """
    from mcp_server.tools.sketchfab_tools import search_models

    try:
        results = search_models(
            query=query,
            count=count,
            sort=sort,
        )
        return TextContent(type="text", text=str(results))
    except Exception as e:
        return TextContent(type="text", text=f"Search failed: {str(e)}")


@mcp.tool()
async def get_sketchfab_model(model_uid: str) -> TextContent:
    """Get detailed information about a Sketchfab model.

    Args:
        model_uid: Sketchfab model UID (from search results)

    Returns:
        Detailed model information including download formats and links.
    """
    from mcp_server.tools.sketchfab_tools import get_model_info

    try:
        info = get_model_info(model_uid)
        return TextContent(type="text", text=str(info))
    except Exception as e:
        return TextContent(type="text", text=f"Failed to get model info: {str(e)}")


@mcp.tool()
async def download_sketchfab_model(
    model_uid: str,
    format_hint: str | None = "obj",
    output_dir: str | None = None,
) -> TextContent:
    """Download a Sketchfab 3D model.

    Downloads the model in the specified format (OBJ recommended for SketchUp).
    After download, models can be imported into SketchUp.

    Args:
        model_uid: Sketchfab model UID (from search results)
        format_hint: Preferred format - "obj" (recommended for SketchUp), "gltf", "glb"
        output_dir: Output directory (defaults to ~/SketchUp/SCC/downloaded_models/)

    Returns:
        Download status and file path.
    """
    from pathlib import Path
    from mcp_server.tools.sketchfab_tools import download_model

    try:
        output_path = Path(output_dir) if output_dir else None
        result = download_model(
            uid=model_uid,
            format_hint=format_hint,
            output_dir=output_path,
        )
        return TextContent(type="text", text=str(result))
    except Exception as e:
        return TextContent(type="text", text=f"Download failed: {str(e)}")


@mcp.tool()
async def search_and_download_sketchfab(
    query: str,
    format_hint: str = "obj",
) -> TextContent:
    """Search Sketchfab and download the top result in one step.

    Convenience function that searches for models and downloads the
    first downloadable result.

    Args:
        query: Search query (e.g., "minimalist coffee table")
        format_hint: Preferred format - "obj" (recommended for SketchUp), "gltf", "glb"

    Returns:
        Search results and download status.
    """
    from pathlib import Path
    from mcp_server.tools.sketchfab_tools import search_and_download

    try:
        result = search_and_download(
            query=query,
            format_hint=format_hint,
        )
        return TextContent(type="text", text=str(result))
    except Exception as e:
        return TextContent(type="text", text=f"Search and download failed: {str(e)}")


@mcp.tool()
async def search_warehouse(query: str) -> TextContent:
    """Get a SketchUp 3D Warehouse search URL.

    Opens the 3D Warehouse search page in your browser where you can
    browse and download 3D models.

    Note: 3D Warehouse does not have a public API, so this tool provides
    a search URL that you can open in your browser.

    Args:
        query: Search query (e.g., "modern sofa", "floor lamp")

    Returns:
        URL to open in browser for searching 3D Warehouse.
    """
    from mcp_server.tools.warehouse_tool import search_warehouse_url

    url = search_warehouse_url(query)
    return TextContent(type="text", text=f"Open this URL in your browser to search 3D Warehouse:\n\n{url}")


@mcp.tool()
async def download_from_warehouse(warehouse_url: str) -> TextContent:
    """Get guidance for downloading a model from SketchUp 3D Warehouse URL.

    Note: 3D Warehouse does not have a public API. This tool provides
    guidance for the manual download process.

    Args:
        warehouse_url: Full URL to a 3D Warehouse model page
                       (e.g., https://3dwarehouse.sketchup.com/model/abc123/...)

    Returns:
        Instructions for downloading the model.
    """
    from mcp_server.tools.warehouse_tool import download_from_warehouse

    result = download_from_warehouse(warehouse_url)
    return TextContent(type="text", text=result.message)


@mcp.tool()
async def get_warehouse_model_info(warehouse_url: str) -> TextContent:
    """Extract model information from a SketchUp 3D Warehouse URL.

    Note: 3D Warehouse does not have a public API. This tool does
    best-effort extraction of model ID from the URL pattern.

    Args:
        warehouse_url: Full URL to a 3D Warehouse model page

    Returns:
        Model ID and URL extracted from the link.
    """
    from mcp_server.tools.warehouse_tool import get_model_info_from_url

    info = get_model_info_from_url(warehouse_url)
    return TextContent(type="text", text=str(info))


@mcp.tool()
async def move_entity(
    entity_ids: list[str],
    delta_x: float,
    delta_y: float,
    delta_z: float,
) -> TextContent:
    """Move entities by a delta in mm.

    Args:
        entity_ids: List of entity IDs to move
        delta_x: Delta X in mm
        delta_y: Delta Y in mm
        delta_z: Delta Z in mm

    Returns:
        JSON string with entity_ids and status of moved entities.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"move_{id(move_entity)}",
                "operation_type": "move_entity",
                "payload": {
                    "entity_ids": entity_ids,
                    "delta": [delta_x, delta_y, delta_z],
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


if __name__ == "__main__":
    # Run the MCP server after all tools have been registered.
    mcp.run()


@mcp.tool()
async def rotate_entity(
    entity_ids: list[str],
    center_x: float,
    center_y: float,
    center_z: float,
    axis: str,
    angle: float,
) -> TextContent:
    """Rotate entities around a center point and axis.

    Args:
        entity_ids: List of entity IDs to rotate
        center_x: Center X coordinate in mm
        center_y: Center Y coordinate in mm
        center_z: Center Z coordinate in mm
        axis: Rotation axis - "+x", "-x", "+y", "-y", "+z", "-z"
        angle: Rotation angle in degrees

    Returns:
        JSON string with entity_ids and status of rotated entities.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"rotate_{id(rotate_entity)}",
                "operation_type": "rotate_entity",
                "payload": {
                    "entity_ids": entity_ids,
                    "center": [center_x, center_y, center_z],
                    "axis": axis,
                    "angle": angle,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def scale_entity(
    entity_ids: list[str],
    center_x: float,
    center_y: float,
    center_z: float,
    scale: float | list[float],
) -> TextContent:
    """Scale entities uniformly or non-uniformly around a center point.

    Args:
        entity_ids: List of entity IDs to scale
        center_x: Center X coordinate in mm
        center_y: Center Y coordinate in mm
        center_z: Center Z coordinate in mm
        scale: Uniform scale factor (float) or [sx, sy, sz] for non-uniform scaling

    Returns:
        JSON string with entity_ids and status of scaled entities.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"scale_{id(scale_entity)}",
                "operation_type": "scale_entity",
                "payload": {
                    "entity_ids": entity_ids,
                    "center": [center_x, center_y, center_z],
                    "scale": scale,
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()


@mcp.tool()
async def copy_entity(
    entity_ids: list[str],
    delta_x: float,
    delta_y: float,
    delta_z: float,
) -> TextContent:
    """Create copies of entities and translate them by delta.

    Args:
        entity_ids: List of entity IDs to copy
        delta_x: Delta X in mm
        delta_y: Delta Y in mm
        delta_z: Delta Z in mm

    Returns:
        JSON string with entity_ids of the new copies.
    """
    bridge = SocketBridge()
    try:
        bridge.connect()
        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"copy_{id(copy_entity)}",
                "operation_type": "copy_entity",
                "payload": {
                    "entity_ids": entity_ids,
                    "delta": [delta_x, delta_y, delta_z],
                },
                "rollback_on_failure": True,
            }
        )
        response = bridge.send(request.to_dict())
        if "error" in response:
            return TextContent(type="text", text=f"Error: {response['error']['message']}")
        return TextContent(type="text", text=str(response.get("result", {})))
    finally:
        bridge.disconnect()
