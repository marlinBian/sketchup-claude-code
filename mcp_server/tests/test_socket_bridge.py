"""Tests for socket bridge module."""

import pytest
import json
import time
from mcp_server.bridge.socket_bridge import (
    SocketBridge,
    SyncSocketBridge,
    BridgeConfig,
    PingResult,
    ConnectionState,
    create_bridge,
)


class TestBridgeConfig:
    def test_default_config(self):
        config = BridgeConfig()
        assert config.socket_path == "/tmp/su_bridge.sock"
        assert config.connect_timeout == 5.0
        assert config.recv_timeout == 30.0
        assert config.max_retries == 3

    def test_custom_config(self):
        config = BridgeConfig(
            socket_path="/tmp/custom.sock",
            connect_timeout=10.0,
            recv_timeout=60.0,
        )
        assert config.socket_path == "/tmp/custom.sock"
        assert config.connect_timeout == 10.0
        assert config.recv_timeout == 60.0


class TestPingResult:
    def test_successful_ping(self):
        result = PingResult(success=True, latency_ms=5.5)
        assert result.success is True
        assert result.latency_ms == 5.5
        assert result.error is None

    def test_failed_ping(self):
        result = PingResult(success=False, error="Connection refused")
        assert result.success is False
        assert result.error == "Connection refused"
        assert result.latency_ms is None


class TestConnectionState:
    def test_states(self):
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.HANDSHAKE.value == "handshake"


class TestSocketBridge:
    def test_initial_state(self):
        bridge = SocketBridge()
        assert bridge.state == ConnectionState.DISCONNECTED
        assert bridge.is_connected is False

    def test_config_passed_to_constructor(self):
        config = BridgeConfig(socket_path="/tmp/test.sock")
        bridge = SocketBridge(config)
        assert bridge._config.socket_path == "/tmp/test.sock"

    def test_factory_function(self):
        bridge = create_bridge("/tmp/test.sock")
        assert bridge._config.socket_path == "/tmp/test.sock"
        assert isinstance(bridge, SocketBridge)


class TestSyncSocketBridge:
    def test_inherits_from_socket_bridge(self):
        bridge = SyncSocketBridge()
        assert isinstance(bridge, SocketBridge)
