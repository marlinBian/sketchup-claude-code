# frozen_string_literal: true

require_relative "spec_helper"
require "su_bridge/entity_manager"
require "su_bridge/undo_manager"

RSpec.describe SuBridge::EntityManager do
  class EntityManagerSpecLayer
    attr_reader :name

    def initialize(name)
      @name = name
    end
  end

  class EntityManagerSpecLayers
    def initialize(layers)
      @layers = layers
    end

    def [](name)
      @layers.find { |layer| layer.name == name }
    end

    def remove(_layer); end
  end

  class EntityManagerSpecEntity
    attr_reader :entityID, :layer, :definition

    def initialize(entity_id:, layer:, definition_name: nil, valid: true)
      @entityID = entity_id
      @layer = layer
      @definition = definition_name ? Struct.new(:name).new(definition_name) : nil
      @valid = valid
      @erased = false
    end

    def valid?
      @valid && !@erased
    end

    def erased?
      @erased
    end

    def erase!
      @erased = true
    end
  end

  class EntityManagerSpecModel
    attr_reader :entities, :layers

    def initialize(entities, layers)
      @entities = entities
      @layers = EntityManagerSpecLayers.new(layers)
    end

    def start_operation(_name, _disable_ui = true); end
    def commit_operation; end
    def abort_operation; end
  end

  let(:walls_layer) { EntityManagerSpecLayer.new("Walls") }
  let(:doors_layer) { EntityManagerSpecLayer.new("Doors") }
  let(:furniture_layer) { EntityManagerSpecLayer.new("Furniture") }

  def use_fake_model(entities, layers = [walls_layer, doors_layer, furniture_layer])
    model = EntityManagerSpecModel.new(entities, layers)
    allow(Sketchup).to receive(:active_model).and_return(model)
    model
  end

  describe ".delete" do
    it "erases matching entities with SketchUp erase!" do
      wall = EntityManagerSpecEntity.new(entity_id: 101, layer: walls_layer)
      door = EntityManagerSpecEntity.new(entity_id: 102, layer: doors_layer)
      use_fake_model([wall, door])

      deleted = described_class.delete(["101"])

      expect(deleted).to eq(["101"])
      expect(wall).to be_erased
      expect(door).not_to be_erased
    end

    it "skips entities that are already invalid" do
      wall = EntityManagerSpecEntity.new(entity_id: 101, layer: walls_layer, valid: false)
      use_fake_model([wall])

      deleted = described_class.delete(["101"])

      expect(deleted).to eq([])
      expect(wall).not_to be_erased
    end
  end

  describe ".delete_all" do
    it "erases entities on requested layers and leaves other layers intact" do
      wall = EntityManagerSpecEntity.new(entity_id: 101, layer: walls_layer)
      door = EntityManagerSpecEntity.new(entity_id: 102, layer: doors_layer)
      furniture = EntityManagerSpecEntity.new(entity_id: 103, layer: furniture_layer)
      use_fake_model([wall, door, furniture])

      result = described_class.delete_all(layer_names: ["Walls", "Doors"])

      expect(result[:deleted_count]).to eq(2)
      expect(result[:deleted_ids]).to eq(["101", "102"])
      expect(wall).to be_erased
      expect(door).to be_erased
      expect(furniture).not_to be_erased
    end
  end

  describe ".cleanup_by_tag" do
    it "erases entities whose definition name contains the tag" do
      imported = EntityManagerSpecEntity.new(
        entity_id: 201,
        layer: furniture_layer,
        definition_name: "sample_floorplan_001_source_overlay"
      )
      regular = EntityManagerSpecEntity.new(
        entity_id: 202,
        layer: furniture_layer,
        definition_name: "regular_component"
      )
      use_fake_model([imported, regular])

      result = described_class.cleanup_by_tag("sample_floorplan_001")

      expect(result[:deleted_count]).to eq(1)
      expect(result[:deleted_ids]).to eq(["201"])
      expect(imported).to be_erased
      expect(regular).not_to be_erased
    end
  end
end
