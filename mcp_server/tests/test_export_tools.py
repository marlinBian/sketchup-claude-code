"""Tests for export tools (glTF and IFC export)."""

import pytest
from unittest.mock import patch, MagicMock


class TestExportGltf:
    """Tests for export_gltf function."""

    @pytest.mark.asyncio
    @patch('mcp_server.tools.export_tools.SocketBridge')
    async def test_export_gltf_basic(self, mock_bridge_class):
        """Test basic glTF export call."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_bridge.send.return_value = {
            "result": {
                "status": "success",
                "output_path": "/tmp/model.gltf",
            }
        }

        from mcp_server.tools.export_tools import export_gltf
        result = await export_gltf("/tmp/model.gltf")

        mock_bridge.connect.assert_called_once()
        mock_bridge.send.assert_called_once()
        mock_bridge.disconnect.assert_called_once()

        # Verify the request format
        call_args = mock_bridge.send.call_args[0][0]
        assert call_args["params"]["operation_type"] == "export_gltf"
        assert call_args["params"]["payload"]["output_path"] == "/tmp/model.gltf"
        assert call_args["params"]["payload"]["include_textures"] is True

    @pytest.mark.asyncio
    @patch('mcp_server.tools.export_tools.SocketBridge')
    async def test_export_gltf_without_textures(self, mock_bridge_class):
        """Test glTF export without textures."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_bridge.send.return_value = {"result": {"status": "success"}}

        from mcp_server.tools.export_tools import export_gltf
        result = await export_gltf("/tmp/model.gltf", include_textures=False)

        call_args = mock_bridge.send.call_args[0][0]
        assert call_args["params"]["payload"]["include_textures"] is False

    @pytest.mark.asyncio
    @patch('mcp_server.tools.export_tools.SocketBridge')
    async def test_export_gltf_error(self, mock_bridge_class):
        """Test glTF export error handling."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_bridge.send.return_value = {
            "error": {
                "code": -32001,
                "message": "Export failed"
            }
        }

        from mcp_server.tools.export_tools import export_gltf

        with pytest.raises(RuntimeError, match="Export failed"):
            await export_gltf("/tmp/model.gltf")

        mock_bridge.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch('mcp_server.tools.export_tools.SocketBridge')
    async def test_export_gltf_disconnect_on_exception(self, mock_bridge_class):
        """Test that bridge disconnects even on exception."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_bridge.connect.side_effect = ConnectionRefusedError("Connection refused")

        from mcp_server.tools.export_tools import export_gltf

        with pytest.raises(ConnectionRefusedError):
            await export_gltf("/tmp/model.gltf")

        # disconnect should still be called via finally
        mock_bridge.disconnect.assert_called_once()


class TestExportIfc:
    """Tests for export_ifc function."""

    @pytest.mark.asyncio
    @patch('mcp_server.tools.export_tools.SocketBridge')
    async def test_export_ifc_basic(self, mock_bridge_class):
        """Test basic IFC export call."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_bridge.send.return_value = {
            "result": {
                "status": "success",
                "output_path": "/tmp/model.ifc",
            }
        }

        from mcp_server.tools.export_tools import export_ifc
        result = await export_ifc("/tmp/model.ifc")

        mock_bridge.connect.assert_called_once()
        mock_bridge.send.assert_called_once()
        mock_bridge.disconnect.assert_called_once()

        # Verify the request format
        call_args = mock_bridge.send.call_args[0][0]
        assert call_args["params"]["operation_type"] == "export_ifc"
        assert call_args["params"]["payload"]["output_path"] == "/tmp/model.ifc"

    @pytest.mark.asyncio
    @patch('mcp_server.tools.export_tools.SocketBridge')
    async def test_export_ifc_error(self, mock_bridge_class):
        """Test IFC export error handling."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_bridge.send.return_value = {
            "error": {
                "code": -32001,
                "message": "IFC export not supported"
            }
        }

        from mcp_server.tools.export_tools import export_ifc

        with pytest.raises(RuntimeError, match="IFC export not supported"):
            await export_ifc("/tmp/model.ifc")

        mock_bridge.disconnect.assert_called_once()
