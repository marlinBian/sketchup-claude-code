"""Sketchfab 3D model search and download tools.

This module provides tools to search Sketchfab's 3D model library,
download models in compatible formats (OBJ, GLTF), and import them
into SketchUp.
"""

import json
import os
import tempfile
import hashlib
from pathlib import Path
from typing import Any

import requests

# Sketchfab API endpoints
SKETCHFAB_API_BASE = "https://api.sketchfab.com/v3"
SKETCHFAB_SEARCH_URL = f"{SKETCHFAB_API_BASE}/search"
SKETCHFAB_MODEL_URL = f"{SKETCHFAB_API_BASE}/models"

# Default download directory
DEFAULT_DOWNLOAD_DIR = Path.home() / "SketchUp" / "SCC" / "downloaded_models"

# Supported formats for SketchUp import
SUPPORTED_FORMATS = ["obj", "gltf", "glb"]


def search_models(
    query: str,
    type_filter: str = "models",
    category: str | None = None,
    count: int = 10,
    sort: str = "relevance",
) -> dict[str, Any]:
    """Search Sketchfab for 3D models.

    Args:
        query: Search query string
        type_filter: Filter by type (always "models" for our use case)
        category: Optional category filter (e.g., "furniture", "architecture")
        count: Number of results to return (max 50)
        sort: Sort order - "relevance", "newest", "likes", "views"

    Returns:
        Dict with search results including model list and metadata
    """
    params = {
        "q": query,
        "type": type_filter,
        "count": min(count, 50),
        "sort": sort,
    }

    if category:
        params["category"] = category

    response = requests.get(
        SKETCHFAB_SEARCH_URL,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    # Format results
    results = []
    for model in data.get("results", []):
        uid = model.get("uid")
        name = model.get("name", "Untitled")
        description = model.get("description", "")[:200]

        # Get animated and rigged status
        animated = model.get("animated", False)
        rigged = model.get("rigged", False)
        staffpicks = model.get("staffpicked", False)

        # Get view count and likes
        view_count = model.get("viewCount", 0)
        like_count = model.get("likeCount", 0)

        # Get the viewer URL
        viewer_url = f"https://sketchfab.com/3d-models/{uid}" if uid else None

        # Get downloadable status and formats
        downloadable = model.get("downloadable", False)
        formats = model.get("formats", [])

        results.append({
            "uid": uid,
            "name": name,
            "description": description,
            "viewer_url": viewer_url,
            "animated": animated,
            "rigged": rigged,
            "staffpicks": staffpicks,
            "view_count": view_count,
            "like_count": like_count,
            "downloadable": downloadable,
            "formats": formats,
            "thumbnail_url": model.get("thumbnails", {}).get("images", [{}])[0].get("url"),
        })

    return {
        "query": query,
        "count": len(results),
        "total": data.get("count", 0),
        "next_cursor": data.get("next"),
        "results": results,
    }


def get_model_info(uid: str) -> dict[str, Any]:
    """Get detailed information about a specific Sketchfab model.

    Args:
        uid: Sketchfab model UID

    Returns:
        Detailed model information including all formats and metadata
    """
    response = requests.get(
        f"{SKETCHFAB_MODEL_URL}/{uid}",
        timeout=30,
    )
    response.raise_for_status()

    model = response.json()

    # Extract relevant fields
    return {
        "uid": model.get("uid"),
        "name": model.get("name"),
        "description": model.get("description"),
        "viewer_url": f"https://sketchfab.com/3d-models/{uid}",
        "author": {
            "name": model.get("user", {}).get("displayName"),
            "username": model.get("user", {}).get("username"),
            "profile_url": f"https://sketchfab.com/{model.get('user', {}).get('username')}",
        },
        "license": model.get("license", {}).get("full"),
        "tags": model.get("tags", []),
        "categories": model.get("categories", []),
        "animated": model.get("animated"),
        "rigged": model.get("rigged"),
        "view_count": model.get("viewCount"),
        "like_count": model.get("likeCount"),
        "downloadable": model.get("downloadable"),
        "files": [
            {
                "format": f.get("format"),
                "available": f.get("available"),
                "download_url": f.get("downloadUrl"),
                "size": f.get("size"),
            }
            for f in model.get("files", [])
            if f.get("available")
        ],
        "thumbnails": model.get("thumbnails", {}).get("images", [])[:5],
    }


def download_model(
    uid: str,
    format_hint: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Download a Sketchfab model.

    Downloads the model file (OBJ, GLTF, or GLB) to the specified directory.
    Returns the path to the downloaded file.

    Args:
        uid: Sketchfab model UID
        format_hint: Preferred format ("obj", "gltf", "glb"). If None, picks first available.
        output_dir: Output directory. Defaults to ~/SketchUp/SCC/downloaded_models/

    Returns:
        Dict with download status, file path, and format info
    """
    # Get model info to find download URL
    model_info = get_model_info(uid)

    if not model_info.get("downloadable"):
        return {
            "success": False,
            "error": f"Model '{model_info.get('name')}' is not downloadable",
            "uid": uid,
        }

    # Find the best format
    files = model_info.get("files", [])
    target_format = None
    download_url = None
    file_size = None

    # If format_hint provided, look for it
    if format_hint:
        for f in files:
            if f.get("format", "").lower() == format_hint.lower() and f.get("available"):
                target_format = f.get("format")
                download_url = f.get("download_url")
                file_size = f.get("size")
                break

    # Otherwise pick first available
    if not download_url:
        for f in files:
            fmt = f.get("format", "").lower()
            if fmt in SUPPORTED_FORMATS and f.get("available"):
                target_format = f.get("format")
                download_url = f.get("download_url")
                file_size = f.get("size")
                break

    if not download_url:
        return {
            "success": False,
            "error": "No supported format found for this model",
            "uid": uid,
            "available_formats": [f.get("format") for f in files],
        }

    # Create output directory
    if output_dir is None:
        output_dir = DEFAULT_DOWNLOAD_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    safe_name = "".join(
        c for c in model_info.get("name", uid) if c.isalnum() or c in " -_"
    )[:50]
    extension = target_format.lower()
    filename = f"{safe_name}_{uid}.{extension}"
    output_path = output_dir / filename

    # Download the file
    try:
        print(f"Downloading {model_info.get('name')} ({target_format}) to {output_path}")

        response = requests.get(download_url, timeout=300, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        return {
            "success": True,
            "uid": uid,
            "name": model_info.get("name"),
            "format": target_format,
            "file_path": str(output_path),
            "file_size": file_size or total_size,
            "viewer_url": model_info.get("viewer_url"),
        }

    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Download failed: {str(e)}",
            "uid": uid,
        }


def import_to_sketchup(
    downloaded_path: str,
    position: list[float] | None = None,
    rotation: float = 0.0,
    scale: float = 1.0,
) -> dict[str, Any]:
    """Import a downloaded model into SketchUp.

    Sends the model to the Ruby bridge for import into SketchUp.

    Args:
        downloaded_path: Path to the downloaded model file (OBJ, GLTF, etc.)
        position: [x, y, z] position in mm
        rotation: Rotation around Z-axis in degrees
        scale: Scale factor

    Returns:
        Dict with import result from SketchUp
    """
    from mcp_server.bridge.socket_bridge import SocketBridge
    from mcp_server.protocol.jsonrpc import JsonRpcRequest

    path = Path(downloaded_path)
    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {downloaded_path}",
        }

    extension = path.suffix.lower().lstrip(".")

    # For now, only OBJ is directly importable via SketchUp API
    # GLTF would need conversion
    if extension not in SUPPORTED_FORMATS:
        return {
            "success": False,
            "error": f"Unsupported format: {extension}. Supported: {SUPPORTED_FORMATS}",
        }

    bridge = SocketBridge()
    try:
        bridge.connect()

        # For OBJ files, we can try to import directly
        if extension == "obj":
            # Import the OBJ file into SketchUp
            # Note: SketchUp's import is interactive - this would need UI automation
            # For now, return the path and let user import manually
            return {
                "success": True,
                "message": f"Model downloaded to {downloaded_path}. Use SketchUp's File > Import to add it.",
                "file_path": downloaded_path,
                "format": extension,
                "manual_import_required": True,
            }
        else:
            return {
                "success": True,
                "message": f"Model downloaded to {downloaded_path}. GLTF/GLB conversion not yet automated.",
                "file_path": downloaded_path,
                "format": extension,
                "manual_import_required": True,
            }

    finally:
        bridge.disconnect()


def search_and_download(
    query: str,
    format_hint: str | None = "obj",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Search Sketchfab and download the top result.

    Convenience function that searches for models and downloads
    the first downloadable result.

    Args:
        query: Search query
        format_hint: Preferred format ("obj", "gltf", "glb")
        output_dir: Output directory for downloads

    Returns:
        Dict with search results and download info
    """
    # Search for models
    search_results = search_models(query, count=5)

    if not search_results.get("results"):
        return {
            "success": False,
            "error": f"No models found for query: {query}",
            "search_results": search_results,
        }

    # Try to download the first downloadable model
    for model in search_results.get("results", []):
        if model.get("downloadable"):
            download_result = download_model(
                model["uid"],
                format_hint=format_hint,
                output_dir=output_dir,
            )
            return {
                "success": download_result.get("success", False),
                "search_results": search_results,
                "download": download_result,
            }

    return {
        "success": False,
        "error": "No downloadable models found in results",
        "search_results": search_results,
    }
