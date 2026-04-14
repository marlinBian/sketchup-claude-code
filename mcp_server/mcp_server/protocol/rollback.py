"""Rollback support for atomic operations."""

from dataclasses import dataclass, field
from typing import Any, Callable
import uuid


@dataclass
class OperationContext:
    """Context for an atomic operation."""

    operation_id: str = field(default_factory=lambda: f"op_{uuid.uuid4().hex[:8]}")
    rollback_on_failure: bool = True
    status: str = "pending"


class RollbackManager:
    """Manages operation rollback state."""

    def __init__(self):
        self._operations: dict[str, OperationContext] = {}

    def begin(self, operation_id: str, rollback_on_failure: bool = True) -> OperationContext:
        """Begin an operation context."""
        ctx = OperationContext(
            operation_id=operation_id,
            rollback_on_failure=rollback_on_failure,
            status="in_progress",
        )
        self._operations[operation_id] = ctx
        return ctx

    def commit(self, operation_id: str) -> None:
        """Mark operation as committed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = "success"

    def rollback(self, operation_id: str) -> None:
        """Mark operation for rollback."""
        if operation_id in self._operations:
            self._operations[operation_id].status = "rollback"

    def get(self, operation_id: str) -> OperationContext | None:
        """Get operation context."""
        return self._operations.get(operation_id)
