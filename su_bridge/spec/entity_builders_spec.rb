# frozen_string_literal: true

require_relative "spec_helper"
require "su_bridge"
require "su_bridge/entities/door_builder"
require "su_bridge/entities/window_builder"
require "su_bridge/entities/stairs_builder"

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
