# frozen_string_literal: true

require_relative "spec_helper"
require "su_bridge"
require "su_bridge/command_dispatcher"
require "su_bridge/entities/face_builder"
require "su_bridge/entities/wall_builder"
require "su_bridge/entities/material_applier"

RSpec.describe SuBridge::CommandDispatcher do
  let(:dispatcher) { described_class.new }

  describe "OPERATION_HANDLERS" do
    it "includes all required operations" do
      required_operations = %w[
        create_face
        create_box
        create_wall
        create_group
        create_door
        create_window
        create_stairs
        delete_entity
        set_material
        apply_material
        apply_style
        query_entities
        query_model_info
        get_scene_info
        place_component
        place_lighting
        set_camera_view
        capture_design
        cleanup_model
        move_entity
        rotate_entity
        scale_entity
        copy_entity
        export_gltf
        export_ifc
      ]

      required_operations.each do |op|
        expect(SuBridge::CommandDispatcher::OPERATION_HANDLERS).to have_key(op),
          "Missing handler for #{op}"
      end
    end
  end

  describe "#dispatch" do
    context "with execute_operation method" do
      it "dispatches create_face operation" do
        request = {
          "method" => "execute_operation",
          "params" => {
            "operation_id" => "test_001",
            "operation_type" => "create_face",
            "payload" => {
              "vertices" => [[0, 0, 0], [1000, 0, 0], [1000, 500, 0], [0, 500, 0]]
            },
            "rollback_on_failure" => true
          },
          "id" => 1
        }

        # This will fail without SketchUp, but validates the dispatch structure
        expect {
          dispatcher.dispatch(request)
        }.not_to raise_error
      end

      it "returns error for unknown operation_type" do
        request = {
          "method" => "execute_operation",
          "params" => {
            "operation_id" => "test_002",
            "operation_type" => "nonexistent_operation",
            "payload" => {},
            "rollback_on_failure" => true
          },
          "id" => 2
        }

        response = dispatcher.dispatch(request)
        expect(response["error"]).not_to be_nil
        expect(response["error"]["code"]).to eq(-32000)
      end

      it "returns error for unknown method" do
        request = {
          "method" => "unknown_method",
          "params" => {},
          "id" => 3
        }

        response = dispatcher.dispatch(request)
        expect(response["error"]).not_to be_nil
        expect(response["error"]["code"]).to eq(-32000)
      end
    end
  end

  describe "error_code_for" do
    it "returns -32001 for ValidationError" do
      error = SuBridge::UndoManager::ValidationError.new("test")
      code = dispatcher.send(:error_code_for, error)
      expect(code).to eq(-32001)
    end

    it "returns -32004 for EntityNotFoundError" do
      error = SuBridge::UndoManager::EntityNotFoundError.new("test")
      code = dispatcher.send(:error_code_for, error)
      expect(code).to eq(-32004)
    end

    it "returns -32005 for PermissionError" do
      error = SuBridge::UndoManager::PermissionError.new("test")
      code = dispatcher.send(:error_code_for, error)
      expect(code).to eq(-32005)
    end

    it "returns -32002 for RollbackError" do
      error = SuBridge::UndoManager::RollbackError.new("test")
      code = dispatcher.send(:error_code_for, error)
      expect(code).to eq(-32002)
    end

    it "returns -32000 for unknown errors" do
      error = StandardError.new("test")
      code = dispatcher.send(:error_code_for, error)
      expect(code).to eq(-32000)
    end
  end

  describe "export handlers" do
    it "has handle_export_gltf method" do
      expect(dispatcher.private_methods).to include(:handle_export_gltf)
    end

    it "has handle_export_ifc method" do
      expect(dispatcher.private_methods).to include(:handle_export_ifc)
    end

    it "dispatcher responds to export_gltf operation" do
      expect {
        dispatcher.dispatch({
          "method" => "execute_operation",
          "params" => {
            "operation_id" => "export_test",
            "operation_type" => "export_gltf",
            "payload" => { "output_path" => "/tmp/test.gltf" },
            "rollback_on_failure" => false
          },
          "id" => 1
        })
      }.not_to raise_error
    end

    it "dispatcher responds to export_ifc operation" do
      expect {
        dispatcher.dispatch({
          "method" => "execute_operation",
          "params" => {
            "operation_id" => "export_test",
            "operation_type" => "export_ifc",
            "payload" => { "output_path" => "/tmp/test.ifc" },
            "rollback_on_failure" => false
          },
          "id" => 1
        })
      }.not_to raise_error
    end
  end
end

RSpec.describe SuBridge::Entities::MaterialApplier do
  describe "STYLE_PRESETS" do
    it "includes all 6 style presets" do
      required_styles = %w[
        japandi_cream
        modern_industrial
        scandinavian
        mediterranean
        bohemian
        contemporary_minimalist
      ]

      required_styles.each do |style|
        expect(described_class::STYLE_PRESETS).to have_key(style),
          "Missing style preset: #{style}"
      end
    end

    it "each style has materials array" do
      described_class::STYLE_PRESETS.each do |name, style|
        expect(style["materials"]).to be_an(Array),
          "Style #{name} should have materials array"
        expect(style["materials"]).not_to be_empty,
          "Style #{name} should have at least one material"
      end
    end

    it "each material has id and color" do
      described_class::STYLE_PRESETS.each do |name, style|
        style["materials"].each do |mat|
          expect(mat["id"]).to be_a(String),
            "Material in #{name} should have id"
          expect(mat["color"]).to be_a(String),
            "Material in #{name} should have color"
          expect(mat["color"]).to match(/^#/),  # Should be hex color
            "Material color in #{name} should be hex format"
        end
      end
    end
  end
end

RSpec.describe SuBridge::Entities::FaceBuilder do
  describe ".mm_to_inch" do
    it "converts millimeters to inches correctly" do
      expect(described_class.mm_to_inch(25.4)).to be_within(0.001).of(1.0)
      expect(described_class.mm_to_inch(1000)).to be_within(0.1).of(39.37)
    end
  end

  describe ".apply_material" do
    it "is a defined method" do
      expect(described_class).to respond_to(:apply_material)
    end
  end
end

RSpec.describe SuBridge::Entities::WallBuilder do
  describe ".mm_to_inch" do
    it "converts millimeters to inches correctly" do
      expect(described_class.mm_to_inch(25.4)).to be_within(0.001).of(1.0)
    end
  end

  describe ".apply_material" do
    it "is a defined method" do
      expect(described_class).to respond_to(:apply_material)
    end
  end

  describe "ALIGNMENT_MODES" do
    it "includes center, inner, outer" do
      expect(described_class::ALIGNMENT_MODES).to contain_exactly("center", "inner", "outer")
    end
  end
end
