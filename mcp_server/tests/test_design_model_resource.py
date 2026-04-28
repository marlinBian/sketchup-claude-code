"""Tests for design_model_resource.py."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

# Sample design model data for testing
SAMPLE_DESIGN_MODEL = {
    "version": "1.0",
    "project_name": "test_project",
    "components": {
        "sofa_001": {
            "id": "sofa_001",
            "type": "sofa",
            "name": "现代双人沙发",
            "position": [1000, 2000, 0],
            "semantic_anchor": {
                "center": [1000, 2000, 450],
                "seat_height": [1000, 2000, 450],
                "back_top": [1000, 2000, 900],
            },
            "layer": "Furniture",
        },
        "table_001": {
            "id": "table_001",
            "type": "table",
            "name": "实木餐桌",
            "position": [3000, 2000, 0],
            "semantic_anchor": {
                "center": [3000, 2000, 750],
                "above_position": {
                    "height_offset": 1200,
                    "used_for": ["light_001"],
                },
            },
            "layer": "Furniture",
        },
        "light_001": {
            "id": "light_001",
            "type": "lighting",
            "name": "餐吊灯",
            "position": [3000, 2000, 1950],
            "layer": "Lighting",
        },
    },
    "spaces": {
        "living_room": {
            "id": "living_room",
            "name": "客厅",
            "bounds": [[0, 0], [5000, 6000]],
            "ceiling_height": 2800,
        },
        "dining_area": {
            "id": "dining_area",
            "name": "餐厅",
            "bounds": [[3000, 0], [6000, 4000]],
            "ceiling_height": 2800,
        },
    },
    "layers": {
        "Walls": [
            {"id": "wall_001", "type": "wall"},
            {"id": "wall_002", "type": "wall"},
        ],
        "Lighting": [],  # Note: Furniture not in layers - will use entities fallback
    },
    "entities": {
        "wall_001": {
            "id": "wall_001",
            "type": "wall",
            "layer": "Walls",
            "bounds": [[0, 0], [5000, 0]],
        },
        "chair_001": {
            "id": "chair_001",
            "type": "chair",
            "layer": "Furniture",
        },
    },
}


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with design_model.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        model_path = project_path / "design_model.json"
        with open(model_path, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_DESIGN_MODEL, f, ensure_ascii=False, indent=2)

        yield str(project_path)


@pytest.fixture
def legacy_project_dir():
    """Create a temporary project directory with legacy .design_model.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        model_path = project_path / ".design_model.json"
        with open(model_path, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_DESIGN_MODEL, f, ensure_ascii=False, indent=2)

        yield str(project_path)


@pytest.fixture
def empty_project_dir():
    """Create an empty project directory with no design model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        # Don't create .design_model.json
        yield str(project_path)


class TestGetDesignModel:
    """Tests for get_design_model resource."""

    @pytest.mark.asyncio
    async def test_read_valid_project(self, temp_project_dir):
        """Test reading a project that exists with valid design_model.json."""
        from mcp_server.resources.design_model_resource import get_design_model

        result = await get_design_model(temp_project_dir)

        assert result["version"] == "1.0"
        assert "components" in result
        assert "spaces" in result

    @pytest.mark.asyncio
    async def test_read_legacy_hidden_project(self, legacy_project_dir):
        """Test migration fallback for legacy .design_model.json projects."""
        from mcp_server.resources.design_model_resource import get_design_model

        result = await get_design_model(legacy_project_dir)

        assert result["project_name"] == "test_project"

    @pytest.mark.asyncio
    async def test_missing_project(self, empty_project_dir):
        """Test reading a project directory that doesn't exist."""
        from mcp_server.resources.design_model_resource import get_design_model

        # Point to a non-existent path
        nonexistent = empty_project_dir + "_nonexistent"
        with pytest.raises(FileNotFoundError, match="Design model not found"):
            await get_design_model(nonexistent)

    @pytest.mark.asyncio
    async def test_empty_project(self, empty_project_dir):
        """Test reading a project directory with no .design_model.json."""
        from mcp_server.resources.design_model_resource import get_design_model

        with pytest.raises(FileNotFoundError, match="Design model not found"):
            await get_design_model(empty_project_dir)


class TestListComponents:
    """Tests for list_components resource."""

    @pytest.mark.asyncio
    async def test_list_all_components(self, temp_project_dir):
        """Test listing all components."""
        from mcp_server.resources.design_model_resource import list_components

        result = await list_components(temp_project_dir)

        assert "components" in result
        components = result["components"]
        assert len(components) == 3
        ids = {c["id"] for c in components}
        assert ids == {"sofa_001", "table_001", "light_001"}

    @pytest.mark.asyncio
    async def test_components_include_type_for_filtering(self, temp_project_dir):
        """Test that components include type field for client-side filtering."""
        from mcp_server.resources.design_model_resource import list_components

        result = await list_components(temp_project_dir)

        # Client can filter by type
        sofas = [c for c in result["components"] if c.get("type") == "sofa"]
        assert len(sofas) == 1
        assert sofas[0]["id"] == "sofa_001"

    @pytest.mark.asyncio
    async def test_available_types_provided(self, temp_project_dir):
        """Test that available_types lists all component types."""
        from mcp_server.resources.design_model_resource import list_components

        result = await list_components(temp_project_dir)

        assert "available_types" in result
        assert set(result["available_types"]) == {"sofa", "table", "lighting"}

    @pytest.mark.asyncio
    async def test_missing_project_returns_empty(self, empty_project_dir):
        """Test that missing project returns empty components list."""
        from mcp_server.resources.design_model_resource import list_components

        nonexistent = empty_project_dir + "_nonexistent"
        result = await list_components(nonexistent)

        assert result["components"] == []
        assert result["project_path"] == nonexistent


class TestGetSpaces:
    """Tests for get_spaces resource."""

    @pytest.mark.asyncio
    async def test_get_all_spaces(self, temp_project_dir):
        """Test getting all spaces."""
        from mcp_server.resources.design_model_resource import get_spaces

        result = await get_spaces(temp_project_dir)

        assert "living_room" in result
        assert "dining_area" in result
        assert result["living_room"]["name"] == "客厅"

    @pytest.mark.asyncio
    async def test_missing_project_raises(self, empty_project_dir):
        """Test that missing project raises FileNotFoundError."""
        from mcp_server.resources.design_model_resource import get_spaces

        nonexistent = empty_project_dir + "_nonexistent"
        with pytest.raises(FileNotFoundError):
            await get_spaces(nonexistent)


class TestGetSemanticAnchor:
    """Tests for get_semantic_anchor resource."""

    @pytest.mark.asyncio
    async def test_get_existing_anchor(self, temp_project_dir):
        """Test getting semantic anchor for existing component."""
        from mcp_server.resources.design_model_resource import get_semantic_anchor

        result = await get_semantic_anchor(temp_project_dir, "sofa_001")

        assert "center" in result
        assert result["center"] == [1000, 2000, 450]

    @pytest.mark.asyncio
    async def test_get_anchor_with_above_position(self, temp_project_dir):
        """Test getting semantic anchor with above_position."""
        from mcp_server.resources.design_model_resource import get_semantic_anchor

        result = await get_semantic_anchor(temp_project_dir, "table_001")

        assert "above_position" in result
        assert result["above_position"]["height_offset"] == 1200

    @pytest.mark.asyncio
    async def test_missing_component_raises(self, temp_project_dir):
        """Test that missing component raises KeyError."""
        from mcp_server.resources.design_model_resource import get_semantic_anchor

        with pytest.raises(KeyError, match="Component not found"):
            await get_semantic_anchor(temp_project_dir, "nonexistent_component")


class TestGetLayerEntities:
    """Tests for get_layer_entities resource."""

    @pytest.mark.asyncio
    async def test_get_layer_from_layers_dict(self, temp_project_dir):
        """Test getting entities from layers dict."""
        from mcp_server.resources.design_model_resource import get_layer_entities

        result = await get_layer_entities(temp_project_dir, "Walls")

        assert len(result) == 2
        ids = {e["id"] for e in result}
        assert ids == {"wall_001", "wall_002"}

    @pytest.mark.asyncio
    async def test_get_layer_from_entities_fallback(self, temp_project_dir):
        """Test getting entities from entities dict when layer not in layers."""
        from mcp_server.resources.design_model_resource import get_layer_entities

        # Furniture is NOT in layers dict (only Walls and Lighting are)
        # So it should fall back to searching entities
        result = await get_layer_entities(temp_project_dir, "Furniture")

        # Should find chair_001 from entities fallback
        assert len(result) == 1
        assert result[0]["id"] == "chair_001"

    @pytest.mark.asyncio
    async def test_empty_layers_entry_returns_empty(self, temp_project_dir):
        """Test that explicit empty list in layers returns empty (no fallback)."""
        from mcp_server.resources.design_model_resource import get_layer_entities

        # Lighting has explicit empty list in layers
        result = await get_layer_entities(temp_project_dir, "Lighting")

        assert result == []

    @pytest.mark.asyncio
    async def test_missing_project_returns_empty(self, empty_project_dir):
        """Test that missing project returns empty list."""
        from mcp_server.resources.design_model_resource import get_layer_entities

        nonexistent = empty_project_dir + "_nonexistent"
        result = await get_layer_entities(nonexistent, "Walls")

        assert result == []

    @pytest.mark.asyncio
    async def test_layer_not_found_returns_empty(self, temp_project_dir):
        """Test that nonexistent layer returns empty list."""
        from mcp_server.resources.design_model_resource import get_layer_entities

        result = await get_layer_entities(temp_project_dir, "NonExistentLayer")

        assert result == []


class TestLoadDesignModel:
    """Tests for _load_design_model helper function."""

    def test_invalid_json_raises(self, temp_project_dir):
        """Test that invalid JSON raises JSONDecodeError."""
        # Create a project with invalid JSON
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            model_path = project_path / "design_model.json"
            model_path.write_text("{ invalid json }")

            from mcp_server.resources.design_model_resource import _load_design_model

            with pytest.raises(json.JSONDecodeError):
                _load_design_model(str(project_path))

    def test_canonical_filename_preferred(self, temp_project_dir):
        """Test that design_model.json is preferred over legacy hidden file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            legacy_path = project_path / ".design_model.json"
            with open(legacy_path, "w", encoding="utf-8") as f:
                json.dump({"version": "1.0", "components": {}}, f)

            canonical_path = project_path / "design_model.json"
            with open(canonical_path, "w", encoding="utf-8") as f:
                json.dump({"version": "9.9", "components": {}}, f)

            from mcp_server.resources.design_model_resource import _load_design_model

            result = _load_design_model(str(project_path))
            assert result["version"] == "9.9"
