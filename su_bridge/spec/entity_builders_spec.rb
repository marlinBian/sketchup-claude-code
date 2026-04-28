# frozen_string_literal: true

require_relative "spec_helper"
require "su_bridge"
require "su_bridge/entities/door_builder"
require "su_bridge/entities/window_builder"
require "su_bridge/entities/stairs_builder"
require "su_bridge/entities/component_manager"
require "su_bridge/entities/face_builder"

RSpec.describe SuBridge::Entities::DoorBuilder do
  describe "module structure" do
    it "is a module" do
      expect(described_class).to be_a(Module)
    end

    it "has sketchup method" do
      expect(described_class).to respond_to(:sketchup)
    end

    it "has mm_to_inch method" do
      expect(described_class).to respond_to(:mm_to_inch)
    end

    it "has create method" do
      expect(described_class).to respond_to(:create)
    end

    it "has spatial_delta method" do
      expect(described_class).to respond_to(:spatial_delta)
    end
  end

  describe ".mm_to_inch" do
    it "converts millimeters to inches correctly" do
      expect(described_class.mm_to_inch(25.4)).to be_within(0.001).of(1.0)
      expect(described_class.mm_to_inch(900)).to be_within(0.1).of(35.43)
      expect(described_class.mm_to_inch(2100)).to be_within(0.1).of(82.68)
    end
  end

  describe ".create parameters" do
    it "accepts wall_id, position coordinates, width, height, swing_direction" do
      # Just verify the method signature exists with correct parameters
      expect(described_class.method(:create).parameters.flatten).to include(:wall_id, :position_x, :position_y, :width, :height, :swing_direction)
    end
  end
end

RSpec.describe SuBridge::Entities::WindowBuilder do
  describe "module structure" do
    it "is a module" do
      expect(described_class).to be_a(Module)
    end

    it "has sketchup method" do
      expect(described_class).to respond_to(:sketchup)
    end

    it "has mm_to_inch method" do
      expect(described_class).to respond_to(:mm_to_inch)
    end

    it "has create method" do
      expect(described_class).to respond_to(:create)
    end

    it "has spatial_delta method" do
      expect(described_class).to respond_to(:spatial_delta)
    end
  end

  describe ".mm_to_inch" do
    it "converts millimeters to inches correctly" do
      expect(described_class.mm_to_inch(25.4)).to be_within(0.001).of(1.0)
      expect(described_class.mm_to_inch(1200)).to be_within(0.1).of(47.24)
      expect(described_class.mm_to_inch(1000)).to be_within(0.1).of(39.37)
    end
  end

  describe ".create parameters" do
    it "accepts wall_id, position coordinates, width, height, sill_height" do
      expect(described_class.method(:create).parameters.flatten).to include(:wall_id, :position_x, :position_y, :width, :height, :sill_height)
    end
  end
end

RSpec.describe SuBridge::Entities::StairsBuilder do
  describe "module structure" do
    it "is a module" do
      expect(described_class).to be_a(Module)
    end

    it "has sketchup method" do
      expect(described_class).to respond_to(:sketchup)
    end

    it "has mm_to_inch method" do
      expect(described_class).to respond_to(:mm_to_inch)
    end

    it "has create method" do
      expect(described_class).to respond_to(:create)
    end

    it "has spatial_delta method" do
      expect(described_class).to respond_to(:spatial_delta)
    end
  end

  describe ".mm_to_inch" do
    it "converts millimeters to inches correctly" do
      expect(described_class.mm_to_inch(25.4)).to be_within(0.001).of(1.0)
      expect(described_class.mm_to_inch(1000)).to be_within(0.1).of(39.37)
    end
  end

  describe ".create parameters" do
    it "accepts start/end coordinates, width, num_steps" do
      params = described_class.method(:create).parameters.flatten
      expect(params).to include(:start_x)
      expect(params).to include(:start_y)
      expect(params).to include(:start_z)
      expect(params).to include(:end_x)
      expect(params).to include(:end_y)
      expect(params).to include(:end_z)
      expect(params).to include(:width)
      expect(params).to include(:num_steps)
    end
  end
end

RSpec.describe SuBridge::Entities::ComponentManager do
  let(:fake_group) do
    Class.new do
      attr_accessor :name

      def entityID
        42
      end
    end.new
  end

  before do
    described_class.clear_cache
    allow(described_class).to receive(:get_instance_bounds).and_return(
      min: [0, 0, 0],
      max: [10, 10, 10]
    )
    allow(described_class).to receive(:spatial_delta).and_return(
      bounding_box: {
        min: [0, 0, 0],
        max: [600, 460, 850],
      },
      volume_mm3: 234_600_000
    )
  end

  describe ".place" do
    it "uses procedural fallback when the SKP asset is missing" do
      allow(SuBridge::Entities::FaceBuilder).to receive(:create_box).and_return(fake_group)

      result = described_class.place(
        skp_path: "/missing/vanity.skp",
        position: [1700, 0, 0],
        component_id: "vanity_wall_600",
        instance_id: "vanity_001",
        procedural_fallback: "box_fixture",
        dimensions: { "width" => 600, "depth" => 460, "height" => 850 },
        layer: "Fixtures",
        name: "Wall vanity 600 mm"
      )

      expect(result[:entity_id]).to eq("42")
      expect(result[:fallback_used]).to eq(true)
      expect(result[:definition_name]).to eq("Procedural box_fixture")
      expect(SuBridge::Entities::FaceBuilder).to have_received(:create_box).with(
        [1400.0, 0, 0],
        600,
        460,
        850,
        { "layer" => "Fixtures" }
      )
    end

    it "requires dimensions for procedural fallback" do
      expect {
        described_class.place(
          skp_path: "/missing/fixture.skp",
          position: [0, 0, 0],
          procedural_fallback: "box_fixture"
        )
      }.to raise_error(SuBridge::UndoManager::ValidationError, /dimensions required/)
    end
  end
end
