"""Tests for local_library_search module."""

import pytest
from pathlib import Path
import json
import tempfile
import os

# Import the module
from mcp_server.tools.local_library_search import (
    fuzzy_match,
    search_library,
    get_categories,
    get_components_by_category,
    format_search_results,
    load_library,
)


@pytest.fixture
def sample_library():
    """Sample library data for testing."""
    return {
        "components": [
            {
                "id": "sofa_modern_double",
                "name": "现代双人沙发",
                "name_en": "Modern Double Sofa",
                "category": "furniture",
                "skp_path": "${SKETCHUP_ASSETS}/furniture/sofa_modern_double.skp",
                "default_dimensions": {"width": 1800, "depth": 900, "height": 850},
                "style_tags": ["modern", "grey", "fabric"]
            },
            {
                "id": "sofa_vintage_single",
                "name": "复古单人沙发",
                "name_en": "Vintage Single Sofa",
                "category": "furniture",
                "skp_path": "${SKETCHUP_ASSETS}/furniture/sofa_vintage_single.skp",
                "default_dimensions": {"width": 900, "depth": 800, "height": 900},
                "style_tags": ["vintage", "brown", "leather"]
            },
            {
                "id": "dining_table_oak",
                "name": "橡木餐桌",
                "name_en": "Oak Dining Table",
                "category": "furniture",
                "skp_path": "${SKETCHUP_ASSETS}/furniture/dining_table_oak.skp",
                "default_dimensions": {"width": 1400, "depth": 800, "height": 750},
                "style_tags": ["oak", "natural", "wood"]
            },
            {
                "id": "floor_lamp_modern",
                "name": "现代落地灯",
                "name_en": "Modern Floor Lamp",
                "category": "lighting",
                "skp_path": "${SKETCHUP_ASSETS}/lighting/floor_lamp_modern.skp",
                "default_dimensions": {"width": 400, "depth": 400, "height": 1800},
                "style_tags": ["modern", "black", "metal"]
            },
            {
                "id": "chandelier_classic",
                "name": "经典吊灯",
                "name_en": "Classic Chandelier",
                "category": "lighting",
                "skp_path": "${SKETCHUP_ASSETS}/lighting/chandelier_classic.skp",
                "style_tags": ["classic", "gold", "crystal"]
            }
        ]
    }


class TestFuzzyMatch:
    def test_exact_substring_match(self):
        is_match, score = fuzzy_match("sofa", "modern sofa")
        assert is_match is True
        assert score == 1.0

    def test_partial_word_match(self):
        is_match, score = fuzzy_match("sofa", "sofas and chairs")
        assert is_match is True
        assert score == 1.0

    def test_no_match(self):
        is_match, score = fuzzy_match("sofa", "table")
        assert is_match is False
        assert score == 0.0

    def test_empty_query(self):
        is_match, score = fuzzy_match("", "something")
        assert is_match is False

    def test_chinese_characters(self):
        is_match, score = fuzzy_match("沙发", "现代双人沙发")
        assert is_match is True


class TestSearchLibrary:
    def test_search_finds_sofa(self, sample_library):
        results = search_library("sofa", library_data=sample_library)
        assert len(results) == 2
        assert all("sofa" in r["name_en"].lower() or "沙发" in r["name"] for r in results)

    def test_search_filters_by_category(self, sample_library):
        results = search_library("lamp", category="lighting", library_data=sample_library)
        assert len(results) == 2
        assert all(r["category"] == "lighting" for r in results)

    def test_search_returns_scores(self, sample_library):
        results = search_library("sofa", library_data=sample_library)
        assert all("_match_score" in r for r in results)

    def test_search_respects_limit(self, sample_library):
        results = search_library("sofa", limit=1, library_data=sample_library)
        assert len(results) == 1

    def test_search_sorted_by_score(self, sample_library):
        results = search_library("modern", library_data=sample_library)
        scores = [r["_match_score"] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestGetCategories:
    def test_returns_all_categories(self, sample_library):
        categories = get_categories(sample_library)
        assert set(categories) == {"furniture", "lighting"}

    def test_empty_library(self):
        categories = get_categories({"components": []})
        assert categories == []


class TestGetComponentsByCategory:
    def test_returns_category_components(self, sample_library):
        furniture = get_components_by_category("furniture", sample_library)
        assert len(furniture) == 3
        assert all(c["category"] == "furniture" for c in furniture)

    def test_returns_empty_for_unknown_category(self, sample_library):
        result = get_components_by_category("unknown", sample_library)
        assert result == []


class TestFormatSearchResults:
    def test_formats_results(self, sample_library):
        results = search_library("sofa", library_data=sample_library)
        formatted = format_search_results(results)
        assert "1." in formatted
        assert "Modern Double Sofa" in formatted

    def test_empty_results(self):
        formatted = format_search_results([])
        assert "No matching" in formatted

    def test_without_score(self, sample_library):
        results = search_library("sofa", library_data=sample_library)
        formatted = format_search_results(results, include_score=False)
        assert "score:" not in formatted


class TestLoadLibrary:
    def test_returns_empty_for_missing_file(self, tmp_path, monkeypatch):
        # Create a temporary module that points to non-existent file
        monkeypatch.setattr(
            "mcp_server.tools.local_library_search.LIBRARY_PATH",
            tmp_path / "nonexistent.json"
        )
        library = load_library()
        assert library == {"components": []}
