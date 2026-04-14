"""Unix socket bridge to su_bridge Ruby plugin."""

import socket
import json
import time
from typing import Any
from dataclasses import dataclass, field
from enum import Enum


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    HANDSHAKE = "handshake"


@dataclass
class BridgeConfig:
    """Configuration for socket bridge."""

    socket_path: str = "/tmp/su_bridge.sock"
    connect_timeout: float = 5.0
    recv_timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 0.5
    ping_interval: float = 30.0
    ping_timeout: float = 5.0


@dataclass
class PingResult:
    """Result of a ping operation."""

    success: bool
    latency_ms: float | None = None
    error: str | None = None


class SocketBridge:
    """Unix domain socket client to su_bridge with ping/pong support."""

    def __init__(self, config: BridgeConfig | None = None):
        self._config = config or BridgeConfig()
        self._socket: socket.socket | None = None
        self._state = ConnectionState.DISCONNECTED
        self._last_pong_time: float | None = None

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected and handshake complete."""
        return self._state == ConnectionState.CONNECTED

    def connect(self) -> None:
        """Connect to the su_bridge socket with retry logic."""
        if self._state == ConnectionState.CONNECTED:
            return

        last_error = None
        for attempt in range(self._config.max_retries):
            try:
                self._state = ConnectionState.CONNECTING
                self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._socket.settimeout(self._config.connect_timeout)
                self._socket.connect(self._config.socket_path)
                self._state = ConnectionState.CONNECTED
                self._last_pong_time = None
                return
            except (socket.error, OSError) as e:
                last_error = e
                self._cleanup_socket()
                if attempt < self._config.max_retries - 1:
                    time.sleep(self._config.retry_delay)

        self._state = ConnectionState.DISCONNECTED
        raise ConnectionError(f"Failed to connect after {self._config.max_retries} attempts: {last_error}")

    def disconnect(self) -> None:
        """Disconnect from the socket."""
        self._state = ConnectionState.DISCONNECTED
        self._cleanup_socket()

    def _cleanup_socket(self) -> None:
        """Clean up socket resource."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def send(self, data: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC request and receive response with timeout.

        Creates a fresh connection for each request since the Ruby server
        closes the connection after each response.
        """
        # Always create fresh connection - Ruby server closes after each request
        self.disconnect()
        self.connect()

        if self._state not in (ConnectionState.CONNECTED, ConnectionState.HANDSHAKE):
            raise ConnectionError(f"Not connected (state: {self._state.value})")

        self._socket.settimeout(self._config.recv_timeout)

        try:
            message = json.dumps(data) + "\n"
            self._socket.sendall(message.encode("utf-8"))

            response_data = self._socket.recv(65536).decode("utf-8")
            if not response_data:
                raise ConnectionError("Empty response from server")

            return json.loads(response_data)
        except socket.timeout:
            raise TimeoutError(f"Request timed out after {self._config.recv_timeout}s")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")

    def ping(self) -> PingResult:
        """Send ping and wait for pong response."""
        start_time = time.monotonic()

        try:
            response = self.send({
                "jsonrpc": "2.0",
                "method": "ping",
                "params": {
                    "timestamp": start_time,
                },
                "id": f"ping_{int(start_time * 1000)}",
            })

            latency_ms = (time.monotonic() - start_time) * 1000

            if response.get("result", {}).get("status") == "pong":
                self._last_pong_time = time.monotonic()
                return PingResult(success=True, latency_ms=latency_ms)

            return PingResult(success=False, error="Invalid pong response")

        except Exception as e:
            return PingResult(success=False, error=str(e))

    def wait_for_connection(self, timeout: float = 10.0) -> bool:
        """Wait for server to be ready with ping/pong."""
        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            try:
                if self._state != ConnectionState.CONNECTED:
                    self.connect()

                result = self.ping()
                if result.success:
                    return True
            except Exception:
                pass

            time.sleep(0.5)

        return False

    def __enter__(self) -> "SocketBridge":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def __del__(self) -> None:
        self._cleanup_socket()


class SyncSocketBridge(SocketBridge):
    """Synchronous wrapper for SocketBridge with blocking operations."""

    def __init__(self, config: BridgeConfig | None = None):
        super().__init__(config)
        self._request_queue: list[dict[str, Any]] = []
        self._response_map: dict[str, dict[str, Any]] = {}

    def send_and_wait(self, data: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        """Send request and wait for response (blocking)."""
        request_id = data.get("id", f"req_{time.monotonic()}")
        data["id"] = request_id

        self._socket.settimeout(timeout or self._config.recv_timeout)

        message = json.dumps(data) + "\n"
        self._socket.sendall(message.encode("utf-8"))

        response_data = self._socket.recv(65536).decode("utf-8")
        return json.loads(response_data)


def create_bridge(socket_path: str = "/tmp/su_bridge.sock") -> SocketBridge:
    """Factory function to create a configured bridge."""
    config = BridgeConfig(socket_path=socket_path)
    return SocketBridge(config)
