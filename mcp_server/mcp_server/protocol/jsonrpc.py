"""JSON-RPC 2.0 serialization utilities."""

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class JsonRpcRequest:
    """JSON-RPC 2.0 request."""

    method: str
    params: dict[str, Any]
    id: int | str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params,
            "id": self.id,
        }


@dataclass
class JsonRpcSuccess:
    """JSON-RPC 2.0 success response."""

    result: dict[str, Any]
    id: int | str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "jsonrpc": "2.0",
            "result": self.result,
            "id": self.id,
        }


@dataclass
class JsonRpcError:
    """JSON-RPC 2.0 error response."""

    code: int
    message: str
    data: dict[str, Any] | None = None
    id: int | str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        result = {
            "jsonrpc": "2.0",
            "error": {
                "code": self.code,
                "message": self.message,
            },
            "id": self.id,
        }
        if self.data is not None:
            result["error"]["data"] = self.data
        return result


ERROR_CODES = {
    "OPERATION_ERROR": -32000,
    "VALIDATION_ERROR": -32001,
    "UNDO_FAILED": -32002,
    "SKETCHUP_BUSY": -32003,
    "ENTITY_NOT_FOUND": -32004,
    "PERMISSION_DENIED": -32005,
}
