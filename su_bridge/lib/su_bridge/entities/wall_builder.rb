# frozen_string_literal: true

require "matrix"

module SuBridge
  module Entities
    # Builds walls in SketchUp with alignment support.
    class WallBuilder
      # Get Sketchup reference dynamically to avoid constant resolution issues
      def self.sketchup
        ::Object.const_get('Sketchup')
      end

      # Convert mm to inches (SketchUp internal unit)
      def self.mm_to_inch(mm)
        mm.to_f / 25.4
      end

      ALIGNMENT_MODES = ["center", "inner", "outer"].freeze

      def self.create(start:, end_point:, height:, thickness:, alignment: "center", options: {})
        validate_params!(start, end_point, height, thickness, alignment)

        vertices = calculate_vertices(start, end_point, height, thickness, alignment)

        # Create the wall as a group of faces
        wall_group = create_wall_group(vertices, options)

        wall_group
      end

      def self.calculate_vertices(start, end_point, height, thickness, alignment)
        p1 = Vector3d.new(*start)
        p2 = Vector3d.new(*end_point)

        # Direction vector along wall
        direction = p2 - p1
        length = direction.r
        raise ::SuBridge::UndoManager::ValidationError, "Wall length must be > 0" if length < 1

        direction = direction / length  # Normalize

        # Perpendicular normal (Z-up, points left of wall direction)
        # N = [-dy, dx, 0]
        normal = Vector3d.new(-direction[1], direction[0], 0)

        # Calculate offset based on alignment
        offset = case alignment
                when "center" then thickness / 2.0
                when "inner" then thickness.to_f
                when "outer" then 0.0
                else thickness / 2.0
                end

        # Calculate the 4 bottom vertices
        offset_vec = normal * offset

        v1 = p1 + offset_vec                    # bottom-left at start
        v2 = p1 - normal * (thickness - offset)  # bottom-right at start
        v3 = p2 - normal * (thickness - offset)  # bottom-right at end
        v4 = p2 + offset_vec                    # bottom-left at end

        # Extrude up by height
        height_vec = Vector3d.new(0, 0, height)
        v5 = v1 + height_vec  # top-left at start
        v6 = v2 + height_vec  # top-right at start
        v7 = v3 + height_vec  # top-right at end
        v8 = v4 + height_vec  # top-left at end

        [v1.to_a, v2.to_a, v3.to_a, v4.to_a, v5.to_a, v6.to_a, v7.to_a, v8.to_a]
      end

      def self.create_wall_group(vertices, options)
        model = sketchup.active_model
        entities = model.entities

        # Convert mm to inches for SketchUp (SketchUp uses inches internally)
        pts = vertices.map { |v| Geom::Point3d.new(mm_to_inch(v[0]), mm_to_inch(v[1]), mm_to_inch(v[2])) }

        # Create empty group first, then add faces to group's entities
        group = entities.add_group

        # Add faces using add_face - SketchUp determines front/back automatically.
        # add_face flips the face if needed to face the camera or match adjacent geometry.
        # No manual reverse needed.

        # Bottom face (at z=0)
        group.entities.add_face(pts[0], pts[1], pts[2], pts[3])
        # Top face (at height)
        group.entities.add_face(pts[4], pts[5], pts[6], pts[7])
        # Left face (x=0, facing -X)
        group.entities.add_face(pts[0], pts[4], pts[5], pts[1])
        # Right face (x=end, facing +X)
        group.entities.add_face(pts[3], pts[7], pts[6], pts[2])
        # Front face (y=start, facing -Y)
        group.entities.add_face(pts[1], pts[2], pts[6], pts[5])
        # Back face (y=end, facing +Y)
        group.entities.add_face(pts[0], pts[3], pts[7], pts[4])

        # Apply layer if specified
        if options["layer"]
          apply_layer(group, options["layer"])
        end

        # Apply material if specified
        if options["material_id"]
          apply_material(group, options["material_id"])
        end

        group
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

      def self.apply_layer(entity, layer_name)
        layer = sketchup.active_model.layers[layer_name]
        layer ||= sketchup.active_model.layers.add(layer_name)
        entity.layer = layer
      end

      def self.apply_material(entity, material_id)
        # Material resolution would look up by ID
      end

      private

      def self.validate_params!(start, end_point, height, thickness, alignment)
        raise ::SuBridge::UndoManager::ValidationError, "start point required" unless start
        raise ::SuBridge::UndoManager::ValidationError, "end point required" unless end_point
        raise ::SuBridge::UndoManager::ValidationError, "height must be positive" unless height && height > 0
        raise ::SuBridge::UndoManager::ValidationError, "thickness must be positive" unless thickness && thickness > 0
        raise ::SuBridge::UndoManager::ValidationError, "invalid alignment" unless ALIGNMENT_MODES.include?(alignment)

        # Check start != end
        if start[0] == end_point[0] && start[1] == end_point[1] && start[2] == end_point[2]
          raise ::SuBridge::UndoManager::ValidationError, "start and end must be different points"
        end
      end

      def self.calculate_volume(group)
        bbox = group.bounds
        # Convert from inches to mm (SketchUp internal units)
        bbox.width.to_mm * bbox.depth.to_mm * bbox.height.to_mm
      end

      # Simple 3D vector class for calculations
      class Vector3d
        attr_reader :x, :y, :z

        def initialize(x, y, z)
          @x = x.to_f
          @y = y.to_f
          @z = z.to_f
        end

        def -(other)
          Vector3d.new(@x - other.x, @y - other.y, @z - other.z)
        end

        def +(other)
          Vector3d.new(@x + other.x, @y + other.y, @z + other.z)
        end

        def *(scalar)
          Vector3d.new(@x * scalar, @y * scalar, @z * scalar)
        end

        def /(scalar)
          Vector3d.new(@x / scalar, @y / scalar, @z / scalar)
        end

        def dot(other)
          @x * other.x + @y * other.y + @z * other.z
        end

        def cross(other)
          Vector3d.new(
            @y * other.z - @z * other.y,
            @z * other.x - @x * other.z,
            @x * other.y - @y * other.x
          )
        end

        def r
          Math.sqrt(@x * @x + @y * @y + @z * @z)
        end

        def to_a
          [@x, @y, @z]
        end

        def [](index)
          to_a[index]
        end
      end
    end
  end
end