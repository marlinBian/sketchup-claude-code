"""Design Model MCP Resources.

Provides read-only access to design_model.json files for LLM consumption.

Resource URIs:
- design://{project_path}/current       - Full design model
- design://{project_path}/components   - All components (filter by type in body)
- design://{project_path}/spaces        - All spaces
- design://{project_path}/semantic-anchor/{component_id} - Semantic anchors for component
- design://{project_path}/layer/{layer_name} - Entities on a layer

Note: project_path is the full directory path where .design_model.json is located.
For example: /Users/name/SketchUpProjects/living-room
"""

import json
import logging
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Initialize FastMCP instance for these resources
mcp = FastMCP("scc-design")

# Design model filename (hidden file)
DESIGN_MODEL_FILENAME = ".design_model.json"


def _load_design_model(project_path: str) -> dict:
    """Load and parse .design_model.json for a project.

    Args:
        project_path: Full directory path where .design_model.json is located

    Returns:
        Parsed .design_model.json data

    Raises:
        FileNotFoundError: If project or .design_model.json doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    # project_path is the directory, we look for .design_model.json inside it
    design_model_path = Path(project_path) / DESIGN_MODEL_FILENAME
    if not design_model_path.exists():
        raise FileNotFoundError(f"Design model not found in: {project_path}")

    with open(design_model_path, "r", encoding="utf-8") as f:
        return json.load(f)


@mcp.resource("design://{project_path}/current")
async def get_design_model(project_path: str) -> dict:
    """Get the current design model for a project.

    Args:
        project_path: Full directory path containing .design_model.json

    Returns:
        Complete design model JSON

    Raises:
        FileNotFoundError: If project doesn't exist
    """
    return _load_design_model(project_path)


@mcp.resource("design://{project_path}/components")
async def list_components(project_path: str) -> dict:
    """List components in a project.

    The returned dict contains all components. The 'type' field of each
    component can be used for filtering on the client side.

    Args:
        project_path: Full directory path containing .design_model.json

    Returns:
        Dict with 'components' list and optional 'type_filter' if provided
    """
    try:
        data = _load_design_model(project_path)
    except FileNotFoundError:
        # Return empty result if project doesn't exist
        return {"components": [], "project_path": project_path}

    components = data.get("components", {})
    return {
        "components": [
            {"id": cid, **cdata}
            for cid, cdata in components.items()
        ],
        "project_path": project_path,
        "available_types": list(set(
            c.get("type", "unknown")
            for c in components.values()
        )),
    }


@mcp.resource("design://{project_path}/spaces")
async def get_spaces(project_path: str) -> dict:
    """Get all spaces in the design.

    Args:
        project_path: Full directory path containing .design_model.json

    Returns:
        Dictionary of space_id -> space_data

    Raises:
        FileNotFoundError: If project doesn't exist
    """
    data = _load_design_model(project_path)
    return data.get("spaces", {})


@mcp.resource("design://{project_path}/semantic-anchor/{component_id}")
async def get_semantic_anchor(project_path: str, component_id: str) -> dict:
    """Get semantic anchors for a specific component.

    Args:
        project_path: Full directory path containing .design_model.json
        component_id: Component ID to look up

    Returns:
        Dictionary of anchor_name -> [x, y, z] or anchor data

    Raises:
        FileNotFoundError: If project or component doesn't exist
    """
    data = _load_design_model(project_path)

    components = data.get("components", {})
    if component_id not in components:
        raise KeyError(f"Component not found: {component_id}")

    component = components[component_id]

    # Return semantic_anchor data if present
    semantic_anchor = component.get("semantic_anchor", {})
    if not semantic_anchor:
        return {}

    return semantic_anchor


@mcp.resource("design://{project_path}/layer/{layer_name}")
async def get_layer_entities(project_path: str, layer_name: str) -> list[dict]:
    """Get all entities on a specific layer.

    Args:
        project_path: Full directory path containing .design_model.json
        layer_name: Layer name to query (e.g., "Walls", "Furniture", "Lighting")

    Returns:
        List of entities on the layer

    Raises:
        FileNotFoundError: If project doesn't exist
    """
    try:
        data = _load_design_model(project_path)
    except FileNotFoundError:
        return []

    # Look for layer data in design model
    # The structure may have entities grouped by layer
    layers = data.get("layers", {})

    if layer_name in layers:
        layer_data = layers[layer_name]
        if isinstance(layer_data, list):
            return layer_data
        return [layer_data] if layer_data else []

    # Fallback: search through all entities and filter by layer
    entities = data.get("entities", {})
    return [
        {"id": eid, **edata}
        for eid, edata in entities.items()
        if edata.get("layer") == layer_name
    ]
