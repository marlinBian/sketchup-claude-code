# frozen_string_literal: true

module SuBridge
  module Entities
    # Builds windows in SketchUp walls with frame and glass.
    class WindowBuilder
      # Get Sketchup reference dynamically to avoid constant resolution issues
      def self.sketchup
        ::Object.const_get('Sketchup')
      end

      # Convert mm to inches (SketchUp internal unit)
      def self.mm_to_inch(mm)
        mm.to_f / 25.4
      end

      # Create a window in a wall
      # @param wall_id [String] Entity ID of the wall
      # @param position_x [Float] Position along the wall from start in mm
      # @param position_y [Float] Position from wall face in mm
      # @param width [Float] Window width in mm (default 1200mm)
      # @param height [Float] Window height in mm (default 1000mm)
      # @param sill_height [Float] Height from floor to windowsill in mm (default 900mm)
      # @return [Hash] Result with entity_ids and spatial_delta
      def self.create(wall_id:, position_x:, position_y:, width: 1200, height: 1000, sill_height: 900)
        validate_params!(wall_id, position_x, position_y, width, height, sill_height)

        # Find the wall entity
        wall_entity = find_entity(wall_id)
        raise ::SuBridge::UndoManager::EntityNotFoundError, "Wall not found: #{wall_id}" unless wall_entity

        # Calculate window position
        window_center = calculate_window_center(wall_entity, position_x, position_y, sill_height, height)

        # Create window group
        window_group = create_window_group(wall_entity, window_center, width, height, position_y)

        # Get all entity IDs created
        entity_ids = collect_entity_ids(window_group)

        {
          entity_ids: entity_ids,
          spatial_delta: spatial_delta(window_group),
          model_revision: 1,
          elapsed_ms: 0,
        }
      end

      def self.spatial_delta(group)
        bbox = group.bounds
        {
          bounding_box: {
            min: [bbox.min.x.to_mm, bbox.min.y.to_mm, bbox.min.z.to_mm],
            max: [bbox.max.x.to_mm, bbox.max.y.to_mm, bbox.max.z.to_mm],
          },
          volume_mm3: calculate_volume(group),
        }
      end

      private

      def self.validate_params!(wall_id, position_x, position_y, width, height, sill_height)
        raise ::SuBridge::UndoManager::ValidationError, "wall_id required" unless wall_id
        raise ::SuBridge::UndoManager::ValidationError, "position_x required" unless position_x
        raise ::SuBridge::UndoManager::ValidationError, "position_y required" unless position_y
        raise ::SuBridge::UndoManager::ValidationError, "width must be positive" unless width && width > 0
        raise ::SuBridge::UndoManager::ValidationError, "height must be positive" unless height && height > 0
        raise ::SuBridge::UndoManager::ValidationError, "sill_height must be non-negative" unless sill_height && sill_height >= 0
      end

      def self.find_entity(entity_id)
        sketchup.active_model.entities.find { |e| e.entityID.to_s == entity_id }
      end

      def self.calculate_window_center(wall_entity, position_x, position_y, sill_height, height)
        wall_bounds = wall_entity.bounds
        wall_min = wall_bounds.min

        # Position in inches (SketchUp internal units)
        px = mm_to_inch(position_x)
        py = wall_min.y + mm_to_inch(position_y)

        # Z position is sill height + half window height
        z_sill = wall_min.z + mm_to_inch(sill_height)
        z_center = z_sill + mm_to_inch(height / 2.0)

        Geom::Point3d.new(px, py, z_center)
      end

      def self.create_window_group(wall_entity, window_center, width, height, depth)
        model = sketchup.active_model

        # Convert dimensions to inches
        w = mm_to_inch(width)
        h = mm_to_inch(height)
        d = mm_to_inch(depth)

        # Create empty group
        group = model.entities.add_group

        # Window frame - 4 sides
        frame_thickness = mm_to_inch(60)  # 60mm frame width
        frame_depth = mm_to_inch(80)       # 80mm frame depth

        half_w = w / 2
        half_h = h / 2

        # Top frame
        top_pts = [
          Geom::Point3d.new(window_center.x - half_w - frame_thickness, window_center.y, window_center.z - half_h),
          Geom::Point3d.new(window_center.x + half_w + frame_thickness, window_center.y, window_center.z - half_h),
          Geom::Point3d.new(window_center.x + half_w + frame_thickness, window_center.y + frame_depth, window_center.z - half_h),
          Geom::Point3d.new(window_center.x - half_w - frame_thickness, window_center.y + frame_depth, window_center.z - half_h),
        ]
        group.entities.add_face(top_pts) if top_pts.all? { |p| p.valid? }

        # Bottom frame (sill)
        bottom_pts = [
          Geom::Point3d.new(window_center.x - half_w - frame_thickness, window_center.y, window_center.z + half_h),
          Geom::Point3d.new(window_center.x + half_w + frame_thickness, window_center.y, window_center.z + half_h),
          Geom::Point3d.new(window_center.x + half_w + frame_thickness, window_center.y + frame_depth, window_center.z + half_h),
          Geom::Point3d.new(window_center.x - half_w - frame_thickness, window_center.y + frame_depth, window_center.z + half_h),
        ]
        group.entities.add_face(bottom_pts) if bottom_pts.all? { |p| p.valid? }

        # Left frame
        left_pts = [
          Geom::Point3d.new(window_center.x - half_w - frame_thickness, window_center.y, window_center.z - half_h),
          Geom::Point3d.new(window_center.x - half_w, window_center.y, window_center.z - half_h),
          Geom::Point3d.new(window_center.x - half_w, window_center.y + frame_depth, window_center.z - half_h),
          Geom::Point3d.new(window_center.x - half_w - frame_thickness, window_center.y + frame_depth, window_center.z - half_h),
        ]
        group.entities.add_face(left_pts) if left_pts.all? { |p| p.valid? }

        # Right frame
        right_pts = [
          Geom::Point3d.new(window_center.x + half_w, window_center.y, window_center.z - half_h),
          Geom::Point3d.new(window_center.x + half_w + frame_thickness, window_center.y, window_center.z - half_h),
          Geom::Point3d.new(window_center.x + half_w + frame_thickness, window_center.y + frame_depth, window_center.z - half_h),
          Geom::Point3d.new(window_center.x + half_w, window_center.y + frame_depth, window_center.z - half_h),
        ]
        group.entities.add_face(right_pts) if right_pts.all? { |p| p.valid? }

        # Create glass pane
        create_glass_pane(group, window_center, width, height)

        group
      end

      def self.create_glass_pane(group, window_center, width, height)
        w = mm_to_inch(width)
        h = mm_to_inch(height)
        glass_thickness = mm_to_inch(5) # 5mm glass thickness

        half_w = w / 2
        half_h = h / 2

        # Glass pane - centered in the window opening
        glass_pts = [
          Geom::Point3d.new(window_center.x - half_w, window_center.y, window_center.z - half_h),
          Geom::Point3d.new(window_center.x + half_w, window_center.y, window_center.z - half_h),
          Geom::Point3d.new(window_center.x + half_w, window_center.y, window_center.z + half_h),
          Geom::Point3d.new(window_center.x - half_w, window_center.y, window_center.z + half_h),
        ]

        return unless glass_pts.all? { |p| p.valid? }

        glass_face = group.entities.add_face(glass_pts)
        return unless glass_face && glass_face.valid?

        # Apply glass material (light blue transparent)
        apply_glass_material(glass_face)

        # Push/pull glass to create pane thickness
        glass_face.pushpull(glass_thickness, false)

        glass_face
      end

      def self.apply_glass_material(face)
        # Find or create glass material
        model = sketchup.active_model
        materials = model.materials

        glass_material = materials["SCC_Glass"]
        unless glass_material
          glass_material = materials.add("SCC_Glass")
          glass_material.color = [200, 220, 255, 128] # Light blue, semi-transparent
          glass_material.alpha = 0.3
        end

        face.material = glass_material if face.valid?
      end

      def self.collect_entity_ids(group)
        ids = [group.entityID.to_s]
        group.entities.each do |entity|
          ids << entity.entityID.to_s
        end
        ids
      end

      def self.calculate_volume(group)
        bbox = group.bounds
        bbox.width.to_mm * bbox.depth.to_mm * bbox.height.to_mm
      end
    end
  end
end
