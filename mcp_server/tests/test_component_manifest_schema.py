"""Tests for component library manifest schema."""

from pathlib import Path

from mcp_server.resources.component_manifest_schema import (
    load_component_library,
    validate_component_library,
)


def test_bathroom_component_fixture_is_valid():
    fixture_path = (
        Path(__file__).parent / "fixtures" / "bathroom" / "component_library.json"
    )

    data, errors = load_component_library(fixture_path)

    assert errors == []
    assert data is not None
    assert data["components"][0]["id"] == "toilet_floor_mounted_basic"


def test_packaged_component_library_is_valid():
    library_path = (
        Path(__file__).parents[1]
        / "mcp_server"
        / "assets"
        / "library.json"
    )

    data, errors = load_component_library(library_path)

    assert errors == []
    assert data is not None
    component_ids = {component["id"] for component in data["components"]}
    assert "toilet_floor_mounted_basic" in component_ids
    assert "vanity_wall_600" in component_ids
    assert "bathroom_door_700" in component_ids


def test_missing_license_fails_validation():
    data = {
        "version": "1.0",
        "components": [
            {
                "id": "fixture_without_license",
                "name": "Fixture without license",
                "category": "fixture",
                "dimensions": {"width": 100, "depth": 100, "height": 100},
                "bounds": {"min": [0, 0, 0], "max": [100, 100, 100]},
                "insertion_point": {
                    "offset": [0, 0, 0],
                    "description": "Origin",
                },
                "anchors": {"bottom": "floor"},
                "clearance": {},
                "assets": {"skp_path": "fixtures/missing.skp"},
                "aliases": {"en": ["fixture"]},
            }
        ],
    }

    is_valid, errors = validate_component_library(data)

    assert is_valid is False
    assert any("license" in error for error in errors)


def test_negative_clearance_fails_validation():
    fixture_path = (
        Path(__file__).parent / "fixtures" / "bathroom" / "component_library.json"
    )
    data, errors = load_component_library(fixture_path)
    assert data is not None
    assert errors == []
    data["components"][0]["clearance"]["front"] = -1

    is_valid, validation_errors = validate_component_library(data)

    assert is_valid is False
    assert any("front" in error for error in validation_errors)
