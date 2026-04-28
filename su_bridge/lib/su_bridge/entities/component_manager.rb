# frozen_string_literal: true

require "fileutils"

module SuBridge
  module Entities
    # Manages SketchUp component placement from library.
    class ComponentManager
      # Get Sketchup reference dynamically to avoid constant resolution issues
      def self.sketchup
        ::Object.const_get('Sketchup')
      end

      # Convert mm to inches (SketchUp internal unit)
      def self.mm_to_inch(mm)
        mm.to_f / 25.4
      end

      COMPONENT_CACHE = {}
      DEFINITION_CACHE = {}

      def self.place(
        skp_path:,
        position:,
        rotation: 0.0,
        scale: 1.0,
        component_id: nil,
        instance_id: nil,
        procedural_fallback: nil,
        dimensions: nil,
        layer: nil,
        name: nil
      )
        raise ::SuBridge::UndoManager::ValidationError, "skp_path required" unless skp_path
        raise ::SuBridge::UndoManager::ValidationError, "position required" unless position

        definition = load_component(skp_path)

        # Create transform
        transform = create_transform(position, rotation, scale)

        # Place instance
        instance = sketchup.active_model.active_entities.add_instance(definition, transform)

        COMPONENT_CACHE[component_id] = instance.entityID if component_id

        {
          entity_id: instance.entityID.to_s,
          definition_name: definition.name,
          fallback_used: false,
          bounds: get_instance_bounds(instance),
        }
      rescue ::SuBridge::UndoManager::ValidationError => e
        raise unless procedural_fallback

        place_procedural(
          procedural_fallback: procedural_fallback,
          position: position,
          rotation: rotation,
          scale: scale,
          component_id: component_id,
          instance_id: instance_id,
          dimensions: dimensions,
          layer: layer,
          name: name,
          original_error: e.message
        )
      end

      def self.load_component(skp_path)
        resolved_path = resolve_skp_path(skp_path)

        # Check cache first
        cached = DEFINITION_CACHE[resolved_path]
        return cached if cached

        unless File.exist?(resolved_path)
          raise ::SuBridge::UndoManager::ValidationError, "SKP file not found: #{resolved_path}"
        end

        # Import or find existing definition
        model = sketchup.active_model

        # Check if already loaded
        definition = model.definitions.find { |d| d.name.include?(File.basename(resolved_path, ".skp")) }

        unless definition
          # Import the SKP file
          status = model.import(resolved_path, false)
          definition = model.definitions.last
        end

        DEFINITION_CACHE[resolved_path] = definition
        definition
      end

      def self.place_procedural(
        procedural_fallback:,
        position:,
        rotation: 0.0,
        scale: 1.0,
        component_id: nil,
        instance_id: nil,
        dimensions: nil,
        layer: nil,
        name: nil,
        original_error: nil
      )
        raise ::SuBridge::UndoManager::ValidationError, "dimensions required for procedural fallback" unless dimensions

        width = dimensions.fetch("width")
        depth = dimensions.fetch("depth")
        height = dimensions.fetch("height")
        corner = [
          position[0] - width / 2.0,
          position[1],
          position[2],
        ]
        group = SuBridge::Entities::FaceBuilder.create_box(
          corner,
          width * scale,
          depth * scale,
          height * scale,
          { "layer" => layer }
        )

        if group.respond_to?(:name=)
          group.name = name || instance_id || component_id || procedural_fallback
        end

        COMPONENT_CACHE[component_id] = group.entityID if component_id

        {
          entity_id: group.entityID.to_s,
          definition_name: "Procedural #{procedural_fallback}",
          fallback_used: true,
          fallback_reason: original_error,
          bounds: get_instance_bounds(group),
          spatial_delta: spatial_delta(group),
        }
      end

      def self.create_transform(position, rotation, scale)
        # Create a transformation matrix
        tr = Geom::Transformation.new

        # Move to position (convert mm to inches for SketchUp)
        point = Geom::Point3d.new(mm_to_inch(position[0]), mm_to_inch(position[1]), mm_to_inch(position[2]))
        tr = Geom::Transformation.new(point)

        # Apply rotation around Z axis (Y-up rotation)
        if rotation != 0
          rotation_tr = Geom::Transformation.rotation(
            ORIGIN,
            Z_AXIS,
            rotation.degrees
          )
          tr = rotation_tr * tr
        end

        # Apply scale
        if scale != 1.0
          scale_tr = Geom::Transformation.scaling(ORIGIN, scale)
          tr = scale_tr * tr
        end

        tr
      end

      def self.get_instance_bounds(instance)
        bbox = instance.bounds
        {
          min: [bbox.min.x, bbox.min.y, bbox.min.z],
          max: [bbox.max.x, bbox.max.y, bbox.max.z],
        }
      end

      def self.spatial_delta(instance)
        bbox = instance.bounds
        {
          bounding_box: {
            min: [bbox.min.x.to_mm, bbox.min.y.to_mm, bbox.min.z.to_mm],
            max: [bbox.max.x.to_mm, bbox.max.y.to_mm, bbox.max.z.to_mm],
          },
          volume_mm3: bbox.width.to_mm * bbox.depth.to_mm * bbox.height.to_mm,
        }
      end

      def self.find_by_id(component_id)
        COMPONENT_CACHE[component_id]
      end

      def self.clear_cache
        COMPONENT_CACHE.clear
        DEFINITION_CACHE.clear
      end

      private

      def self.resolve_skp_path(skp_path)
        if skp_path.start_with?("${")
          env_var = skp_path.match(/\$\{(\w+)\}/)[1]
          env_path = ENV[env_var] || ""
          skp_path = skp_path.gsub("${#{env_var}}", env_path)
        end
        skp_path
      end
    end
  end
end
