"""Tests for export tools (glTF and IFC export)."""

import json
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


class TestSaveSkpModel:
    """Tests for save_skp_model function."""

    @pytest.mark.asyncio
    @patch('mcp_server.tools.export_tools.SocketBridge')
    async def test_save_skp_model_basic(self, mock_bridge_class):
        """Test basic SketchUp model save call."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_bridge.send.return_value = {
            "result": {
                "status": "success",
                "save_info": {
                    "format": "skp",
                    "output_path": "/tmp/model.skp",
                },
            }
        }

        from mcp_server.tools.export_tools import save_skp_model
        result = await save_skp_model("/tmp/model.skp")

        mock_bridge.connect.assert_called_once()
        mock_bridge.send.assert_called_once()
        mock_bridge.disconnect.assert_called_once()

        call_args = mock_bridge.send.call_args[0][0]
        assert call_args["params"]["operation_type"] == "save_model"
        assert call_args["params"]["payload"]["output_path"] == "/tmp/model.skp"
        assert call_args["params"]["rollback_on_failure"] is False
        assert result["save_info"]["format"] == "skp"

    @pytest.mark.asyncio
    @patch('mcp_server.tools.export_tools.SocketBridge')
    async def test_save_skp_model_error(self, mock_bridge_class):
        """Test SketchUp model save error handling."""
        mock_bridge = MagicMock()
        mock_bridge_class.return_value = mock_bridge
        mock_bridge.send.return_value = {
            "error": {
                "code": -32001,
                "message": "Model save failed",
            }
        }

        from mcp_server.tools.export_tools import save_skp_model

        with pytest.raises(RuntimeError, match="Model save failed"):
            await save_skp_model("/tmp/model.skp")

        mock_bridge.disconnect.assert_called_once()


def test_cli_save_skp_outputs_json(monkeypatch, capsys):
    """Test CLI save-skp command output."""
    from mcp_server import cli

    async def fake_save_skp_model(output_path):
        return {
            "status": "success",
            "save_info": {
                "format": "skp",
                "output_path": output_path,
            },
        }

    monkeypatch.setattr(cli, "save_skp_model", fake_save_skp_model)

    exit_code = cli.main(["save-skp", "/tmp/model.skp"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["save_info"]["output_path"] == "/tmp/model.skp"
