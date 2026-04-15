"""SketchUp 3D Warehouse Tool.

Note: SketchUp 3D Warehouse does not have a public API.
This tool provides functionality to:
1. Guide users to find models on 3D Warehouse
2. Allow user to provide a Warehouse URL
3. Download the model via SketchUp's import functionality
"""

from dataclasses import dataclass
from typing import Optional
import os
import re
from urllib.parse import quote

# Default download directory
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/SketchUp/SCC/downloaded_models")


@dataclass
class WarehouseResult:
    """Result from warehouse operation."""
    success: bool
    message: str
    file_path: Optional[str] = None


def search_warehouse_url(query: str) -> str:
    """Generate a 3D Warehouse search URL for user.

    Args:
        query: Search query

    Returns:
        URL to open in browser
    """
    # 3D Warehouse uses Trimble ID for authentication
    # Search URL format
    base_url = "https://3dwarehouse.sketchup.com"
    search_path = f"/search?q={quote(query)}"
    return f"{base_url}{search_path}"


def download_from_warehouse(warehouse_url: str, output_dir: str = DEFAULT_DOWNLOAD_DIR) -> WarehouseResult:
    """Download a model from 3D Warehouse URL.

    This requires user to:
    1. Navigate to the model page in browser
    2. Click "Download" button
    3. SketchUp will handle the actual download

    This function provides guidance for the user.

    Args:
        warehouse_url: Full URL to the 3D Warehouse model page
        output_dir: Where to save downloaded files

    Returns:
        WarehouseResult with guidance message
    """
    # Validate URL is a valid 3D Warehouse URL
    if "3dwarehouse.sketchup.com" not in warehouse_url:
        return WarehouseResult(
            success=False,
            message="Invalid 3D Warehouse URL. Please provide a URL from 3dwarehouse.sketchup.com"
        )

    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)

    # Guide user through manual download process
    message = f"""To download from 3D Warehouse:

1. Open this URL in your browser:
   {warehouse_url}

2. Click the "Download" button on the model page

3. In SketchUp, use File > Import to bring in the downloaded file

4. Place and position the imported model using move_entity

The downloaded file is typically saved to your browser's download folder.
"""
    return WarehouseResult(
        success=True,
        message=message,
        file_path=None
    )


def get_model_info_from_url(warehouse_url: str) -> dict:
    """Get basic model info from warehouse URL (without API).

    This does a best-effort extraction of model info from URL patterns.

    Args:
        warehouse_url: Full URL to the 3D Warehouse model page

    Returns:
        Dict with model_id and URL
    """
    # Extract model ID from URL patterns like:
    # https://3dwarehouse.sketchup.com/model/abc123/...
    # or
    # https://3dwarehouse.sketchup.com/uc/abc123/...

    model_id = None

    # Try to extract from /model/ path
    if "/model/" in warehouse_url:
        parts = warehouse_url.split("/model/")[-1].split("/")
        if parts:
            model_id = parts[0]

    # Try to extract from /uc/ path
    if "/uc/" in warehouse_url and not model_id:
        parts = warehouse_url.split("/uc/")[-1].split("/")
        if parts:
            model_id = parts[0]

    return {
        "model_id": model_id,
        "warehouse_url": warehouse_url,
        "note": "Model info extracted from URL. Full metadata requires manual verification."
    }


def validate_warehouse_url(url: str) -> bool:
    """Validate that a URL is a valid 3D Warehouse URL format.

    Args:
        url: URL to validate

    Returns:
        True if URL appears to be a valid 3D Warehouse URL
    """
    if not url or not isinstance(url, str):
        return False

    # Check for 3dwarehouse.sketchup.com domain
    if "3dwarehouse.sketchup.com" not in url:
        return False

    # Check for valid URL patterns
    valid_patterns = [
        r"/model/[a-zA-Z0-9]+",
        r"/uc/[a-zA-Z0-9]+",
        r"/warehouse/view/[a-zA-Z0-9]+",
    ]

    return any(re.search(pattern, url) for pattern in valid_patterns)
