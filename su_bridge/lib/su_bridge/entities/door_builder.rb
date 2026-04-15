# frozen_string_literal: true

module SuBridge
  module Entities
    # Builds doors in SketchUp walls with frame and swing panel.
    class DoorBuilder
      # Get Sketchup reference dynamically to avoid constant resolution issues
      def self.sketchup
        ::Object.const_get('Sketchup')
      end

      # Convert mm to inches (SketchUp internal unit)
      def self.mm_to_inch(mm)
        mm.to_f / 25.4
      end

      # Create a door in a wall
      # @param wall_id [String] Entity ID of the wall
      # @param position_x [Float] Position along the wall from start in mm
      # @param position_y [Float] Position from wall face in mm
      # @param width [Float] Door width in mm (default 900mm)
      # @param height [Float] Door height in mm (default 2100mm)
      # @param swing_direction [String] "left" or "right"
      # @return [Hash] Result with entity_ids and spatial_delta
      def self.create(wall_id:, position_x:, position_y:, width: 900, height: 2100, swing_direction: "left")
        validate_params!(wall_id, position_x, position_y, width, height, swing_direction)

        # Find the wall entity
        wall_entity = find_entity(wall_id)
        raise ::SuBridge::UndoManager::EntityNotFoundError, "Wall not found: #{wall_id}" unless wall_entity

        # Get wall bounds and geometry
        wall_bounds = wall_entity.bounds

        # Calculate door position based on wall geometry
        # For simplicity, assume wall is axis-aligned
        door_center = calculate_door_center(wall_entity, position_x, position_y, width)

        # Create door group
        door_group = create_door_group(wall_entity, door_center, width, height, position_y, swing_direction)

        # Get all entity IDs created
        entity_ids = collect_entity_ids(door_group)

        {
          entity_ids: entity_ids,
          spatial_delta: spatial_delta(door_group),
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

      def self.validate_params!(wall_id, position_x, position_y, width, height, swing_direction)
        raise ::SuBridge::UndoManager::ValidationError, "wall_id required" unless wall_id
        raise ::SuBridge::UndoManager::ValidationError, "position_x required" unless position_x
        raise ::SuBridge::UndoManager::ValidationError, "position_y required" unless position_y
        raise ::SuBridge::UndoManager::ValidationError, "width must be positive" unless width && width > 0
        raise ::SuBridge::UndoManager::ValidationError, "height must be positive" unless height && height > 0
        unless ["left", "right"].include?(swing_direction)
          raise ::SuBridge::UndoManager::ValidationError, "swing_direction must be 'left' or 'right'"
        end
      end

      def self.find_entity(entity_id)
        sketchup.active_model.entities.find { |e| e.entityID.to_s == entity_id }
      end

      def self.calculate_door_center(wall_entity, position_x, position_y, width)
        # Wall start position in mm (converted from inches)
        wall_bounds = wall_entity.bounds
        wall_min = wall_bounds.min

        # Position in inches (SketchUp internal units)
        px = mm_to_inch(position_x)
        py = wall_min.y + mm_to_inch(position_y)

        # Calculate door bottom center
        z_bottom = wall_min.z

        Geom::Point3d.new(px, py, z_bottom)
      end

      def self.create_door_group(wall_entity, door_center, width, height, depth, swing_direction)
        model = sketchup.active_model
        entities = model.entities

        # Convert dimensions to inches
        w = mm_to_inch(width)
        h = mm_to_inch(height)
        d = mm_to_inch(depth)

        # Create empty group
        group = entities.add_group

        # Door opening (rectangle cutout in wall)
        # For simplicity, create door frame as 4 rectangles (top, left, right, bottom)
        frame_thickness = mm_to_inch(50) # 50mm frame
        frame_depth = mm_to_inch(100)     # 100mm frame depth

        half_w = w / 2
        half_h = h / 2

        # Door frame - 4 sides
        # Top frame
        top_pts = [
          Geom::Point3d.new(door_center.x - half_w - frame_thickness, door_center.y, door_center.z),
          Geom::Point3d.new(door_center.x + half_w + frame_thickness, door_center.y, door_center.z),
          Geom::Point3d.new(door_center.x + half_w + frame_thickness, door_center.y + frame_depth, door_center.z),
          Geom::Point3d.new(door_center.x - half_w - frame_thickness, door_center.y + frame_depth, door_center.z),
        ]
        group.entities.add_face(top_pts) if top_pts.all? { |p| p.valid? }

        # Bottom frame (sill)
        bottom_pts = [
          Geom::Point3d.new(door_center.x - half_w - frame_thickness, door_center.y, door_center.z),
          Geom::Point3d.new(door_center.x + half_w + frame_thickness, door_center.y, door_center.z),
          Geom::Point3d.new(door_center.x + half_w + frame_thickness, door_center.y + frame_depth, door_center.z),
          Geom::Point3d.new(door_center.x - half_w - frame_thickness, door_center.y + frame_depth, door_center.z),
        ]
        group.entities.add_face(bottom_pts) if bottom_pts.all? { |p| p.valid? }

        # Left frame
        left_pts = [
          Geom::Point3d.new(door_center.x - half_w - frame_thickness, door_center.y, door_center.z),
          Geom::Point3d.new(door_center.x - half_w, door_center.y, door_center.z),
          Geom::Point3d.new(door_center.x - half_w, door_center.y + frame_depth, door_center.z),
          Geom::Point3d.new(door_center.x - half_w - frame_thickness, door_center.y + frame_depth, door_center.z),
        ]
        group.entities.add_face(left_pts) if left_pts.all? { |p| p.valid? }

        # Right frame
        right_pts = [
          Geom::Point3d.new(door_center.x + half_w, door_center.y, door_center.z),
          Geom::Point3d.new(door_center.x + half_w + frame_thickness, door_center.y, door_center.z),
          Geom::Point3d.new(door_center.x + half_w + frame_thickness, door_center.y + frame_depth, door_center.z),
          Geom::Point3d.new(door_center.x + half_w, door_center.y + frame_depth, door_center.z),
        ]
        group.entities.add_face(right_pts) if right_pts.all? { |p| p.valid? }

        # Create door panel
        create_door_panel(group, door_center, width, height, swing_direction)

        group
      end

      def self.create_door_panel(group, door_center, width, height, swing_direction)
        w = mm_to_inch(width)
        h = mm_to_inch(height)
        panel_thickness = mm_to_inch(40) # 40mm door thickness

        half_w = w / 2

        # Door panel - slightly smaller than opening
        panel_pts = [
          Geom::Point3d.new(door_center.x - half_w + mm_to_inch(10), door_center.y, door_center.z + mm_to_inch(10)),
          Geom::Point3d.new(door_center.x + half_w - mm_to_inch(10), door_center.y, door_center.z + mm_to_inch(10)),
          Geom::Point3d.new(door_center.x + half_w - mm_to_inch(10), door_center.y, door_center.z + h - mm_to_inch(10)),
          Geom::Point3d.new(door_center.x - half_w + mm_to_inch(10), door_center.y, door_center.z + h - mm_to_inch(10)),
        ]

        return unless panel_pts.all? { |p| p.valid? }

        face = group.entities.add_face(panel_pts)
        return unless face

        # Extrude door panel if face was created
        if face.valid?
          # Determine swing direction and create hinge rotation
          # For a left-swing door, hinge is on the left side
          # For a right-swing door, hinge is on the right side
          hinge_edge = if swing_direction == "left"
                         face.edges.find { |e| e.start.position.x < face.bounds.min.x + mm_to_inch(20) }
                       else
                         face.edges.find { |e| e.start.position.x > face.bounds.max.x - mm_to_inch(20) }
                       end

          if hinge_edge
            # Push/pull to create door thickness
            direction = Geom::Vector3d.new(0, 1, 0) # Push outward in Y direction
            face.pushpull(-panel_thickness, false)
          end
        end

        face
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
