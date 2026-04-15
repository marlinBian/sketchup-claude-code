"""Tests for placement tools module."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestFindComponentByName:
    """Tests for find_component_by_name function."""

    @patch('mcp_server.tools.placement_tools.LIBRARY_PATH', new=MagicMock(
        return_value=Path(__file__).parent / 'test_data' / 'library.json'
    ))
    def test_finds_exact_chinese_name(self, tmp_path):
        """Test finding component by exact Chinese name."""
        test_lib_dir = tmp_path / 'test_data'
        test_lib_dir.mkdir()
        library_data = {
            "components": [
                {
                    "id": "sofa_test",
                    "name": "现代双人沙发",
                    "name_en": "Modern Double Sofa",
                    "skp_path": "${SKETCHUP_ASSETS}/test.skp",
                    "tags": ["sofa", "沙发"]
                }
            ]
        }
        (test_lib_dir / 'library.json').write_text(json.dumps(library_data))

        from mcp_server.tools.placement_tools import find_component_by_name
        result = find_component_by_name("现代双人沙发")
        assert result is not None
        assert result["id"] == "sofa_test"

    @patch('mcp_server.tools.placement_tools.LIBRARY_PATH', new=MagicMock(
        return_value=Path(__file__).parent / 'test_data' / 'library.json'
    ))
    def test_finds_exact_english_name(self, tmp_path):
        """Test finding component by exact English name."""
        test_lib_dir = tmp_path / 'test_data'
        test_lib_dir.mkdir()
        library_data = {
            "components": [
                {
                    "id": "sofa_test",
                    "name": "现代双人沙发",
                    "name_en": "Modern Double Sofa",
                    "skp_path": "${SKETCHUP_ASSETS}/test.skp",
                    "tags": ["sofa"]
                }
            ]
        }
        (test_lib_dir / 'library.json').write_text(json.dumps(library_data))

        from mcp_server.tools.placement_tools import find_component_by_name
        result = find_component_by_name("Modern Double Sofa")
        assert result is not None
        assert result["id"] == "sofa_test"

    @patch('mcp_server.tools.placement_tools.LIBRARY_PATH', new=MagicMock(
        return_value=Path(__file__).parent / 'test_data' / 'library.json'
    ))
    def test_finds_by_tag(self, tmp_path):
        """Test finding component by tag."""
        test_lib_dir = tmp_path / 'test_data'
        test_lib_dir.mkdir()
        library_data = {
            "components": [
                {
                    "id": "sofa_test",
                    "name": "现代双人沙发",
                    "name_en": "Modern Double Sofa",
                    "skp_path": "${SKETCHUP_ASSETS}/test.skp",
                    "tags": ["sofa", "seating"]
                }
            ]
        }
        (test_lib_dir / 'library.json').write_text(json.dumps(library_data))

        from mcp_server.tools.placement_tools import find_component_by_name
        result = find_component_by_name("seating")
        assert result is not None
        assert result["id"] == "sofa_test"

    @patch('mcp_server.tools.placement_tools.LIBRARY_PATH', new=MagicMock(
        return_value=Path(__file__).parent / 'test_data' / 'library.json'
    ))
    def test_returns_none_for_missing(self, tmp_path):
        """Test that missing component returns None."""
        test_lib_dir = tmp_path / 'test_data'
        test_lib_dir.mkdir()
        library_data = {"components": []}
        (test_lib_dir / 'library.json').write_text(json.dumps(library_data))

        from mcp_server.tools.placement_tools import find_component_by_name
        result = find_component_by_name("nonexistent")
        assert result is None


class TestResolveSkpPath:
    """Tests for resolve_skp_path function."""

    def test_resolves_env_var(self):
        """Test resolving SKETCHUP_ASSETS environment variable."""
        from mcp_server.tools.placement_tools import resolve_skp_path
        result = resolve_skp_path("${SKETCHUP_ASSETS}/test.skp")
        assert "SKETCHUP_ASSETS" not in result
        assert result.endswith("/test.skp")

    def test_passes_through_regular_path(self):
        """Test that regular paths are passed through unchanged."""
        from mcp_server.tools.placement_tools import resolve_skp_path
        result = resolve_skp_path("/Users/test/Desktop/model.skp")
        assert result == "/Users/test/Desktop/model.skp"


class TestSearchComponents:
    """Tests for search_components function."""

    @patch('mcp_server.tools.placement_tools.LIBRARY_PATH', new=MagicMock(
        return_value=Path(__file__).parent / 'test_data' / 'library.json'
    ))
    def test_search_returns_matches(self, tmp_path):
        """Test that search returns matching components."""
        test_lib_dir = tmp_path / 'test_data'
        test_lib_dir.mkdir()
        library_data = {
            "components": [
                {"id": "sofa_1", "name": "沙发A", "name_en": "Sofa A", "tags": ["sofa"]},
                {"id": "sofa_2", "name": "沙发B", "name_en": "Sofa B", "tags": ["sofa"]},
                {"id": "table_1", "name": "桌子A", "name_en": "Table A", "tags": ["table"]}
            ]
        }
        (test_lib_dir / 'library.json').write_text(json.dumps(library_data))

        from mcp_server.tools.placement_tools import search_components
        results = search_components("沙发")
        assert len(results) == 2
        assert all("沙发" in r["name"] for r in results)

    @patch('mcp_server.tools.placement_tools.LIBRARY_PATH', new=MagicMock(
        return_value=Path(__file__).parent / 'test_data' / 'library.json'
    ))
    def test_search_respects_limit(self, tmp_path):
        """Test that search respects limit parameter."""
        test_lib_dir = tmp_path / 'test_data'
        test_lib_dir.mkdir()
        library_data = {
            "components": [
                {"id": f"sofa_{i}", "name": f"沙发{i}", "name_en": f"Sofa {i}", "tags": ["sofa"]}
                for i in range(10)
            ]
        }
        (test_lib_dir / 'library.json').write_text(json.dumps(library_data))

        from mcp_server.tools.placement_tools import search_components
        results = search_components("沙发", limit=3)
        assert len(results) == 3
