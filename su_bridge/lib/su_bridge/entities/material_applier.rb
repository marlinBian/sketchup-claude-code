# frozen_string_literal: true

module SuBridge
  module Entities
    # Applies materials and textures to entities with color and scale support.
    class MaterialApplier
      # Get Sketchup reference dynamically to avoid constant resolution issues
      def self.sketchup
        ::Object.const_get('Sketchup')
      end

      def self.apply(entity_ids, material_id: nil, color: nil, texture_scale: nil)
        material = find_or_create_material(material_id, color, texture_scale)
        entities = find_entities(entity_ids)

        transaction do
          entities.each do |entity|
            apply_to_entity(entity, material, texture_scale)
          end
        end

        { applied_to: entity_ids.length, material_name: material.name }
      end

      def self.apply_to_face(face, color: nil, texture_scale: nil)
        material = find_or_create_material(nil, color, texture_scale)
        face.material = material
        apply_texture_scale(face, texture_scale) if texture_scale
      end

      def self.apply_to_entity(entity, material, texture_scale = nil)
        entity.material = material
        if texture_scale && entity.respond_to?(:texture_scale=)
          apply_texture_scale(entity, texture_scale)
        end
      end

      def self.apply_style(style_name, entity_ids: nil)
        style = STYLE_PRESETS[style_name]
        raise ValidationError, "Unknown style: #{style_name}" unless style

        results = []
        entities = entity_ids ? find_entities(entity_ids) : all_faces

        style["materials"].each do |mat_def|
          material = find_or_create_material(
            mat_def["id"],
            mat_def["color"],
            mat_def["texture_scale"]
          )

          # Apply to matching entities (simplified - would need better matching)
          entities.each do |entity|
            if matches_criteria(entity, mat_def["criteria"])
              entity.material = material
              results << { entity_id: entity.entityID.to_s, material: mat_def["id"] }
            end
          end
        end

        results
      end

      def self.find_or_create_material(material_id, color = nil, texture_scale = nil)
        # If material_id provided, try to find existing
        if material_id
          existing = sketchup.active_model.materials[material_id]
          return existing if existing
        end

        # If color provided, create from color
        if color
          material = create_material_from_color(color, material_id || "CustomMaterial")
          apply_texture_scale_to_material(material, texture_scale) if texture_scale
          return material
        end

        # Fallback: create generic material
        name = material_id || "UnnamedMaterial"
        sketchup.active_model.materials.add(name)
      end

      def self.create_material_from_color(color_input, name)
        color = parse_color(color_input)
        material = sketchup.active_model.materials.add(name)
        material.color = color
        material
      end

      def self.parse_color(color_input)
        case color_input
        when String
          if color_input.start_with?("#")
            # Hex color
            hex = color_input[1..7]
            r = hex[0..1].to_i(16)
            g = hex[2..3].to_i(16)
            b = hex[4..5].to_i(16)
            return sketchup.const_get("Color").new(r, g, b)
          else
            # Named color or RGB array string
            return sketchup.const_get("Color").new(color_input)
          end
        when Array
          # RGB array [r, g, b]
          return sketchup.const_get("Color").new(color_input[0], color_input[1], color_input[2])
        when sketchup.const_get("Color")
          return color_input
        else
          return sketchup.const_get("Color").new(128, 128, 128) # Default gray
        end
      end

      def self.apply_texture_scale(entity, scale)
        return unless scale && entity.respond_to?(:texture_scale)

        if entity.is_a?(sketchup.const_get("Face"))
          # Get the face's mesh for texture coordinates
          mesh = entity.mesh
          # Texture scale is applied to material
        end

        # Set texture tiling
        if entity.material
          entity.material.texture.scale(
            scale[0].to_f / 1000.0,
            scale[1].to_f / 1000.0
          )
        end
      end

      def self.apply_texture_scale_to_material(material, scale)
        return unless scale && material

        material.texture.scale(
          scale[0].to_f / 1000.0,
          scale[1].to_f / 1000.0
        )
      end

      def self.find_entities(entity_ids)
        all_entities = sketchup.active_model.entities.to_a
        all_entities.select { |e| entity_ids.include?(e.entityID.to_s) }
      end

      def self.all_faces
        sketchup.active_model.entities.select { |e| e.is_a?(sketchup.const_get("Face")) }
      end

      def self.matches_criteria(entity, criteria)
        # Simplified criteria matching
        return true unless criteria
        # Would implement more sophisticated matching based on criteria
      end

      def self.transaction
        model = sketchup.active_model
        model.start_operation("Apply Material", true)
        begin
          result = yield
          model.commit_operation
          result
        rescue => e
          model.abort_operation
          raise e
        end
      end

      # Style presets (simplified - full definitions in skills/styles.md)
      STYLE_PRESETS = {
        "japandi_cream" => {
          "name" => "Japandi Cream",
          "materials" => [
            { "id" => "japandi_wall_cream", "color" => "#F5F0E8", "criteria" => { "type" => "wall" } },
            { "id" => "japandi_wood_oak", "color" => "#C4A77D", "criteria" => { "type" => "floor" } },
          ]
        },
        "modern_industrial" => {
          "name" => "Modern Industrial",
          "materials" => [
            { "id" => "industrial_concrete", "color" => "#B8B5B0", "criteria" => { "type" => "wall" } },
            { "id" => "industrial_metal_black", "color" => "#2A2A2A", "criteria" => { "type" => "furniture" } },
          ]
        },
        "scandinavian" => {
          "name" => "Scandinavian",
          "materials" => [
            { "id" => "scandi_wall_white", "color" => "#FAFAFA", "criteria" => { "type" => "wall" } },
            { "id" => "scandi_floor_light_wood", "color" => "#E8DCC8", "criteria" => { "type" => "floor" } },
            { "id" => "scandi_wood_oak", "color" => "#D4B896", "criteria" => { "type" => "furniture" } },
            { "id" => "scandi_trim_white", "color" => "#FFFFFF", "criteria" => { "type" => "trim" } },
          ]
        },
        "mediterranean" => {
          "name" => "Mediterranean",
          "materials" => [
            { "id" => "mediterr_wall_terracotta", "color" => "#D4A574", "criteria" => { "type" => "wall" } },
            { "id" => "mediterr_floor_tile", "color" => "#C17F59", "criteria" => { "type" => "floor" } },
            { "id" => "mediterr_wood_warm", "color" => "#8B5A2B", "criteria" => { "type" => "furniture" } },
            { "id" => "mediterr_blue_accent", "color" => "#5B7C99", "criteria" => { "type" => "trim" } },
          ]
        },
        "bohemian" => {
          "name" => "Bohemian",
          "materials" => [
            { "id" => "boho_wall_cream", "color" => "#F5E6D3", "criteria" => { "type" => "wall" } },
            { "id" => "boho_floor_terracotta", "color" => "#C67B5C", "criteria" => { "type" => "floor" } },
            { "id" => "boho_wood_walnut", "color" => "#5D4037", "criteria" => { "type" => "furniture" } },
            { "id" => "boho_pattern_accent", "color" => "#D4A574", "criteria" => { "type" => "trim" } },
          ]
        },
        "contemporary_minimalist" => {
          "name" => "Contemporary Minimalist",
          "materials" => [
            { "id" => "minimal_wall_pure_white", "color" => "#F5F5F5", "criteria" => { "type" => "wall" } },
            { "id" => "minimal_floor_concrete", "color" => "#9E9E9E", "criteria" => { "type" => "floor" } },
            { "id" => "minimal_metal_chrome", "color" => "#757575", "criteria" => { "type" => "furniture" } },
            { "id" => "minimal_trim_matte", "color" => "#EEEEEE", "criteria" => { "type" => "trim" } },
          ]
        },
      }.freeze

      class ValidationError < StandardError; end
    end
  end
end
