# frozen_string_literal: true

module SuBridge
  module Rules
    # Validates spatial constraints for entity placement.
    # Ensures minimum clearances are maintained between entities.
    class SpatialValidator
      MINIMUM_CLEARANCES = {
        walking_path: 800,
        chair_to_table: 600,
        sofa_to_coffee_table: 400,
        door_swing_clearance: 900,
        bed_to_nightstand: 600,
        tv_to_seating: 1500
      }.freeze

      def initialize
        @entities = []
      end

      # Add an entity to track for validation
      # @param entity [Sketchup::Entity] The entity to track
      def add_entity(entity)
        @entities << entity
      end

      # Remove an entity from tracking
      # @param entity [Sketchup::Entity] The entity to remove
      def remove_entity(entity)
        @entities.delete_if { |e| e.entityID == entity.entityID }
      end

      # Clear all tracked entities
      def clear
        @entities = []
      end

      # Validate if a new entity can be placed at a position without violating constraints
      # @param new_entity [Sketchup::Entity] The entity to validate
      # @param context [Symbol] The clearance context (:walking_path, :chair_to_table, etc.)
      # @return [Hash] { valid: Boolean, violations: Array of violation details }
      def validate_placement(new_entity, context: :default)
        min_distance = MINIMUM_CLEARANCES[context] || 800
        violations = []

        @entities.each do |existing|
          next if existing.entityID == new_entity.entityID

          distance = get_min_distance(new_entity, existing)
          if distance < min_distance && distance > 0
            violations << {
              entity_id: existing.entityID,
              entity_name: existing.name || existing.class.name,
              distance: distance.round(2),
              required: min_distance,
              context: context,
              shortfall: (min_distance - distance).round(2)
            }
          end
        end

        { valid: violations.empty?, violations: violations }
      end

      # Check if two entities are colliding (bounding boxes overlap)
      # @param entity1 [Sketchup::Entity] First entity
      # @param entity2 [Sketchup::Entity] Second entity
      # @return [Boolean] true if colliding
      def check_collision(entity1, entity2)
        bounds1 = entity1.bounds
        bounds2 = entity2.bounds

        return false if bounds1.nil? || bounds2.nil?

        # Check if bounds don't overlap in any axis
        !(bounds1.min.x > bounds2.max.x ||
          bounds1.max.x < bounds2.min.x ||
          bounds1.min.y > bounds2.max.y ||
          bounds1.max.y < bounds2.min.y ||
          bounds1.min.z > bounds2.max.z ||
          bounds1.max.z < bounds2.min.z)
      end

      # Calculate minimum distance between two entities
      # Uses center point distance as approximation
      # @param entity1 [Sketchup::Entity] First entity
      # @param entity2 [Sketchup::Entity] Second entity
      # @return [Float] Distance in millimeters
      def get_min_distance(entity1, entity2)
        bounds1 = entity1.bounds
        bounds2 = entity2.bounds

        return Float::INFINITY if bounds1.nil? || bounds2.nil?

        # Get center positions
        pos1 = entity1.transformation ? entity1.transformation.origin : bounds1.center
        pos2 = entity2.transformation ? entity2.transformation.origin : bounds2.center

        delta_x = (pos1.x - pos2.x).abs
        delta_y = (pos1.y - pos2.y).abs
        delta_z = (pos1.z - pos2.z).abs

        # Return Euclidean distance (SketchUp works in inches internally, but we normalize)
        Math.sqrt(delta_x**2 + delta_y**2 + delta_z**2)
      end

      # Get clearance requirement for a specific context
      # @param context [Symbol] The clearance context
      # @return [Integer] Required clearance in mm
      def self.get_clearance(context)
        MINIMUM_CLEARANCES[context] || 800
      end

      # List all available clearance contexts
      # @return [Array<Symbol>] Available context names
      def self.available_clearances
        MINIMUM_CLEARANCES.keys
      end

      # Validate multiple entities for mutual collision
      # @param entities [Array<Sketchup::Entity>] Entities to check
      # @return [Array<Hash>] List of collision pairs
      def self.find_collisions(entities)
        collisions = []
        entities.each_with_index do |entity1, i|
          entities[(i + 1)..].each do |entity2|
            next unless entity1.bounds && entity2.bounds

            bounds1 = entity1.bounds
            bounds2 = entity2.bounds

            if !(bounds1.min.x > bounds2.max.x ||
                 bounds1.max.x < bounds2.min.x ||
                 bounds1.min.y > bounds2.max.y ||
                 bounds1.max.y < bounds2.min.y ||
                 bounds1.min.z > bounds2.max.z ||
                 bounds1.max.z < bounds2.min.z)
              collisions << {
                entity1_id: entity1.entityID,
                entity1_name: entity1.name || entity1.class.name,
                entity2_id: entity2.entityID,
                entity2_name: entity2.name || entity2.class.name
              }
            end
          end
        end
        collisions
      end
    end
  end
end
