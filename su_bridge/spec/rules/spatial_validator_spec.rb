# frozen_string_literal: true

require_relative '../spec_helper'
require_relative '../../lib/su_bridge/rules/spatial_validator'

RSpec.describe SuBridge::Rules::SpatialValidator do
  let(:validator) { described_class.new }

  # Helper to create a mock entity with bounds
  def create_mock_entity(x:, y:, z:, width: 100, depth: 100, height: 100, name: 'MockEntity', entity_id: rand(1000))
    entity = double('Entity')
    bounds = double('Bounds')
    center = double('Center')

    # Create min and max points for bounds
    min_point = double('MinPoint')
    max_point = double('MaxPoint')

    allow(entity).to receive(:bounds) { bounds }
    allow(entity).to receive(:name) { name }
    allow(entity).to receive(:entityID) { entity_id }
    allow(entity).to receive(:transformation) { nil }

    allow(bounds).to receive(:min) { min_point }
    allow(bounds).to receive(:max) { max_point }
    allow(bounds).to receive(:center) { center }

    # Bounds are defined by min/max corners
    # For simplicity, center at (x, y, z) with given dimensions
    half_w = width / 2.0
    half_d = depth / 2.0
    half_h = height / 2.0

    allow(min_point).to receive(:x) { x - half_w }
    allow(min_point).to receive(:y) { y - half_d }
    allow(min_point).to receive(:z) { z }
    allow(max_point).to receive(:x) { x + half_w }
    allow(max_point).to receive(:y) { y + half_d }
    allow(max_point).to receive(:z) { z + height }
    allow(center).to receive(:x) { x }
    allow(center).to receive(:y) { y }
    allow(center).to receive(:z) { z }

    entity
  end

  describe '#initialize' do
    it 'creates an empty validator' do
      expect(validator).to be_a(described_class)
    end
  end

  describe '#add_entity and #remove_entity' do
    it 'adds and removes entities' do
      entity = create_mock_entity(x: 0, y: 0, z: 0)
      validator.add_entity(entity)
      # Can't easily test internal state, but coverage should catch issues
      validator.remove_entity(entity)
      expect { validator.remove_entity(entity) }.not_to raise_error
    end

    it 'clears all entities' do
      3.times { |i| validator.add_entity(create_mock_entity(x: i * 100, y: 0, z: 0)) }
      validator.clear
      # Validation should return no violations when no entities tracked
      new_entity = create_mock_entity(x: 1000, y: 0, z: 0)
      result = validator.validate_placement(new_entity)
      expect(result[:valid]).to be true
    end
  end

  describe '#validate_placement' do
    context 'with no existing entities' do
      it 'returns valid for any entity' do
        entity = create_mock_entity(x: 1000, y: 1000, z: 0)
        result = validator.validate_placement(entity)
        expect(result[:valid]).to be true
        expect(result[:violations]).to be_empty
      end
    end

    context 'with entities at safe distance' do
      before do
        # Add existing entity at origin, 2000mm away
        @existing = create_mock_entity(x: 0, y: 0, z: 0, entity_id: 1)
        validator.add_entity(@existing)
      end

      it 'returns valid when entity is far enough' do
        # New entity at 3000mm distance (greater than 800mm walking_path)
        new_entity = create_mock_entity(x: 3000, y: 0, z: 0, entity_id: 2)
        result = validator.validate_placement(new_entity, context: :walking_path)
        expect(result[:valid]).to be true
      end
    end

    context 'with entities too close' do
      before do
        @existing = create_mock_entity(x: 0, y: 0, z: 0, entity_id: 1)
        validator.add_entity(@existing)
      end

      it 'returns violations when too close' do
        # New entity at 500mm (less than 800mm walking_path)
        new_entity = create_mock_entity(x: 500, y: 0, z: 0, entity_id: 2)
        result = validator.validate_placement(new_entity, context: :walking_path)
        expect(result[:valid]).to be false
        expect(result[:violations].size).to eq(1)
        expect(result[:violations][0][:distance]).to eq(500)
        expect(result[:violations][0][:required]).to eq(800)
      end

      it 'respects different clearance contexts' do
        # 500mm apart - too close for walking_path (800mm) but ok for sofa_to_coffee_table (400mm)
        new_entity = create_mock_entity(x: 500, y: 0, z: 0, entity_id: 2)
        result = validator.validate_placement(new_entity, context: :sofa_to_coffee_table)
        expect(result[:valid]).to be true
      end
    end
  end

  describe '#check_collision' do
    it 'detects overlapping bounding boxes' do
      entity1 = create_mock_entity(x: 0, y: 0, z: 0, width: 500, depth: 500, height: 500, entity_id: 1)
      entity2 = create_mock_entity(x: 300, y: 300, z: 0, width: 500, depth: 500, height: 500, entity_id: 2)
      expect(validator.check_collision(entity1, entity2)).to be true
    end

    it 'detects non-overlapping bounding boxes' do
      entity1 = create_mock_entity(x: 0, y: 0, z: 0, width: 100, depth: 100, height: 100, entity_id: 1)
      entity2 = create_mock_entity(x: 500, y: 500, z: 0, width: 100, depth: 100, height: 100, entity_id: 2)
      expect(validator.check_collision(entity1, entity2)).to be false
    end
  end

  describe '#get_min_distance' do
    it 'calculates Euclidean distance between entities' do
      entity1 = create_mock_entity(x: 0, y: 0, z: 0, entity_id: 1)
      entity2 = create_mock_entity(x: 3000, y: 4000, z: 0, entity_id: 2)
      distance = validator.get_min_distance(entity1, entity2)
      # 3-4-5 triangle = 5000mm
      expect(distance).to be_within(1).of(5000)
    end

    it 'returns infinity for nil bounds' do
      entity1 = double('Entity')
      allow(entity1).to receive(:bounds) { nil }
      entity2 = create_mock_entity(x: 0, y: 0, z: 0, entity_id: 2)
      distance = validator.get_min_distance(entity1, entity2)
      expect(distance).to eq(Float::INFINITY)
    end
  end

  describe '.get_clearance' do
    it 'returns clearance for valid context' do
      expect(described_class.get_clearance(:walking_path)).to eq(800)
      expect(described_class.get_clearance(:chair_to_table)).to eq(600)
    end

    it 'returns default for unknown context' do
      expect(described_class.get_clearance(:unknown)).to eq(800)
    end
  end

  describe '.available_clearances' do
    it 'returns all available clearance contexts' do
      clearances = described_class.available_clearances
      expect(clearances).to include(:walking_path, :chair_to_table, :sofa_to_coffee_table)
      expect(clearances.size).to eq(6)
    end
  end

  describe '.find_collisions' do
    it 'finds all colliding pairs in a list of entities' do
      entity1 = create_mock_entity(x: 0, y: 0, z: 0, width: 500, depth: 500, height: 500, entity_id: 1)
      entity2 = create_mock_entity(x: 300, y: 300, z: 0, width: 500, depth: 500, height: 500, entity_id: 2)
      entity3 = create_mock_entity(x: 2000, y: 0, z: 0, width: 100, depth: 100, height: 100, entity_id: 3)

      collisions = described_class.find_collisions([entity1, entity2, entity3])
      expect(collisions.size).to eq(1)
      expect(collisions[0][:entity1_id]).to eq(1)
      expect(collisions[0][:entity2_id]).to eq(2)
    end

    it 'returns empty array when no collisions' do
      entity1 = create_mock_entity(x: 0, y: 0, z: 0, width: 100, depth: 100, height: 100, entity_id: 1)
      entity2 = create_mock_entity(x: 1000, y: 0, z: 0, width: 100, depth: 100, height: 100, entity_id: 2)
      collisions = described_class.find_collisions([entity1, entity2])
      expect(collisions).to be_empty
    end
  end
end
