"""Tests for project asset lock schema."""

import copy
import json
from pathlib import Path

from mcp_server.resources.asset_lock_schema import (
    build_assets_lock,
    component_refs_from_design_model,
    create_empty_assets_lock,
    load_assets_lock,
    validate_assets_lock,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "bathroom"


def load_fixture(name: str) -> dict:
    """Load a bathroom fixture JSON file."""
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_empty_assets_lock_is_valid():
    lock = create_empty_assets_lock()

    is_valid, errors = validate_assets_lock(lock)

    assert is_valid is True
    assert errors == []
    assert lock["cache"]["root"] == "assets/components"
    assert lock["assets"] == []


def test_component_refs_include_components_and_lighting():
    design_model = load_fixture("design_model.json")

    refs = component_refs_from_design_model(design_model)

    assert refs["toilet_floor_mounted_basic"] == ["toilet_001"]
    assert refs["ceiling_light_basic"] == ["ceiling_light_001"]


def test_build_assets_lock_from_bathroom_design_model():
    design_model = load_fixture("design_model.json")
    library = load_fixture("component_library.json")

    lock = build_assets_lock(design_model, library)

    is_valid, errors = validate_assets_lock(lock)
    component_ids = {asset["component_id"] for asset in lock["assets"]}

    assert is_valid is True
    assert errors == []
    assert "toilet_floor_mounted_basic" in component_ids
    assert "ceiling_light_basic" in component_ids
    toilet = next(
        asset
        for asset in lock["assets"]
        if asset["component_id"] == "toilet_floor_mounted_basic"
    )
    assert toilet["source"]["kind"] == "seed"
    assert toilet["source"]["license"] == "unknown"
    assert toilet["cache"]["path"] == (
        "assets/components/toilet_floor_mounted_basic.skp"
    )
    assert toilet["procedural_fallback"] == "box_fixture"


def test_build_assets_lock_marks_project_cache_hit(tmp_path):
    design_model = load_fixture("design_model.json")
    library = load_fixture("component_library.json")
    cached_asset = tmp_path / "assets" / "components" / "toilet_floor_mounted_basic.skp"
    cached_asset.parent.mkdir(parents=True)
    cached_asset.write_text("skp placeholder", encoding="utf-8")

    lock = build_assets_lock(design_model, library, project_path=tmp_path)

    toilet = next(
        asset
        for asset in lock["assets"]
        if asset["component_id"] == "toilet_floor_mounted_basic"
    )
    assert toilet["cache"]["status"] == "cached"
    assert toilet["cache"]["path"] == "assets/components/toilet_floor_mounted_basic.skp"


def test_missing_component_ref_is_recorded_as_missing():
    design_model = copy.deepcopy(load_fixture("design_model.json"))
    library = load_fixture("component_library.json")
    design_model["components"]["unknown_001"] = {
        "name": "Unknown placeholder",
        "component_ref": "unknown_component",
    }

    lock = build_assets_lock(design_model, library)

    missing = next(
        asset for asset in lock["assets"] if asset["component_id"] == "unknown_component"
    )
    assert missing["category"] == "other"
    assert missing["cache"]["status"] == "missing"
    assert missing["source"]["kind"] == "unknown"


def test_missing_source_fails_validation():
    lock = create_empty_assets_lock()
    lock["assets"].append(
        {
            "component_id": "bad_component",
            "component_name": "Bad Component",
            "category": "fixture",
            "used_by": ["bad_001"],
            "paths": {},
            "cache": {
                "status": "referenced",
                "path": "assets/components/bad_component.skp",
            },
        }
    )

    is_valid, errors = validate_assets_lock(lock)

    assert is_valid is False
    assert any("source" in error for error in errors)


def test_load_assets_lock(tmp_path):
    lock_path = tmp_path / "assets.lock.json"
    lock_path.write_text(
        json.dumps(create_empty_assets_lock(), indent=2) + "\n",
        encoding="utf-8",
    )

    data, errors = load_assets_lock(lock_path)

    assert errors == []
    assert data is not None
    assert data["version"] == "1.0"
