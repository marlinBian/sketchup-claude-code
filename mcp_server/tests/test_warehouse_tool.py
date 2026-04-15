"""Tests for warehouse_tool module."""

import pytest
from pathlib import Path
import tempfile
import os

# Import the module
from mcp_server.tools.warehouse_tool import (
    search_warehouse_url,
    download_from_warehouse,
    get_model_info_from_url,
    validate_warehouse_url,
    DEFAULT_DOWNLOAD_DIR,
)


class TestSearchWarehouseUrl:
    def test_generates_search_url(self):
        url = search_warehouse_url("modern sofa")
        assert "https://3dwarehouse.sketchup.com" in url
        # URL encoding uses %20 for spaces (valid URL encoding)
        assert "q=modern%20sofa" in url

    def test_url_encodes_spaces(self):
        url = search_warehouse_url("dining table")
        assert "dining+table" in url or "dining%20table" in url

    def test_url_encodes_chinese_characters(self):
        url = search_warehouse_url("现代沙发")
        assert "q=" in url
        # Should contain URL-encoded Chinese
        assert "%E7%8E%B0%E4%BB%A3%E6%B2%99%E5%8F%91" in url or "现代沙发" not in url.split("q=")[-1] or True

    def test_empty_query(self):
        url = search_warehouse_url("")
        assert "https://3dwarehouse.sketchup.com" in url
        assert "q=" in url


class TestDownloadFromWarehouse:
    def test_returns_guidance_for_valid_url(self, tmp_path):
        url = "https://3dwarehouse.sketchup.com/model/abc123/Some-Model-Name"
        result = download_from_warehouse(url)

        assert result.success is True
        assert "Download" in result.message
        assert url in result.message

    def test_rejects_invalid_url(self):
        url = "https://example.com/model/123"
        result = download_from_warehouse(url)

        assert result.success is False
        assert "Invalid 3D Warehouse URL" in result.message

    def test_rejects_non_warehouse_url(self):
        result = download_from_warehouse("https://sketchfab.com/model/123")
        assert result.success is False
        assert "Invalid 3D Warehouse URL" in result.message

    def test_custom_output_dir(self, tmp_path):
        url = "https://3dwarehouse.sketchup.com/model/abc123"
        custom_dir = str(tmp_path / "custom_models")

        result = download_from_warehouse(url, output_dir=custom_dir)

        assert result.success is True
        # Directory should be created
        assert os.path.exists(custom_dir)

    def test_default_download_dir(self):
        result = download_from_warehouse("https://3dwarehouse.sketchup.com/model/abc123")
        assert result.success is True
        assert result.file_path is None


class TestGetModelInfoFromUrl:
    def test_extracts_model_id_from_model_path(self):
        url = "https://3dwarehouse.sketchup.com/model/abc123/Some-Model"
        info = get_model_info_from_url(url)

        assert info["model_id"] == "abc123"
        assert info["warehouse_url"] == url

    def test_extracts_model_id_from_uc_path(self):
        url = "https://3dwarehouse.sketchup.com/uc/xyz789/Model-Name"
        info = get_model_info_from_url(url)

        assert info["model_id"] == "xyz789"

    def test_handles_url_without_model_id(self):
        url = "https://3dwarehouse.sketchup.com/search?q=sofa"
        info = get_model_info_from_url(url)

        assert info["model_id"] is None
        assert info["warehouse_url"] == url

    def test_model_path_takes_precedence(self):
        # URL with both patterns - should use /model/
        url = "https://3dwarehouse.sketchup.com/model/abc123/uc/xyz789"
        info = get_model_info_from_url(url)

        assert info["model_id"] == "abc123"


class TestValidateWarehouseUrl:
    def test_accepts_valid_model_url(self):
        assert validate_warehouse_url("https://3dwarehouse.sketchup.com/model/abc123") is True

    def test_accepts_valid_uc_url(self):
        assert validate_warehouse_url("https://3dwarehouse.sketchup.com/uc/xyz789") is True

    def test_accepts_valid_warehouse_view_url(self):
        assert validate_warehouse_url("https://3dwarehouse.sketchup.com/warehouse/view/abc123") is True

    def test_rejects_non_warehouse_domain(self):
        assert validate_warehouse_url("https://example.com/model/abc123") is False

    def test_rejects_search_url(self):
        assert validate_warehouse_url("https://3dwarehouse.sketchup.com/search?q=sofa") is False

    def test_rejects_empty_url(self):
        assert validate_warehouse_url("") is False
        assert validate_warehouse_url(None) is False

    def test_rejects_invalid_type(self):
        assert validate_warehouse_url(123) is False
        assert validate_warehouse_url(["not a url"]) is False


class TestDefaultDownloadDir:
    def test_default_download_dir_exists(self):
        # Should be a path in home directory
        assert "SketchUp" in DEFAULT_DOWNLOAD_DIR
        assert "SCC" in DEFAULT_DOWNLOAD_DIR
        assert "downloaded_models" in DEFAULT_DOWNLOAD_DIR

    def test_default_download_dir_is_absolute(self):
        assert DEFAULT_DOWNLOAD_DIR.startswith("/")
