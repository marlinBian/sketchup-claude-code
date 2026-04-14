"""Model resource: model://current"""

from typing import Any


async def get_current_model() -> dict[str, Any]:
    """Get the current SketchUp model state."""
    raise NotImplementedError("Pending su_bridge integration")
