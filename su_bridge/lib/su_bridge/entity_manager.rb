# frozen_string_literal: true

module SuBridge
  # Manages entity deletion and lookup.
  class EntityManager
    # Get Sketchup reference dynamically to avoid constant resolution issues
    def self.sketchup
      ::Object.const_get('Sketchup')
    end

    # AI-generated content layer names
    AI_LAYERS = [
      "Walls",
      "Doors",
      "Windows",
      "Furniture",
      "Fixtures",
      "Lighting",
      "Materials",
    ].freeze

    def self.delete(entity_ids)
      deleted = []
      all_entities = sketchup.active_model.entities.to_a

      entity_ids.each do |id|
        entity = all_entities.find { |e| e.entityID.to_s == id }
        if erase_entity(entity)
          deleted << id
        end
      end

      deleted
    end

    def self.delete_all(layer_names: nil, all_entities: false)
      """Delete all entities in specified layers or all AI layers.

      Args:
        layer_names: Specific layer names to clean. If nil, uses AI_LAYERS.
        all_entities: If true, delete every valid entity in the active model.

      Returns:
        Hash with deleted count and entity_ids
      """
      layers_to_clean = layer_names || AI_LAYERS
      deleted_count = 0
      deleted_ids = []

      UndoManager.with_transaction(name: "Cleanup Model", rollback_on_failure: true) do
        sketchup.active_model.entities.to_a.each do |entity|
          layer_name = entity_layer_name(entity)
          if all_entities || (layer_name && layers_to_clean.include?(layer_name))
            entity_id = entity_id_string(entity)
            if erase_entity(entity)
              deleted_count += 1
              deleted_ids << entity_id if entity_id
            end
          end
        end
      end

      # Also clean up empty layers
      cleanup_empty_layers(layers_to_clean) unless all_entities

      {
        deleted_count: deleted_count,
        deleted_ids: deleted_ids,
        layers_cleaned: all_entities ? ["*"] : layers_to_clean,
        all_entities: all_entities,
      }
    end

    def self.cleanup_by_tag(tag)
      """Delete entities with specific tag (definition name contains tag)."""
      deleted_count = 0
      deleted_ids = []

      UndoManager.with_transaction(name: "Cleanup by Tag", rollback_on_failure: true) do
        sketchup.active_model.entities.to_a.each do |entity|
          next unless valid_entity?(entity)

          if entity.respond_to?(:definition) && entity.definition
            if entity.definition.name.include?(tag)
              entity_id = entity_id_string(entity)
              if erase_entity(entity)
                deleted_count += 1
                deleted_ids << entity_id if entity_id
              end
            end
          end
        end
      end

      { deleted_count: deleted_count, deleted_ids: deleted_ids, tag: tag }
    end

    def self.find_by_id(entity_id)
      all_entities = sketchup.active_model.entities.to_a
      all_entities.find { |e| e.entityID.to_s == entity_id }
    end

    def self.find_by_layer(layer_name)
      layer = sketchup.active_model.layers[layer_name]
      return [] unless layer

      sketchup.active_model.entities.select { |e| e.layer == layer }
    end

    def self.list_ai_layers
      """Return list of AI-managed layers that exist in model."""
      AI_LAYERS.select do |layer_name|
        sketchup.active_model.layers[layer_name]
      end
    end

    def self.get_entity_summary
      """Get summary of entities by layer for debugging."""
      summary = {}

      sketchup.active_model.entities.each do |entity|
        layer_name = entity.layer ? entity.layer.name : "No Layer"
        summary[layer_name] ||= { count: 0, entity_ids: [] }
        summary[layer_name][:count] += 1
        summary[layer_name][:entity_ids] << entity.entityID.to_s
      end

      summary
    end

    private

    def self.erase_entity(entity)
      return false unless entity
      return false unless valid_entity?(entity)
      return false unless entity.respond_to?(:erase!)

      entity.erase!
      true
    end

    def self.valid_entity?(entity)
      return false unless entity
      return entity.valid? if entity.respond_to?(:valid?)

      true
    rescue
      false
    end

    def self.entity_id_string(entity)
      return nil unless valid_entity?(entity)

      entity.entityID.to_s
    rescue
      nil
    end

    def self.entity_layer_name(entity)
      return nil unless valid_entity?(entity)

      entity.layer&.name
    rescue
      nil
    end

    def self.cleanup_empty_layers(layer_names)
      """Remove layers that have no entities."""
      layer_names.each do |layer_name|
        layer = sketchup.active_model.layers[layer_name]
        next unless layer

        # Check if any entities use this layer
        entities_on_layer = sketchup.active_model.entities.select do |entity|
          valid_entity?(entity) && entity.layer == layer
        rescue
          false
        end
        if entities_on_layer.empty?
          sketchup.active_model.layers.remove(layer)
        end
      end
    end
  end
end
