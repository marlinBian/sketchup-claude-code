"""Export tools for glTF and IFC."""

from typing import Any


async def export_gltf(output_path: str, include_textures: bool = True) -> dict[str, Any]:
    """Export model to glTF format.

    Args:
        output_path: Destination file path
        include_textures: Whether to embed textures
    """
    raise NotImplementedError("Pending su_bridge integration")


async def export_ifc(output_path: str) -> dict[str, Any]:
    """Export model to IFC format.

    Args:
        output_path: Destination file path
    """
    raise NotImplementedError("Pending su_bridge integration")
