"""Entity resource: entity://{id}"""

from typing import Any


async def get_entity(entity_id: str) -> dict[str, Any]:
    """Get entity by ID.

    Args:
        entity_id: Entity identifier
    """
    raise NotImplementedError("Pending su_bridge integration")
