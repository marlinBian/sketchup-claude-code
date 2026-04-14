# frozen_string_literal: true

module SuBridge
  # Manages entity deletion and lookup.
  class EntityManager
    # Get Sketchup reference dynamically to avoid constant resolution issues
    def self.sketchup
      ::Object.const_get('Sketchup')
    end

    # AI-generated content layer names
    AI_LAYERS = ["Walls", "Furniture", "Fixtures", "Lighting", "Materials"].freeze

    def self.delete(entity_ids)
      deleted = []
      all_entities = sketchup.active_model.entities.to_a

      entity_ids.each do |id|
        entity = all_entities.find { |e| e.entityID.to_s == id }
        if entity
          entity.deleted = true
          deleted << id
        end
      end

      deleted
    end

    def self.delete_all(layer_names: nil)
      """Delete all entities in specified layers or all AI layers.

      Args:
        layer_names: Specific layer names to clean. If nil, uses AI_LAYERS.

      Returns:
        Hash with deleted count and entity_ids
      """
      layers_to_clean = layer_names || AI_LAYERS
      deleted_count = 0
      deleted_ids = []

      UndoManager.with_transaction(name: "Cleanup Model", rollback_on_failure: true) do
        sketchup.active_model.entities.each do |entity|
          if entity.layer && layers_to_clean.include?(entity.layer.name)
            entity.deleted = true
            deleted_count += 1
            deleted_ids << entity.entityID.to_s
          end
        end
      end

      # Also clean up empty layers
      cleanup_empty_layers(layers_to_clean)

      {
        deleted_count: deleted_count,
        deleted_ids: deleted_ids,
        layers_cleaned: layers_to_clean,
      }
    end

    def self.cleanup_by_tag(tag)
      """Delete entities with specific tag (definition name contains tag)."""
      deleted_count = 0
      deleted_ids = []

      UndoManager.with_transaction(name: "Cleanup by Tag", rollback_on_failure: true) do
        sketchup.active_model.entities.each do |entity|
          if entity.respond_to?(:definition) && entity.definition
            if entity.definition.name.include?(tag)
              entity.deleted = true
              deleted_count += 1
              deleted_ids << entity.entityID.to_s
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

    def self.cleanup_empty_layers(layer_names)
      """Remove layers that have no entities."""
      layer_names.each do |layer_name|
        layer = sketchup.active_model.layers[layer_name]
        next unless layer

        # Check if any entities use this layer
        entities_on_layer = sketchup.active_model.entities.select { |e| e.layer == layer }
        if entities_on_layer.empty?
          sketchup.active_model.layers.remove(layer)
        end
      end
    end
  end
end
