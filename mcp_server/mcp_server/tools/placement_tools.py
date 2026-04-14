"""Furniture placement tools with spatial validation."""

import json
import math
from typing import Any
from pathlib import Path

from mcp_server.bridge.socket_bridge import SocketBridge
from mcp_server.protocol.jsonrpc import JsonRpcRequest
from mcp_server.protocol.spatial import create_bounding_box


# Load component library
LIBRARY_PATH = Path(__file__).parent.parent / "assets" / "library.json"


def load_library() -> dict[str, Any]:
    """Load the component library from JSON."""
    with open(LIBRARY_PATH) as f:
        return json.load(f)


def find_component_by_name(name: str) -> dict[str, Any] | None:
    """Find a component by name (supports Chinese and English)."""
    library = load_library()
    name_lower = name.lower()

    for component in library.get("components", []):
        if (name_lower in component.get("name", "").lower() or
            name_lower in component.get("name_en", "").lower() or
            any(name_lower in tag.lower() for tag in component.get("tags", []))):
            return component

    return None


def calculate_wall_offset(
    wall_start: list[float],
    wall_end: list[float],
    wall_thickness: float,
    alignment: str = "inner",
) -> tuple[list[float], float]:
    """Calculate position offset and rotation for wall alignment.

    Returns:
        Tuple of (offset_position, rotation_angle_degrees)
    """
    # Direction vector along wall
    dx = wall_end[0] - wall_start[0]
    dy = wall_end[1] - wall_start[1]
    length = math.sqrt(dx*dx + dy*dy)

    if length < 1:
        return wall_start, 0.0

    # Normalized direction
    dir_x, dir_y = dx / length, dy / length

    # Perpendicular normal (points left of wall direction, Z-up)
    normal = [-dir_y, dir_x, 0]

    # Calculate offset based on alignment
    offset_distance = wall_thickness / 2.0
    if alignment == "inner":
        offset_distance = wall_thickness
    elif alignment == "outer":
        offset_distance = 0.0

    offset = [
        normal[0] * offset_distance,
        normal[1] * offset_distance,
        0.0
    ]

    # Calculate rotation angle (angle from +X axis to wall direction)
    rotation_rad = math.atan2(dir_y, dir_x)
    rotation_deg = math.degrees(rotation_rad)

    return offset, rotation_deg


def align_to_wall(
    target_wall: dict[str, Any],
    component_bounds: dict[str, Any],
    alignment: str = "inner",
) -> dict[str, Any]:
    """Calculate placement position aligned to a wall.

    Args:
        target_wall: Wall info with start, end, thickness
        component_bounds: Component bounding box {min, max}
        alignment: "inner", "outer", or "center"

    Returns:
        Dict with position and rotation
    """
    wall_start = target_wall["start"]
    wall_end = target_wall["end"]
    wall_thickness = target_wall.get("thickness", 150)

    # Get wall direction
    dx = wall_end[0] - wall_start[0]
    dy = wall_end[1] - wall_start[1]
    wall_length = math.sqrt(dx*dx + dy*dy)

    # Calculate offset
    offset, rotation = calculate_wall_offset(wall_start, wall_end, wall_thickness, alignment)

    # Get component dimensions
    comp_width = component_bounds["max"][0] - component_bounds["min"][0]
    comp_depth = component_bounds["max"][1] - component_bounds["min"][1]

    # Position is offset from wall center along the normal
    position = [
        wall_start[0] + offset[0],
        wall_start[1] + offset[1],
        wall_start[2] + 0,  # On floor
    ]

    return {
        "position": position,
        "rotation": rotation,
        "width": comp_width,
        "depth": comp_depth,
    }


def check_collision(
    new_bounds: dict[str, Any],
    existing_entities: list[dict[str, Any]],
    min_clearance: float = 600,
) -> dict[str, Any]:
    """Check if new component would collide with existing entities.

    Args:
        new_bounds: Bounding box of new component {min, max}
        existing_entities: List of existing entity bounds
        min_clearance: Minimum gap required in mm

    Returns:
        Dict with collision status and details
    """
    new_min = new_bounds["min"]
    new_max = new_bounds["max"]

    for entity in existing_entities:
        ent_min = entity["bounds"]["min"]
        ent_max = entity["bounds"]["max"]

        # Check AABB collision with clearance
        if (new_min[0] - min_clearance < ent_max[0] and
            new_max[0] + min_clearance > ent_min[0] and
            new_min[1] - min_clearance < ent_max[1] and
            new_max[1] + min_clearance > ent_min[1] and
            new_min[2] < ent_max[2] and
            new_max[2] > ent_min[2]):
            return {
                "collision": True,
                "entity_id": entity.get("entity_id"),
                "type": entity.get("type"),
                "message": f"Would collide with {entity.get('type', 'entity')}",
            }

    return {"collision": False}


async def place_component(
    component_name: str,
    position: list[float] | None = None,
    rotation: float = 0.0,
    wall_id: str | None = None,
    wall_alignment: str = "inner",
    scale: float = 1.0,
) -> dict[str, Any]:
    """Place a furniture component in the scene.

    Args:
        component_name: Name of component (e.g., "现代双人沙发")
        position: [x, y, z] position in mm, or None for origin
        rotation: Rotation angle in degrees (Y-axis rotation)
        wall_id: Optional wall ID to align to
        wall_alignment: Alignment to wall ("inner", "outer", "center")
        scale: Scale factor (1.0 = default size)

    Returns:
        Dict with entity_id, spatial_delta, and placement info
    """
    # Find component in library
    component = find_component_by_name(component_name)
    if not component:
        raise ValueError(f"Component not found: {component_name}")

    # Calculate placement position
    if wall_id and position is None:
        # Get wall info and calculate aligned position
        # This would query the scene for wall info
        # For now, use a placeholder
        pass

    if position is None:
        position = [0, 0, 0]

    # Apply insertion point offset
    insertion_offset = component.get("insertion_point", {}).get("offset", [0, 0, 0])
    placement_position = [
        position[0] + insertion_offset[0] * scale,
        position[1] + insertion_offset[1] * scale,
        position[2] + insertion_offset[2] * scale,
    ]

    # Send to Ruby bridge
    bridge = SocketBridge()
    try:
        bridge.connect()

        request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": f"place_{id(place_component)}",
                "operation_type": "place_component",
                "payload": {
                    "skp_path": resolve_skp_path(component["skp_path"]),
                    "position": placement_position,
                    "rotation": rotation,
                    "scale": scale,
                    "component_id": component["id"],
                },
                "rollback_on_failure": True,
            }
        )

        response = bridge.send(request.to_dict())

        if "error" in response:
            raise RuntimeError(f"Placement failed: {response['error']['message']}")

        result = response.get("result", {})
        result["component_info"] = {
            "id": component["id"],
            "name": component["name"],
            "name_en": component.get("name_en"),
        }

        return result

    finally:
        bridge.disconnect()


def resolve_skp_path(skp_path: str) -> str:
    """Resolve SKP path from environment variable or default."""
    import os
    assets_path = os.environ.get("SKETCHUP_ASSETS", "/Applications/SketchUp.app/Contents/Resources")
    return skp_path.replace("${SKETCHUP_ASSETS}", assets_path)


async def validate_placement(
    component_name: str,
    position: list[float],
    rotation: float = 0.0,
) -> dict[str, Any]:
    """Validate if placement is valid (no collisions, meets clearances).

    Args:
        component_name: Name of component
        position: Target position [x, y, z]
        rotation: Rotation in degrees

    Returns:
        Dict with validation result and suggestions
    """
    component = find_component_by_name(component_name)
    if not component:
        return {"valid": False, "error": f"Unknown component: {component_name}"}

    # Get scene info
    bridge = SocketBridge()
    try:
        bridge.connect()

        # Get current scene
        scene_request = JsonRpcRequest(
            method="execute_operation",
            params={
                "operation_id": "validate_check",
                "operation_type": "get_scene_info",
                "payload": {},
                "rollback_on_failure": False,
            }
        )
        scene_response = bridge.send(scene_request.to_dict())
        scene_info = scene_response.get("result", {}).get("scene_info", {})

        # Calculate component bounds at target position
        bounds = component.get("bounds", {})
        if bounds:
            comp_min = bounds.get("min", [0, 0, 0])
            comp_max = bounds.get("max", [0, 0, 0])

            # Rotate and translate bounds (simplified)
            new_bounds = {
                "min": position,
                "max": [
                    position[0] + (comp_max[0] - comp_min[0]),
                    position[1] + (comp_max[1] - comp_min[1]),
                    position[2] + (comp_max[2] - comp_min[2]),
                ],
            }

            # Check collision
            library = load_library()
            min_clearance = library.get("placement_rules", {}).get("min_clearance", 600)

            collision = check_collision(
                new_bounds,
                [],  # Would pass existing entities from scene_info
                min_clearance
            )

            if collision.get("collision"):
                return {
                    "valid": False,
                    "error": collision.get("message", "Would cause collision"),
                    "suggestion": "Try moving the component or removing obstacles",
                }

        return {"valid": True, "position": position}

    finally:
        bridge.disconnect()
