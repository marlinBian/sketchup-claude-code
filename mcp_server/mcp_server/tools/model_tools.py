"""Entity creation and deletion tools."""

from typing import Any


async def create_face(vertices: list[list[float]], material_id: str | None = None, layer: str | None = None) -> dict[str, Any]:
    """Create a face from vertices.

    Args:
        vertices: Array of [x, y, z] points in mm
        material_id: Optional material to apply
        layer: Optional layer name
    """
    raise NotImplementedError("Pending su_bridge integration")


async def create_box(
    corner: list[float],
    width: float,
    depth: float,
    height: float,
    material_id: str | None = None,
    layer: str | None = None,
) -> dict[str, Any]:
    """Create a 3D box.

    Args:
        corner: Bottom-left corner [x, y, z] in mm
        width: Width in mm
        depth: Depth in mm
        height: Height in mm
        material_id: Optional material to apply
        layer: Optional layer name
    """
    raise NotImplementedError("Pending su_bridge integration")


async def create_group(entity_ids: list[str], name: str | None = None) -> dict[str, Any]:
    """Create a group containing entities.

    Args:
        entity_ids: Entities to group
        name: Optional group name
    """
    raise NotImplementedError("Pending su_bridge integration")


async def delete_entity(entity_ids: list[str]) -> dict[str, Any]:
    """Delete entities by ID.

    Args:
        entity_ids: Entities to delete
    """
    raise NotImplementedError("Pending su_bridge integration")


async def set_material(entity_ids: list[str], material_id: str) -> dict[str, Any]:
    """Apply material to entities.

    Args:
        entity_ids: Target entities
        material_id: Material ID to apply
    """
    raise NotImplementedError("Pending su_bridge integration")
