"""Tests for canonical project file helpers."""

from pathlib import Path

from mcp_server.resources.project_files import (
    ASSETS_LOCK_FILENAME,
    DESIGN_MODEL_FILENAME,
    DESIGN_RULES_FILENAME,
    LEGACY_DESIGN_MODEL_FILENAME,
    assets_cache_path,
    assets_lock_path,
    design_rules_path,
    find_design_model_path,
)


def test_find_design_model_prefers_canonical(tmp_path):
    canonical = tmp_path / DESIGN_MODEL_FILENAME
    legacy = tmp_path / LEGACY_DESIGN_MODEL_FILENAME
    canonical.write_text("{}", encoding="utf-8")
    legacy.write_text("{}", encoding="utf-8")

    assert find_design_model_path(tmp_path) == canonical


def test_find_design_model_falls_back_to_legacy(tmp_path):
    legacy = tmp_path / LEGACY_DESIGN_MODEL_FILENAME
    legacy.write_text("{}", encoding="utf-8")

    assert find_design_model_path(tmp_path) == legacy


def test_find_design_model_returns_canonical_when_missing(tmp_path):
    assert find_design_model_path(tmp_path) == tmp_path / DESIGN_MODEL_FILENAME


def test_design_rules_path(tmp_path):
    assert design_rules_path(tmp_path) == Path(tmp_path) / DESIGN_RULES_FILENAME


def test_assets_lock_path(tmp_path):
    assert assets_lock_path(tmp_path) == Path(tmp_path) / ASSETS_LOCK_FILENAME


def test_assets_cache_path(tmp_path):
    assert assets_cache_path(tmp_path) == Path(tmp_path) / "assets" / "components"
