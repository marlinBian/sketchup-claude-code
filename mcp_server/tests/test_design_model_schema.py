"""Tests for Design Model Schema and Validation."""

import json
import tempfile
from pathlib import Path

import pytest

from mcp_server.resources.design_model_schema import (
    DESIGN_MODEL_SCHEMA,
    create_empty_template,
    load_design_model,
    save_design_model,
    validate_design_model,
)


class TestValidateDesignModel:
    """Tests for validate_design_model function."""

    def test_valid_minimal_design_model(self):
        """Test validation of minimal valid design model."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {},
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is True
        assert errors == []

    def test_valid_full_design_model(self):
        """Test validation of complete valid design model."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T12:00:00Z",
            "metadata": {
                "style": "scandinavian",
                "ceiling_height": 2400,
                "units": "mm",
            },
            "spaces": {
                "living_room_001": {
                    "type": "living_room",
                    "bounds": {
                        "min": [0, 0, 0],
                        "max": [5000, 4000, 2400],
                    },
                    "center": [2500, 2000, 1200],
                },
            },
            "components": {
                "sofa_001": {
                    "type": "sofa",
                    "name": "Modern L-Shaped Sofa",
                    "position": [1500, 2000, 0],
                    "dimensions": {
                        "width": 2500,
                        "depth": 1800,
                        "height": 800,
                    },
                    "rotation": 0,
                    "layer": "Furniture",
                    "relative_to": None,
                    "created_at": "2024-01-15T10:30:00Z",
                },
            },
            "lighting": {
                "chandelier_001": {
                    "type": "chandelier",
                    "position": [2500, 2000, 2400],
                    "relative_to": {
                        "anchor": "dining_table_center",
                        "relationship": "above",
                        "height_offset": 600,
                    },
                },
            },
            "semantic_anchors": {
                "dining_table_001": {
                    "center": [2500, 2000, 0],
                    "surface_center": [2500, 2000, 750],
                },
            },
            "layers": {
                "Walls": {"color": "#CCCCCC"},
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is True
        assert errors == []

    def test_valid_bathroom_contract_fixture(self):
        """Test validation of the first bathroom vertical-slice fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "bathroom" / "design_model.json"

        loaded, errors = load_design_model(str(fixture_path))

        assert errors == []
        assert loaded is not None
        assert loaded["spaces"]["bathroom_001"]["type"] == "bathroom"
        assert loaded["components"]["toilet_001"]["component_ref"] == (
            "toilet_floor_mounted_basic"
        )

    def test_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        data = {
            "version": "1.0",
            # Missing project_name and components
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        assert len(errors) >= 2
        # jsonschema reports required field errors at root level
        error_messages = " ".join(errors)
        assert "project_name" in error_messages
        assert "components" in error_messages

    def test_missing_version_field(self):
        """Test validation fails when version is missing."""
        data = {
            "project_name": "test_project",
            "components": {},
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        error_messages = " ".join(errors)
        assert "version" in error_messages

    def test_invalid_component_data(self):
        """Test validation fails for invalid component data."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {
                "sofa_001": {
                    # Missing required 'type', 'name', 'position'
                    "dimensions": {
                        "width": 2500,
                    },
                },
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        # Should have errors about missing required fields
        component_errors = [e for e in errors if "sofa_001" in e]
        assert len(component_errors) > 0

    def test_invalid_position_format(self):
        """Test validation fails when position is not an array of 3 numbers."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {
                "sofa_001": {
                    "type": "sofa",
                    "name": "Sofa",
                    "position": [100, 200],  # Missing third element
                },
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        position_errors = [e for e in errors if "position" in e]
        assert len(position_errors) > 0

    def test_invalid_space_type(self):
        """Test validation fails for invalid space type."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {},
            "spaces": {
                "room_001": {
                    "type": "invalid_room_type",  # Invalid type
                    "bounds": {
                        "min": [0, 0, 0],
                        "max": [1000, 1000, 2400],
                    },
                },
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        type_errors = [e for e in errors if "invalid_room_type" in e]
        assert len(type_errors) > 0

    def test_invalid_layer_name(self):
        """Test validation fails for invalid layer name."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {
                "chair_001": {
                    "type": "chair",
                    "name": "Chair",
                    "position": [0, 0, 0],
                    "layer": "InvalidLayer",  # Not in enum
                },
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        layer_errors = [e for e in errors if "InvalidLayer" in e]
        assert len(layer_errors) > 0

    def test_invalid_lighting_type(self):
        """Test validation fails for invalid lighting type."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {},
            "lighting": {
                "light_001": {
                    "type": "invalid_light_type",
                    "position": [0, 0, 2400],
                },
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        light_errors = [e for e in errors if "invalid_light_type" in e]
        assert len(light_errors) > 0

    def test_semantic_anchors_format(self):
        """Test validation of semantic_anchors format."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {},
            "semantic_anchors": {
                "dining_table_001": {
                    "center": [2500, 2000, 0],
                    "surface_center": [2500, 2000, 750],
                },
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is True
        assert errors == []

    def test_invalid_semantic_anchor_coordinates(self):
        """Test validation fails when semantic anchor has wrong coordinate count."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {},
            "semantic_anchors": {
                "table_001": {
                    "center": [2500, 2000],  # Missing third element
                },
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        anchor_errors = [e for e in errors if "table_001" in e or "center" in e]
        assert len(anchor_errors) > 0

    def test_layer_color_format(self):
        """Test validation of layer color hex format."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {},
            "layers": {
                "Walls": {"color": "#AABBCC"},
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is True

    def test_invalid_layer_color_format(self):
        """Test validation fails for invalid color format."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {},
            "layers": {
                "Walls": {"color": "red"},  # Not a hex color
            },
        }
        is_valid, errors = validate_design_model(data)
        assert is_valid is False
        color_errors = [e for e in errors if "red" in e]
        assert len(color_errors) > 0

    def test_none_data(self):
        """Test validation fails for None input."""
        is_valid, errors = validate_design_model(None)
        assert is_valid is False
        assert "Design model must be a dictionary" in errors

    def test_non_dict_data(self):
        """Test validation fails for non-dictionary input."""
        is_valid, errors = validate_design_model("not a dict")
        assert is_valid is False
        assert "Design model must be a dictionary" in errors


class TestCreateEmptyTemplate:
    """Tests for create_empty_template function."""

    def test_default_project_name(self):
        """Test template with default project name."""
        template = create_empty_template()
        assert template["project_name"] == "untitled"

    def test_custom_project_name(self):
        """Test template with custom project name."""
        template = create_empty_template("my_kitchen")
        assert template["project_name"] == "my_kitchen"

    def test_template_has_required_fields(self):
        """Test template contains all required fields."""
        template = create_empty_template()
        assert "version" in template
        assert "project_name" in template
        assert "created_at" in template
        assert "updated_at" in template
        assert "metadata" in template
        assert "spaces" in template
        assert "components" in template
        assert "lighting" in template
        assert "semantic_anchors" in template
        assert "layers" in template

    def test_template_metadata_defaults(self):
        """Test template has correct metadata defaults."""
        template = create_empty_template()
        assert template["metadata"]["style"] == ""
        assert template["metadata"]["ceiling_height"] == 2400
        assert template["metadata"]["units"] == "mm"

    def test_template_empty_collections(self):
        """Test template has empty collections for dynamic content."""
        template = create_empty_template()
        assert template["spaces"] == {}
        assert template["components"] == {}
        assert template["lighting"] == {}
        assert template["semantic_anchors"] == {}
        assert template["layers"] == {}


class TestLoadDesignModel:
    """Tests for load_design_model function."""

    def test_load_valid_design_model(self):
        """Test loading a valid design model file."""
        data = {
            "version": "1.0",
            "project_name": "test_project",
            "components": {},
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            loaded, errors = load_design_model(temp_path)
            assert loaded is not None
            assert errors == []
            assert loaded["project_name"] == "test_project"
        finally:
            Path(temp_path).unlink()

    def test_load_nonexistent_file(self):
        """Test loading a non-existent file."""
        loaded, errors = load_design_model("/nonexistent/path/design_model.json")
        assert loaded is None
        assert len(errors) == 1
        assert "not found" in errors[0].lower()

    def test_load_invalid_json(self):
        """Test loading a file with invalid JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            loaded, errors = load_design_model(temp_path)
            assert loaded is None
            assert len(errors) == 1
            assert "invalid json" in errors[0].lower()
        finally:
            Path(temp_path).unlink()

    def test_load_invalid_schema(self):
        """Test loading a file with valid JSON but invalid schema."""
        data = {
            "version": "1.0",
            # Missing required project_name and components
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            loaded, errors = load_design_model(temp_path)
            assert loaded is None
            assert len(errors) > 0
        finally:
            Path(temp_path).unlink()


class TestSaveDesignModel:
    """Tests for save_design_model function."""

    def test_save_valid_design_model(self):
        """Test saving a valid design model."""
        data = create_empty_template("save_test")
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "design_model.json"

        success, errors = save_design_model(str(temp_path), data)
        assert success is True
        assert errors == []
        assert temp_path.exists()

        # Verify saved content
        with open(temp_path) as f:
            loaded = json.load(f)
        assert loaded["project_name"] == "save_test"

        # Cleanup
        temp_path.unlink()
        Path(temp_dir).rmdir()

    def test_save_invalid_design_model(self):
        """Test saving an invalid design model fails."""
        data = {
            "version": "1.0",
            # Missing required project_name and components
        }
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "design_model.json"

        success, errors = save_design_model(str(temp_path), data)
        assert success is False
        assert len(errors) > 0
        assert not temp_path.exists()

        # Cleanup
        Path(temp_dir).rmdir()

    def test_save_updates_timestamp(self):
        """Test that save_design_model updates the updated_at field."""
        data = create_empty_template("timestamp_test")
        original_updated_at = data["updated_at"]

        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "design_model.json"

        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.01)

        success, errors = save_design_model(str(temp_path), data)
        assert success is True

        with open(temp_path) as f:
            loaded = json.load(f)

        assert loaded["updated_at"] != original_updated_at

        # Cleanup
        temp_path.unlink()
        Path(temp_dir).rmdir()

    def test_save_creates_parent_directories(self):
        """Test that save_design_model creates parent directories if needed."""
        data = create_empty_template("nested_test")
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "deeply" / "nested" / "design_model.json"

        success, errors = save_design_model(str(temp_path), data)
        assert success is True
        assert temp_path.exists()
        assert temp_path.parent.exists()

        # Cleanup
        temp_path.unlink()
        temp_path.parent.rmdir()
        temp_path.parent.parent.rmdir()
        Path(temp_dir).rmdir()
