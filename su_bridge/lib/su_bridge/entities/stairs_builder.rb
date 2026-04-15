# frozen_string_literal: true

module SuBridge
  module Entities
    # Builds staircases in SketchUp between two levels.
    class StairsBuilder
      # Get Sketchup reference dynamically to avoid constant resolution issues
      def self.sketchup
        ::Object.const_get('Sketchup')
      end

      # Convert mm to inches (SketchUp internal unit)
      def self.mm_to_inch(mm)
        mm.to_f / 25.4
      end

      # Create a staircase between two levels
      # @param start_x [Float] Start X position in mm
      # @param start_y [Float] Start Y position in mm
      # @param start_z [Float] Start Z position (bottom of stairs) in mm
      # @param end_x [Float] End X position in mm
      # @param end_y [Float] End Y position in mm
      # @param end_z [Float] End Z position (top of stairs) in mm
      # @param width [Float] Stair width in mm (default 1000mm)
      # @param num_steps [Integer] Number of steps (calculated from rise if not provided)
      # @return [Hash] Result with entity_ids and spatial_delta
      def self.create(start_x:, start_y:, start_z:, end_x:, end_y:, end_z:, width: 1000, num_steps: nil)
        validate_params!(start_x, start_y, start_z, end_x, end_y, end_z, width)

        # Calculate total rise and run
        total_rise = end_z - start_z
        total_run = Math.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)

        raise ::SuBridge::UndoManager::ValidationError, "Stairs must go up (end_z > start_z)" if total_rise <= 0

        # Calculate steps
        if num_steps.nil? || num_steps <= 0
          # Default step rise is around 175mm (residential standard)
          default_step_rise = 175
          num_steps = (total_rise / default_step_rise).ceil
          num_steps = [num_steps, 3].max # Minimum 3 steps
        end

        # Calculate actual step dimensions
        step_rise = total_rise.to_f / num_steps
        step_run = total_run.to_f / num_steps

        # Direction vector for stairs
        run_direction_x = num_steps > 0 ? (end_x - start_x) / num_steps : 0
        run_direction_y = num_steps > 0 ? (end_y - start_y) / num_steps : 0

        # Create stairs group
        stairs_group = create_stairs_group(
          start_x, start_y, start_z,
          run_direction_x, run_direction_y, step_rise,
          step_run, width, num_steps
        )

        # Get all entity IDs created
        entity_ids = collect_entity_ids(stairs_group)

        {
          entity_ids: entity_ids,
          spatial_delta: spatial_delta(stairs_group),
          model_revision: 1,
          elapsed_ms: 0,
          stairs_info: {
            num_steps: num_steps,
            total_rise: total_rise,
            total_run: total_run.round(2),
            step_rise: step_rise.round(2),
            step_run: step_run.round(2),
          },
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

      def self.validate_params!(start_x, start_y, start_z, end_x, end_y, end_z, width)
        raise ::SuBridge::UndoManager::ValidationError, "start_x required" unless start_x
        raise ::SuBridge::UndoManager::ValidationError, "start_y required" unless start_y
        raise ::SuBridge::UndoManager::ValidationError, "start_z required" unless start_z
        raise ::SuBridge::UndoManager::ValidationError, "end_x required" unless end_x
        raise ::SuBridge::UndoManager::ValidationError, "end_y required" unless end_y
        raise ::SuBridge::UndoManager::ValidationError, "end_z required" unless end_z
        raise ::SuBridge::UndoManager::ValidationError, "width must be positive" unless width && width > 0
      end

      def self.create_stairs_group(start_x, start_y, start_z, run_dx, run_dy, step_rise, step_run, width, num_steps)
        model = sketchup.active_model
        group = model.entities.add_group

        w = mm_to_inch(width)
        half_w = w / 2

        # Create each step
        num_steps.times do |i|
          step_z_bottom = start_z + (i * step_rise)
          step_z_top = step_z_bottom + step_rise

          step_x_start = start_x + (i * run_dx)
          step_y_start = start_y + (i * run_dy)
          step_x_end = step_x_start + run_dx
          step_y_end = step_y_start + run_dy

          # Create step tread (horizontal face)
          create_step_tread(group, step_x_start, step_y_start, step_z_bottom, step_x_end, step_y_end, step_z_bottom, w, step_run, i)

          # Create step riser (vertical face) - except for last step
          if i < num_steps - 1
            create_step_riser(group, step_x_end, step_y_end, step_z_bottom, step_x_end, step_y_end, step_z_top, w, step_rise, i)
          end
        end

        # Create final tread at top
        final_step_z = start_z + (num_steps * step_rise)
        final_x = start_x + (num_steps * run_dx)
        final_y = start_y + (num_steps * run_dy)
        create_step_tread(group, final_x, final_y, final_step_z, final_x, final_y, final_step_z, w, mm_to_inch(step_run), num_steps)

        # Add stringers (side supports)
        create_stringers(group, start_x, start_y, start_z, run_dx, run_dy, step_rise, step_run, width, num_steps)

        # Add optional handrail
        create_handrail(group, start_x, start_y, start_z, run_dx, run_dy, step_rise, step_run, width, num_steps)

        group
      end

      def self.create_step_tread(group, x1, y1, z1, x2, y2, z2, width, depth, step_index)
        # Tread is the horizontal walking surface
        # Create as a rectangle in the XY plane at height z1
        half_w = width / 2

        # The tread extends from the current step to the next
        pts = [
          Geom::Point3d.new(mm_to_inch(x1 - half_w), mm_to_inch(y1), mm_to_inch(z1)),
          Geom::Point3d.new(mm_to_inch(x1 + half_w), mm_to_inch(y1), mm_to_inch(z1)),
          Geom::Point3d.new(mm_to_inch(x2 + half_w), mm_to_inch(y2), mm_to_inch(z2)),
          Geom::Point3d.new(mm_to_inch(x2 - half_w), mm_to_inch(y2), mm_to_inch(z2)),
        ]

        return unless pts.all? { |p| p.valid? }

        face = group.entities.add_face(pts)
        face.reverse! if face.normal.z < 0 # Ensure face points up
        face
      end

      def self.create_step_riser(group, x, y, z_bottom, x_end, y_end, z_top, width, height, step_index)
        # Riser is the vertical face at the back of each step
        half_w = width / 2

        pts = [
          Geom::Point3d.new(mm_to_inch(x - half_w), mm_to_inch(y), mm_to_inch(z_bottom)),
          Geom::Point3d.new(mm_to_inch(x + half_w), mm_to_inch(y), mm_to_inch(z_bottom)),
          Geom::Point3d.new(mm_to_inch(x_end + half_w), mm_to_inch(y_end), mm_to_inch(z_top)),
          Geom::Point3d.new(mm_to_inch(x_end - half_w), mm_to_inch(y_end), mm_to_inch(z_top)),
        ]

        return unless pts.all? { |p| p.valid? }

        face = group.entities.add_face(pts)
        face
      end

      def self.create_stringers(group, start_x, start_y, start_z, run_dx, run_dy, step_rise, step_run, width, num_steps)
        # Stringers are the diagonal side supports
        w = mm_to_inch(width)
        half_w = w / 2

        stringer_thickness = mm_to_inch(40) # 40mm stringer thickness

        num_steps.times do |i|
          step_z = start_z + (i * step_rise)
          next_step_z = step_z + step_rise
          step_x = start_x + (i * run_dx)
          step_y = start_y + (i * run_dy)
          next_step_x = step_x + run_dx
          next_step_y = step_y + run_dy

          # Left stringer
          left_stringer_pts = [
            Geom::Point3d.new(mm_to_inch(step_x - half_w), mm_to_inch(step_y), mm_to_inch(step_z)),
            Geom::Point3d.new(mm_to_inch(next_step_x - half_w), mm_to_inch(next_step_y), mm_to_inch(next_step_z)),
            Geom::Point3d.new(mm_to_inch(next_step_x - half_w), mm_to_inch(next_step_y), mm_to_inch(next_step_z + 100)), # Height of stringer
            Geom::Point3d.new(mm_to_inch(step_x - half_w), mm_to_inch(step_y), mm_to_inch(step_z + 100)),
          ]
          group.entities.add_face(left_stringer_pts) if left_stringer_pts.all? { |p| p.valid? }

          # Right stringer
          right_stringer_pts = [
            Geom::Point3d.new(mm_to_inch(step_x + half_w), mm_to_inch(step_y), mm_to_inch(step_z)),
            Geom::Point3d.new(mm_to_inch(next_step_x + half_w), mm_to_inch(next_step_y), mm_to_inch(next_step_z)),
            Geom::Point3d.new(mm_to_inch(next_step_x + half_w), mm_to_inch(next_step_y), mm_to_inch(next_step_z + 100)),
            Geom::Point3d.new(mm_to_inch(step_x + half_w), mm_to_inch(step_y), mm_to_inch(step_z + 100)),
          ]
          group.entities.add_face(right_stringer_pts) if right_stringer_pts.all? { |p| p.valid? }
        end
      end

      def self.create_handrail(group, start_x, start_y, start_z, run_dx, run_dy, step_rise, step_run, width, num_steps)
        # Handrail runs along the stairs at a comfortable height (around 900mm above tread)
        w = mm_to_inch(width)
        half_w = w / 2
        handrail_height = mm_to_inch(900)
        handrail_radius = mm_to_inch(25) # 25mm radius

        # Handrail position - along the left side
        handrail_x = start_x - half_w - mm_to_inch(50) # 50mm inset from stringer
        handrail_y = start_y

        # Calculate handrail path
        total_rise = num_steps * step_rise
        total_run = num_steps * step_run

        # Handrail follows the slope of the stairs
        handrail_pts = []
        (num_steps + 1).times do |i|
          x = start_x + (i * run_dx) - half_w - mm_to_inch(50)
          y = start_y + (i * run_dy)
          z = start_z + (i * step_rise) + handrail_height
          handrail_pts << Geom::Point3d.new(mm_to_inch(x), mm_to_inch(y), mm_to_inch(z))
        end

        return unless handrail_pts.length >= 2

        # Create handrail as a cylinder (circle profile swept along path)
        # For simplicity, create it as a series of faces forming a box rail
        rail_width = mm_to_inch(50)
        rail_height = mm_to_inch(25)

        handrail_pts.each_cons(2) do |p1, p2|
          direction = p2 - p1
          next if direction.length < 0.001

          # Create a simple box rail segment
          offset = Geom::Vector3d.new(0, 0, rail_height / 2)

          rail_pts = [
            p1 - offset,
            p1 + Geom::Vector3d.new(rail_width, 0, 0) - offset,
            p2 + Geom::Vector3d.new(rail_width, 0, 0) - offset,
            p2 - offset,
          ]
          group.entities.add_face(rail_pts) if rail_pts.all? { |p| p.valid? }
        end
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
