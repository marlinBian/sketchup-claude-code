# frozen_string_literal: true

module SuBridge
  module Entities
    # Builds faces and meshes in SketchUp.
    class FaceBuilder
      # Get Sketchup reference dynamically to avoid constant resolution issues
      def self.sketchup
        ::Object.const_get('Sketchup')
      end

      # Convert mm to inches (SketchUp internal unit)
      def self.mm_to_inch(mm)
        mm.to_f / 25.4
      end

      def self.create_from_vertices(vertices, options = {})
        points = vertices.map { |v| Geom::Point3d.new(mm_to_inch(v[0]), mm_to_inch(v[1]), mm_to_inch(v[2])) }
        raise ValidationError, "Need at least 3 vertices" if points.length < 3

        # Check if points are collinear
        if collinear?(points)
          raise ValidationError, "Points are collinear"
        end

        face = sketchup.active_model.entities.add_face(points)

        apply_layer(face, options["layer"]) if options["layer"]
        apply_material(face, options["material_id"]) if options["material_id"]

        face
      end

      def self.create_box(corner, width, depth, height, options = {})
        raise ValidationError, "All dimensions must be positive" if width <= 0 || depth <= 0 || height <= 0

        x, y, z = corner

        # Create 8 corners of the box (convert mm to inches for SketchUp)
        pts = [
          Geom::Point3d.new(mm_to_inch(x), mm_to_inch(y), mm_to_inch(z)),
          Geom::Point3d.new(mm_to_inch(x + width), mm_to_inch(y), mm_to_inch(z)),
          Geom::Point3d.new(mm_to_inch(x + width), mm_to_inch(y + depth), mm_to_inch(z)),
          Geom::Point3d.new(mm_to_inch(x), mm_to_inch(y + depth), mm_to_inch(z)),
          Geom::Point3d.new(mm_to_inch(x), mm_to_inch(y), mm_to_inch(z + height)),
          Geom::Point3d.new(mm_to_inch(x + width), mm_to_inch(y), mm_to_inch(z + height)),
          Geom::Point3d.new(mm_to_inch(x + width), mm_to_inch(y + depth), mm_to_inch(z + height)),
          Geom::Point3d.new(mm_to_inch(x), mm_to_inch(y + depth), mm_to_inch(z + height)),
        ]

        # Create box as a group of faces
        model = sketchup.active_model
        group = model.entities.add_group

        # Bottom face
        group.entities.add_face(pts[0], pts[1], pts[2], pts[3])
        # Top face
        group.entities.add_face(pts[4], pts[5], pts[6], pts[7])
        # Front face
        group.entities.add_face(pts[0], pts[1], pts[5], pts[4])
        # Back face
        group.entities.add_face(pts[2], pts[3], pts[7], pts[6])
        # Left face
        group.entities.add_face(pts[0], pts[3], pts[7], pts[4])
        # Right face
        group.entities.add_face(pts[1], pts[2], pts[6], pts[5])

        apply_layer(group, options["layer"]) if options["layer"]
        apply_material(group, options["material_id"]) if options["material_id"]

        group
      end

      def self.spatial_delta(entity)
        bbox = entity.bounds
        {
          bounding_box: {
            min: [bbox.min.x.to_mm, bbox.min.y.to_mm, bbox.min.z.to_mm],
            max: [bbox.max.x.to_mm, bbox.max.y.to_mm, bbox.max.z.to_mm],
          },
          volume_mm3: calculate_volume(entity),
        }
      end

      def self.apply_layer(entity, layer_name)
        layer = sketchup.active_model.layers[layer_name]
        layer ||= sketchup.active_model.layers.add(layer_name)
        entity.layer = layer
      end

      def self.apply_material(entity, material_id)
        # Material resolution would happen here
        # For now, materials are looked up by ID
      end

      private

      def self.collinear?(points)
        return false if points.length < 3

        # Check if all points lie on the same line using cross product
        p1, p2, p3 = points[0], points[1], points[2]
        v1 = p2 - p1
        v2 = p3 - p1

        cross = v1.cross(v2)
        cross.length < 0.0001
      end

      def self.calculate_volume(entity)
        # Simplified - would use actual mesh volume calculation
        bbox = entity.bounds
        # Convert from inches to mm (SketchUp internal units)
        bbox.width.to_mm * bbox.depth.to_mm * bbox.height.to_mm
      end
    end
  end
end
