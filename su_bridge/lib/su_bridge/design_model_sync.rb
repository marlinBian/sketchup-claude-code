# frozen_string_literal: true

require 'json'
require 'monitor'
require 'time'

module SuBridge
  # Syncs SketchUp model state to design_model.json file.
  #
  # This module provides bidirectional sync between SketchUp's live model
  # and the JSON design model that LLM can read/write.
  #
  # Sync is triggered:
  # - On model save (on_save hook)
  # - On explicit sync request via sync_to_file! or sync_from_file!
  # - On entity changes (debounced via EntityObserver)
  class DesignModelSync
    attr_reader :project_path

    # Get Sketchup reference dynamically to avoid constant resolution issues
    def self.sketchup
      ::Object.const_get('Sketchup')
    end

    # Default design model file name (hidden file)
    DESIGN_MODEL_FILENAME = ".design_model.json".freeze

    # Layer names that SCC manages
    AI_LAYERS = %w[Walls Floors Furniture Fixtures Lighting Windows Doors Stairs Ceiling].freeze

    def initialize(project_path = nil)
      @project_path = project_path || default_project_path
      @design_model_path = File.join(@project_path, DESIGN_MODEL_FILENAME)
      @observer = nil
    end

    # Get the path to design_model.json
    # @return [String] Full path to design_model.json
    def design_model_path
      @design_model_path
    end

    # Get the current design model data
    # @return [Hash, nil] Parsed JSON data or nil if file doesn't exist
    def load
      return nil unless File.exist?(@design_model_path)

      JSON.parse(File.read(@design_model_path))
    rescue JSON::ParserError => e
      puts "[SuBridge] Failed to parse design_model.json: #{e.message}"
      nil
    end

    # Save design model data to file
    # @param data [Hash] Design model data to save
    # @return [Boolean] true if successful
    def save(data)
      data["updated_at"] = Time.now.utc.iso8601 if data.is_a?(Hash)
      File.write(@design_model_path, JSON.pretty_generate(data))
      true
    rescue IOError, JSON::GeneratorError => e
      puts "[SuBridge] Failed to save design_model.json: #{e.message}"
      false
    end

    # Add a single entity to design_model.json
    # @param entity [sketchup::Entity] Entity to add
    # @return [Boolean] true if successful
    def add_entity(entity)
      return false unless entity

      data = load || create_empty_model
      data["components"] ||= {}
      data["updated_at"] = Time.now.utc.iso8601

      entity_id = "entity_#{entity.entityID}"
      data["components"][entity_id] = entity_to_hash(entity)

      save(data)
    rescue => e
      puts "[SuBridge] Failed to add entity: #{e.message}"
      false
    end

    # Remove an entity from design_model.json
    # @param entity_id [Integer] SketchUp entity ID to remove
    # @return [Boolean] true if successful
    def remove_entity(entity_id)
      data = load
      return false unless data

      data["components"] ||= {}
      key = "entity_#{entity_id}"

      if data["components"].delete(key)
        data["updated_at"] = Time.now.utc.iso8601
        save(data)
      else
        false
      end
    rescue => e
      puts "[SuBridge] Failed to remove entity: #{e.message}"
      false
    end

    # Update entity position after move/rotate/scale
    # @param entity_id [Integer] SketchUp entity ID
    # @param new_position [Array<Float>] New position [x, y, z] in mm
    # @param new_rotation [Float] New rotation in degrees (optional)
    # @return [Boolean] true if successful
    def update_entity_position(entity_id, new_position, new_rotation = nil)
      data = load
      return false unless data

      data["components"] ||= {}
      key = "entity_#{entity_id}"
      component = data["components"][key]

      if component
        component["position"] = new_position
        component["rotation"] = new_rotation if new_rotation
        data["updated_at"] = Time.now.utc.iso8601
        save(data)
      else
        false
      end
    rescue => e
      puts "[SuBridge] Failed to update entity position: #{e.message}"
      false
    end

    # Batch update for debounced sync
    # @param changes [Array<Hash>] Changes to apply
    #   Each change: { operation: :add|:remove|:update, entity_id: Integer, data: Hash }
    # @return [Boolean] true if successful
    def batch_update(changes)
      return true if changes.empty?

      data = load || create_empty_model
      data["components"] ||= {}
      data["updated_at"] = Time.now.utc.iso8601

      changes.each do |change|
        operation = change[:operation]
        entity_id = change[:entity_id]
        key = "entity_#{entity_id}"

        case operation
        when :add
          entity_data = change[:data]
          data["components"][key] = entity_data if entity_data
        when :remove
          data["components"].delete(key)
        when :update
          entity_data = change[:data]
          if data["components"][key] && entity_data
            data["components"][key].merge!(entity_data)
          end
        end
      end

      save(data)
    rescue => e
      puts "[SuBridge] Failed to batch update: #{e.message}"
      false
    end

    # Sync SketchUp model state to design_model.json
    # Reads all relevant entities and writes to JSON file
    #
    # @return [Hash] Result with counts of synced entities
    def sync_to_file!
      return { error: "Model not available" } unless ::Sketchup.active_model

      model = ::Sketchup.active_model
      data = load || create_empty_model

      # Update timestamp
      data["updated_at"] = Time.now.utc.iso8601

      # Sync entities from SketchUp
      data["components"] = extract_components(model)
      data["layers"] = extract_layers(model)

      # Save
      if save(data)
        { success: true, component_count: data["components"].size }
      else
        { error: "Failed to save design_model.json" }
      end
    end

    # Sync from design_model.json to SketchUp model
    # Applies entity positions and properties from JSON to SketchUp
    #
    # @return [Hash] Result with counts of synced entities
    def sync_from_file!
      return { error: "Model not available" } unless ::Sketchup.active_model
      return { error: "design_model.json not found" } unless File.exist?(@design_model_path)

      model = ::Sketchup.active_model
      data = load

      return { error: "Failed to load design_model.json" } unless data

      # Apply components to model
      apply_components(model, data["components"] || {})

      { success: true }
    end

    # Register SketchUp model observer for auto-sync
    # @return [EntityObserver] The registered observer
    def register_observer
      return @observer if @observer

      model = ::Sketchup.active_model
      return nil unless model

      @observer = EntityObserver.new(self)
      model.add_observer(@observer)
      @observer
    end

    # Unregister observer
    def unregister_observer
      return unless @observer

      model = ::Sketchup.active_model
      model.remove_observer(@observer) if model
      @observer = nil
    end

    private

    # Get default project path based on current model
    # @return [String] Default project path
    def default_project_path
      model = ::Sketchup.active_model
      if model && model.path && !model.path.empty?
        File.dirname(model.path)
      else
        File.join(Dir.pwd, "designs", "default")
      end
    end

    # Create empty design model template
    # @return [Hash] Empty template
    def create_empty_model
      {
        "version" => "1.0",
        "project_name" => File.basename(@project_path),
        "created_at" => Time.now.utc.iso8601,
        "updated_at" => Time.now.utc.iso8601,
        "metadata" => {
          "style" => "",
          "ceiling_height" => 2400,
          "units" => "mm"
        },
        "spaces" => {},
        "components" => {},
        "lighting" => {},
        "semantic_anchors" => {},
        "layers" => {}
      }
    end

    # Extract components from SketchUp model
    # @param model [sketchup::Model] SketchUp model
    # @return [Hash] Components keyed by entity_id
    def extract_components(model)
      components = {}

      # Get all entities from AI-managed layers
      AI_LAYERS.each do |layer_name|
        layer = model.layers.find { |l| l.name == layer_name }
        next unless layer

        layer.entities.each do |entity|
          next unless valid_entity?(entity)

          entity_id = "entity_#{entity.entityID}"
          components[entity_id] = entity_to_hash(entity)
        end
      end

      components
    end

    # Extract layers from SketchUp model
    # @param model [sketchup::Model] SketchUp model
    # @return [Hash] Layers with colors
    def extract_layers(model)
      layers = {}

      model.layers.each do |layer|
        next unless AI_LAYERS.include?(layer.name)

        layers[layer.name] = {
          "color" => layer.color ? layer.color.to_s : "#CCCCCC"
        }
      end

      layers
    end

    # Convert SketchUp entity to hash
    # @param entity [sketchup::Entity] Entity to convert
    # @return [Hash] Entity data
    def entity_to_hash(entity)
      trans = entity.transformation
      bounds = entity.bounds

      position = if trans && trans.origin
                   inch_to_mm(trans.origin.to_a)
                 elsif bounds
                   inch_to_mm(bounds.center.to_a)
                 else
                   [0, 0, 0]
                 end

      dimensions = if bounds
                     {
                       "width" => inch_to_mm(bounds.width),
                       "depth" => inch_to_mm(bounds.depth),
                       "height" => bounds.height ? inch_to_mm(bounds.height) : 0
                     }
                   else
                     { "width" => 0, "depth" => 0, "height" => 0 }
                   end

      layer_name = entity.layer ? entity.layer.name : "Other"

      {
        "type" => entity.class.name.split("::").last.downcase,
        "name" => entity.name || "",
        "position" => position,
        "dimensions" => dimensions,
        "rotation" => extract_rotation(trans),
        "layer" => layer_name
      }
    end

    # Extract rotation angle from transformation (Z-axis rotation in degrees)
    # @param trans [sketchup::Transformation, nil] Transformation
    # @return [Float] Rotation in degrees
    def extract_rotation(trans)
      return 0 unless trans

      # Get Z-axis rotation from transformation matrix
      # This is a simplified extraction
      angle = Math.atan2(trans[0, 1], trans[0, 0])
      (angle * 180 / Math::PI).round(2)
    end

    # Convert inches to millimeters
    # @param value [Numeric] Value in inches
    # @return [Float] Value in mm
    def inch_to_mm(value)
      return value.map { |item| inch_to_mm(item) } if value.is_a?(Array)

      (value.to_f * 25.4).round(2)
    end

    # Check if entity should be tracked
    # @param entity [sketchup::Entity] Entity to check
    # @return [Boolean] true if entity is valid for tracking
    def valid_entity?(entity)
      return false unless entity
      return false unless entity.layer
      return false unless AI_LAYERS.include?(entity.layer.name)

      # Only track groups and component instances for now
      entity.is_a?(::Sketchup::Group) || entity.is_a?(::Sketchup::ComponentInstance)
    end

    # Apply components from design model to SketchUp model
    # @param model [sketchup::Model] SketchUp model
    # @param components [Hash] Components to apply
    def apply_components(model, components)
      # TODO: Implement applying entities from JSON back to SketchUp
      # This is more complex as it requires creating actual geometry
      puts "[SuBridge] apply_components not yet implemented"
    end
  end

  # Hooks module for automatic sync configuration
  module Hooks
    class << self
      attr_accessor :enabled, :debounce_ms, :sync_on_undo

      def enabled?
        @enabled != false
      end

      def enable!
        @enabled = true
      end

      def disable!
        @enabled = false
      end

      def debounce_ms
        @debounce_ms || 500
      end

      def sync_on_undo?
        @sync_on_undo == true
      end

      def configure(debounce_ms: nil, sync_on_undo: nil)
        @debounce_ms = debounce_ms if debounce_ms
        @sync_on_undo = sync_on_undo if sync_on_undo
      end

      def reset!
        @enabled = true
        @debounce_ms = 500
        @sync_on_undo = false
      end
    end

    # Initialize defaults
    @enabled = true
    @debounce_ms = 500
    @sync_on_undo = false
  end

  # SketchUp Entity Observer for automatic design model sync
  # Uses debounced sync to batch changes and avoid excessive file I/O
  class EntityObserver < (::Sketchup)::ModelObserver
    def initialize(sync_manager)
      @sync_manager = sync_manager
      @pending_changes = []
      @debounce_timer = nil
      @lock = Monitor.new
    end

    # Called when an entity is added to the model
    # @param model [sketchup::Model] The model
    # @param entity [sketchup::Entity] The added entity
    def onEntityAdded(model, entity)
      return unless Hooks.enabled?
      return unless should_track?(entity)

      @lock.synchronize do
        @pending_changes << {
          operation: :add,
          entity_id: entity.entityID,
          data: entity_to_change_data(entity),
          timestamp: Time.now
        }
      end

      schedule_debounced_sync
    end

    # Called when an entity is removed from the model
    # @param model [sketchup::Model] The model
    # @param entity [sketchup::Entity] The removed entity
    def onEntityRemoved(model, entity)
      return unless Hooks.enabled?

      # Entity ID from removed entity
      entity_id = entity.entityID

      @lock.synchronize do
        @pending_changes << {
          operation: :remove,
          entity_id: entity_id,
          timestamp: Time.now
        }
      end

      schedule_debounced_sync
    end

    # Called when a transaction is undone
    # @param model [sketchup::Model] The model
    def onTransactionUndo(model)
      return unless Hooks.enabled?
      return unless Hooks.sync_on_undo?

      # Cancel any pending debounced sync
      UI.stop_timer(@debounce_timer) if @debounce_timer

      # Clear pending changes as we're rolling back
      @lock.synchronize do
        @pending_changes.clear
      end

      # Perform full sync to reflect the undo state
      @sync_manager.sync_to_file!
    end

    # Called when the model is saved
    # @param model [sketchup::Model] The model
    def onSaveModel(model)
      return unless Hooks.enabled?

      # Cancel any pending debounced sync
      UI.stop_timer(@debounce_timer) if @debounce_timer

      # Clear pending changes since we're saving
      @lock.synchronize do
        @pending_changes.clear
      end

      # Immediate sync on save
      @sync_manager.sync_to_file!
    end

    # Called when entities are transformed (moved/rotated/scaled)
    # This is triggered via the model's onEntityChange observer
    # @param model [sketchup::Model] The model
    # @param entity [sketchup::Entity] The transformed entity
    def onEntityChange(model, entity)
      return unless Hooks.enabled?
      return unless should_track?(entity)
      return unless entity.is_a?(::Sketchup::Group) || entity.is_a?(::Sketchup::ComponentInstance)

      @lock.synchronize do
        @pending_changes << {
          operation: :update,
          entity_id: entity.entityID,
          data: entity_to_change_data(entity),
          timestamp: Time.now
        }
      end

      schedule_debounced_sync
    end

    private

    # Check if entity should be tracked
    # @param entity [sketchup::Entity] Entity to check
    # @return [Boolean] true if entity should be tracked
    def should_track?(entity)
      return false unless entity
      return false unless entity.layer

      DesignModelSync::AI_LAYERS.include?(entity.layer.name)
    end

    # Convert entity to change data hash
    # @param entity [sketchup::Entity] Entity to convert
    # @return [Hash] Entity data for change tracking
    def entity_to_change_data(entity)
      trans = entity.transformation
      bounds = entity.bounds

      position = if trans && trans.origin
                   inch_to_mm(trans.origin.to_a)
                 elsif bounds
                   inch_to_mm(bounds.center.to_a)
                 else
                   [0, 0, 0]
                 end

      dimensions = if bounds
                     {
                       "width" => inch_to_mm(bounds.width),
                       "depth" => inch_to_mm(bounds.depth),
                       "height" => bounds.height ? inch_to_mm(bounds.height) : 0
                     }
                   else
                     { "width" => 0, "depth" => 0, "height" => 0 }
                   end

      layer_name = entity.layer ? entity.layer.name : "Other"

      {
        "type" => entity.class.name.split("::").last.downcase,
        "name" => entity.name || "",
        "position" => position,
        "dimensions" => dimensions,
        "rotation" => extract_rotation(trans),
        "layer" => layer_name
      }
    end

    # Extract rotation angle from transformation
    # @param trans [sketchup::Transformation, nil] Transformation
    # @return [Float] Rotation in degrees
    def extract_rotation(trans)
      return 0 unless trans

      angle = Math.atan2(trans[0, 1], trans[0, 0])
      (angle * 180 / Math::PI).round(2)
    end

    # Convert inches to millimeters
    # @param value [Numeric] Value in inches
    # @return [Float] Value in mm
    def inch_to_mm(value)
      (value.to_f * 25.4).round(2)
    end

    # Schedule a debounced sync using UI.start_timer
    # @return [void]
    def schedule_debounced_sync
      # Cancel existing timer
      UI.stop_timer(@debounce_timer) if @debounce_timer

      # Schedule new sync after debounce delay
      @debounce_timer = UI.start_timer(Hooks.debounce_ms / 1000.0, false) do
        perform_sync
      end
    end

    # Perform the actual sync with pending changes
    # @return [void]
    def perform_sync
      changes = @lock.synchronize do
        return if @pending_changes.empty?

        changes = @pending_changes.dup
        @pending_changes.clear
        changes
      end

      return if changes.empty?

      puts "[SuBridge] Syncing #{changes.size} changes to design_model.json"

      # Use batch_update for efficient single-file-write
      @sync_manager.batch_update(changes)
    rescue => e
      puts "[SuBridge] Sync failed: #{e.message}"
    end
  end
end
