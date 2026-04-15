# frozen_string_literal: true

require_relative '../spec_helper'
require_relative '../../lib/su_bridge/design_model_sync'

RSpec.describe SuBridge::DesignModelSync do
  let(:temp_dir) { Dir.mktmpdir("scc_test") }
  let(:sync) { described_class.new(temp_dir) }

  after do
    FileUtils.rm_rf(temp_dir) if Dir.exist?(temp_dir)
  end

  describe "#initialize" do
    it "creates with custom project path" do
      sync = described_class.new(temp_dir)
      expect(sync.project_path).to eq(temp_dir)
      expect(sync.design_model_path).to eq(File.join(temp_dir, "design_model.json"))
    end
  end

  describe "#design_model_path" do
    it "returns correct path" do
      expect(sync.design_model_path).to eq(File.join(temp_dir, "design_model.json"))
    end
  end

  describe "#load" do
    context "when file does not exist" do
      it "returns nil" do
        expect(sync.load).to be_nil
      end
    end

    context "when file exists" do
      before do
        File.write(File.join(temp_dir, "design_model.json"), '{"version": "1.0", "components": {}}')
      end

      it "returns parsed JSON" do
        data = sync.load
        expect(data["version"]).to eq("1.0")
        expect(data["components"]).to eq({})
      end
    end

    context "when file has invalid JSON" do
      before do
        File.write(File.join(temp_dir, "design_model.json"), "invalid json")
      end

      it "returns nil" do
        expect(sync.load).to be_nil
      end
    end
  end

  describe "#save" do
    it "writes data to file" do
      data = { "version" => "1.0", "components" => {} }
      result = sync.save(data)
      expect(result).to be true

      loaded = JSON.parse(File.read(sync.design_model_path))
      expect(loaded["version"]).to eq("1.0")
    end

    it "updates updated_at timestamp" do
      data = { "version" => "1.0", "components" => {} }
      sync.save(data)

      loaded = sync.load
      expect(loaded["updated_at"]).to be_a(String)
    end
  end

  describe "#sync_to_file!" do
    it "returns error hash when no active model" do
      # Stub SketchUp.active_model to return nil
      allow(Sketchup).to receive(:active_model).and_return(nil)

      result = sync.sync_to_file!
      expect(result[:error]).to be_a(String)
    end
  end

  describe "#sync_from_file!" do
    it "returns error when no active model" do
      allow(Sketchup).to receive(:active_model).and_return(nil)

      result = sync.sync_from_file!
      expect(result[:error]).to be_a(String)
    end

    it "returns error when file does not exist" do
      model = double("Model")
      allow(Sketchup).to receive(:active_model).and_return(model)

      result = sync.sync_from_file!
      expect(result[:error]).to eq("design_model.json not found")
    end
  end

  describe ".AI_LAYERS" do
    it "contains expected layer names" do
      expect(described_class::AI_LAYERS).to include("Walls", "Furniture", "Lighting")
    end
  end

  describe "Hooks module" do
    after do
      described_class::Hooks.reset!
    end

    it "is enabled by default" do
      described_class::Hooks.reset!
      expect(described_class::Hooks.enabled?).to be true
    end

    it "can be disabled" do
      described_class::Hooks.enable!
      described_class::Hooks.disable!
      expect(described_class::Hooks.enabled?).to be false
    end

    it "has default debounce of 500ms" do
      described_class::Hooks.reset!
      expect(described_class::Hooks.debounce_ms).to eq(500)
    end

    it "sync_on_undo is disabled by default" do
      described_class::Hooks.reset!
      expect(described_class::Hooks.sync_on_undo?).to be false
    end

    describe "#configure" do
      it "allows setting custom debounce_ms" do
        described_class::Hooks.configure(debounce_ms: 1000)
        expect(described_class::Hooks.debounce_ms).to eq(1000)
      end

      it "allows setting sync_on_undo" do
        described_class::Hooks.configure(sync_on_undo: true)
        expect(described_class::Hooks.sync_on_undo?).to be true
      end
    end

    describe "#reset!" do
      it "resets all settings to defaults" do
        described_class::Hooks.configure(debounce_ms: 1000, sync_on_undo: true)
        described_class::Hooks.reset!
        expect(described_class::Hooks.enabled?).to be true
        expect(described_class::Hooks.debounce_ms).to eq(500)
        expect(described_class::Hooks.sync_on_undo?).to be false
      end
    end
  end

  describe "#add_entity" do
    it "returns false when entity is nil" do
      expect(sync.add_entity(nil)).to be false
    end

    it "creates design_model.json if it does not exist" do
      entity = double("Entity", entityID: 123, name: "TestEntity")
      allow(entity).to receive(:layer).and_return(double("Layer", name: "Furniture"))
      allow(entity).to receive(:transformation).and_return(nil)
      allow(entity).to receive(:bounds).and_return(double("Bounds", center: [0, 0, 0], width: 100, depth: 100, height: 50))

      result = sync.add_entity(entity)
      expect(result).to be true
      expect(File.exist?(sync.design_model_path)).to be true
    end
  end

  describe "#remove_entity" do
    before do
      # Create a design_model.json with components
      data = {
        "version" => "1.0",
        "components" => {
          "entity_123" => { "type" => "group", "name" => "Test" },
          "entity_456" => { "type" => "group", "name" => "Test2" }
        }
      }
      File.write(sync.design_model_path, JSON.generate(data))
    end

    it "returns false when design_model.json does not exist" do
      sync_no_file = described_class.new(Dir.mktmpdir("scc_empty"))
      result = sync_no_file.remove_entity(123)
      FileUtils.rm_rf(Dir.mktmpdir("scc_empty")) if Dir.exist?(Dir.mktmpdir("scc_empty"))
      expect(result).to be false
    end

    it "removes entity from components" do
      result = sync.remove_entity(123)
      expect(result).to be true

      loaded = sync.load
      expect(loaded["components"]["entity_123"]).to be_nil
      expect(loaded["components"]["entity_456"]).to be_truthy
    end

    it "returns false when entity_id not found" do
      result = sync.remove_entity(999)
      expect(result).to be false
    end
  end

  describe "#update_entity_position" do
    before do
      data = {
        "version" => "1.0",
        "components" => {
          "entity_123" => { "type" => "group", "name" => "Test", "position" => [0, 0, 0], "rotation" => 0 }
        }
      }
      File.write(sync.design_model_path, JSON.generate(data))
    end

    it "updates entity position" do
      result = sync.update_entity_position(123, [100, 200, 300])
      expect(result).to be true

      loaded = sync.load
      expect(loaded["components"]["entity_123"]["position"]).to eq([100, 200, 300])
    end

    it "updates entity position and rotation" do
      result = sync.update_entity_position(123, [100, 200, 300], 45.0)
      expect(result).to be true

      loaded = sync.load
      expect(loaded["components"]["entity_123"]["position"]).to eq([100, 200, 300])
      expect(loaded["components"]["entity_123"]["rotation"]).to eq(45.0)
    end

    it "returns false when entity not found" do
      result = sync.update_entity_position(999, [100, 200, 300])
      expect(result).to be false
    end
  end

  describe "#batch_update" do
    it "returns true when changes is empty" do
      expect(sync.batch_update([])).to be true
    end

    it "applies add operation" do
      changes = [
        { operation: :add, entity_id: 123, data: { "type" => "group", "name" => "NewGroup" } }
      ]

      result = sync.batch_update(changes)
      expect(result).to be true

      loaded = sync.load
      expect(loaded["components"]["entity_123"]["name"]).to eq("NewGroup")
    end

    it "applies remove operation" do
      # First create an entity
      data = {
        "version" => "1.0",
        "components" => {
          "entity_123" => { "type" => "group", "name" => "Test" }
        }
      }
      File.write(sync.design_model_path, JSON.generate(data))

      changes = [
        { operation: :remove, entity_id: 123 }
      ]

      result = sync.batch_update(changes)
      expect(result).to be true

      loaded = sync.load
      expect(loaded["components"]["entity_123"]).to be_nil
    end

    it "applies update operation" do
      # First create an entity
      data = {
        "version" => "1.0",
        "components" => {
          "entity_123" => { "type" => "group", "name" => "Test", "position" => [0, 0, 0] }
        }
      }
      File.write(sync.design_model_path, JSON.generate(data))

      changes = [
        { operation: :update, entity_id: 123, data: { "position" => [500, 500, 0] } }
      ]

      result = sync.batch_update(changes)
      expect(result).to be true

      loaded = sync.load
      expect(loaded["components"]["entity_123"]["position"]).to eq([500, 500, 0])
      expect(loaded["components"]["entity_123"]["name"]).to eq("Test") # Original preserved
    end

    it "handles multiple operations in batch" do
      data = {
        "version" => "1.0",
        "components" => {
          "entity_123" => { "type" => "group", "name" => "Original" }
        }
      }
      File.write(sync.design_model_path, JSON.generate(data))

      changes = [
        { operation: :add, entity_id: 456, data: { "type" => "component", "name" => "NewComp" } },
        { operation: :remove, entity_id: 123 },
        { operation: :update, entity_id: 789, data: { "position" => [100, 100, 0] } }
      ]

      result = sync.batch_update(changes)
      expect(result).to be true

      loaded = sync.load
      expect(loaded["components"]["entity_123"]).to be_nil
      expect(loaded["components"]["entity_456"]["name"]).to eq("NewComp")
    end
  end

  describe SuBridge::EntityObserver do
    let(:sync_manager) { double("sync_manager") }
    let(:observer) { described_class.new(sync_manager) }

    describe "#initialize" do
      it "initializes with sync_manager" do
        expect(observer).to be_a(described_class)
      end

      it "initializes with empty pending_changes" do
        expect(observer.instance_variable_get(:@pending_changes)).to eq([])
      end

      it "initializes with Monitor lock" do
        lock = observer.instance_variable_get(:@lock)
        expect(lock).to be_a(Monitor)
      end
    end
  end
end
