# frozen_string_literal: true

module SuBridge
  module Entities
    # Handles group and component creation.
    class GroupBuilder
      # Get Sketchup reference dynamically to avoid constant resolution issues
      def self.sketchup
        ::Object.const_get('Sketchup')
      end

      def self.create(entity_ids, name = nil)
        entities = find_entities(entity_ids)
        raise EntityNotFoundError, "No entities found for IDs: #{entity_ids.join(', ')}" if entities.empty?

        group = sketchup.active_model.entities.add_group(entities)
        group.name = name if name

        group
      end

      def self.create_component(entity_ids, name = nil)
        entities = find_entities(entity_ids)
        raise EntityNotFoundError, "No entities found for IDs: #{entity_ids.join(', ')}" if entities.empty?

        definition = sketchup.active_model.definitions.add(name || "Component")
        group = definition.entities.add_group(entities)

        # Add instance to the model
        sketchup.active_model.active_entities.add_instance(definition, ORIGIN)
      end

      private

      def self.find_entities(entity_ids)
        all_entities = sketchup.active_model.entities.to_a
        all_entities.select { |e| entity_ids.include?(e.entityID.to_s) }
      end
    end
  end
end
