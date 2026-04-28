"""Tests for placement tools module."""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFindComponentByName:
    """Tests for find_component_by_name function."""

    def test_finds_exact_chinese_name(self):
        """Test finding component by exact Chinese name."""
        from mcp_server.tools.placement_tools import find_component_by_name
        # Test with actual library data - Chinese sofa alias exists
        result = find_component_by_name("现代双人沙发")
        assert result is not None
        assert result["id"] == "sofa_modern_2seat"

    def test_finds_exact_english_name(self):
        """Test finding component by exact English name."""
        from mcp_server.tools.placement_tools import find_component_by_name
        # Test with actual library data - "Modern 2-Seat Sofa" alias exists
        result = find_component_by_name("Modern 2-Seat Sofa")
        assert result is not None
        assert result["id"] == "sofa_modern_2seat"

    def test_finds_by_tag(self):
        """Test finding component by tag."""
        from mcp_server.tools.placement_tools import find_component_by_name
        # Test finding by tag
        result = find_component_by_name("sofa")
        assert result is not None

    def test_returns_none_for_missing(self):
        """Test that missing component returns None."""
        from mcp_server.tools.placement_tools import find_component_by_name
        result = find_component_by_name("nonexistent_component_xyz")
        assert result is None


class TestResolveSkpPath:
    """Tests for resolve_skp_path function."""

    def test_resolves_env_var(self):
        """Test resolving SKETCHUP_ASSETS environment variable."""
        import os
        os.environ["SKETCHUP_ASSETS"] = "/test/assets"
        from mcp_server.tools.placement_tools import resolve_skp_path
        result = resolve_skp_path("${SKETCHUP_ASSETS}/test.skp")
        assert "SKETCHUP_ASSETS" not in result
        assert result == "/test/assets/test.skp"

    def test_passes_through_regular_path(self):
        """Test that regular paths are passed through unchanged."""
        from mcp_server.tools.placement_tools import resolve_skp_path
        result = resolve_skp_path("/Users/test/Desktop/model.skp")
        assert result == "/Users/test/Desktop/model.skp"


class TestSearchComponents:
    """Tests for search_components function."""

    def test_search_returns_matches(self):
        """Test that search returns matching components."""
        from mcp_server.tools.placement_tools import search_components
        # Use a query that should match something in the library
        results = search_components("沙发")
        assert len(results) >= 1
        assert all("沙发" in str(r.get("aliases", {})) or "沙发" in str(r.get("tags", [])) for r in results)

    def test_search_respects_limit(self):
        """Test that search respects limit parameter."""
        from mcp_server.tools.placement_tools import search_components
        results = search_components("sofa", limit=5)
        assert len(results) <= 5
