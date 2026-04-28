# frozen_string_literal: true

require "securerandom"
require "set"

module SuBridge
  # Routes JSON-RPC requests to appropriate Ruby API handlers.
  class CommandDispatcher
    # Operations that modify entity geometry and should trigger sync
    ENTITY_MODIFYING_OPERATIONS = Set.new(%w[
      create_face create_box create_wall create_group
      create_door create_window create_stairs
      move_entity rotate_entity scale_entity
      delete_entity
    ]).freeze

    OPERATION_HANDLERS = {
      "create_face" => :handle_create_face,
      "create_box" => :handle_create_box,
      "create_wall" => :handle_create_wall,
      "create_group" => :handle_create_group,
      "create_door" => :handle_create_door,
      "create_window" => :handle_create_window,
      "create_stairs" => :handle_create_stairs,
      "delete_entity" => :handle_delete_entity,
      "set_material" => :handle_set_material,
      "apply_material" => :handle_apply_material,
      "apply_style" => :handle_apply_style,
      "query_entities" => :handle_query_entities,
      "query_model_info" => :handle_query_model_info,
      "get_scene_info" => :handle_get_scene_info,
      "move_entity" => :handle_move_entity,
      "rotate_entity" => :handle_rotate_entity,
      "scale_entity" => :handle_scale_entity,
      "copy_entity" => :handle_copy_entity,
      "place_component" => :handle_place_component,
      "place_lighting" => :handle_place_lighting,
      "set_camera_view" => :handle_set_camera_view,
      "capture_design" => :handle_capture_design,
      "cleanup_model" => :handle_cleanup_model,
      "export_gltf" => :handle_export_gltf,
      "export_ifc" => :handle_export_ifc,
    }.freeze

    # Public dispatch for JSON-RPC requests
    def dispatch(request)
      method = request.dig("method")
      params = request.dig("params") || {}
      id = request["id"]

      if method == "execute_operation"
        dispatch_operation(
          params["operation_id"] || "op_#{SecureRandom.hex(4)}",
          params["operation_type"],
          params["payload"] || {},
          params.fetch("rollback_on_failure", true)
        )
      else
        SuBridge::JsonRpcHandler.error_response(
          -32000,
          "Unknown method: #{method}",
          id
        )
      end
    end

    # Public dispatch for operation with individual parameters
    def dispatch_operation(operation_id, operation_type, payload, rollback_on_failure = true)
      start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)

      handler = OPERATION_HANDLERS[operation_type]
      unless handler
        return SuBridge::JsonRpcHandler.error_response(
          -32000,
          "Unknown operation_type: #{operation_type}",
          nil,
          { operation_id: operation_id }
        )
      end

      result = UndoManager.with_transaction(
        name: operation_type,
        rollback_on_failure: rollback_on_failure
      ) do
        send(handler, payload)
      end

      elapsed_ms = ((Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time) * 1000).round

      # Trigger design model sync for entity-modifying operations
      sync_design_model(operation_type, result[:entity_ids] || [])

      # Merge handler result with standard fields
      {
        operation_id: operation_id,
        status: "success",
        entity_ids: result[:entity_ids] || [],
        spatial_delta: result[:spatial_delta] || {},
        model_revision: result[:model_revision] || 1,
        elapsed_ms: elapsed_ms,
      }.merge(result.reject { |k| [:entity_ids, :spatial_delta, :model_revision, :elapsed_ms].include?(k) })
    rescue => e
      rollback_status = rollback_on_failure ? "completed" : "skipped"
      elapsed_ms = ((Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time) * 1000).round

      SuBridge::JsonRpcHandler.error_response(
        error_code_for(e),
        e.message,
        nil,
        {
          operation_id: operation_id,
          rollback_status: rollback_status,
          model_revision: 1,
          elapsed_ms: elapsed_ms,
        }
      )
    end

    private

    # Trigger design model sync after entity-modifying operations
    # @param operation_type [String] The operation type (e.g., "create_wall")
    # @param entity_ids [Array<String>] Entity IDs that were modified
    def sync_design_model(operation_type, entity_ids = [])
      return unless ENTITY_MODIFYING_OPERATIONS.include?(operation_type)

      sync = SuBridge.design_sync
      return unless sync

      case operation_type
      when "delete_entity"
        entity_ids.each do |eid|
          # Extract numeric ID from entity ID string
          numeric_id = eid.to_s.gsub("entity_", "").to_i
          sync.remove_entity(numeric_id) if numeric_id > 0
        end
      when "move_entity", "rotate_entity", "scale_entity"
        # For transform operations, we need to update the entity positions
        # The EntityObserver will handle this via onEntityChange
        # But we can also do an immediate sync for reliability
        entity_ids.each do |eid|
          numeric_id = eid.to_s.gsub("entity_", "").to_i
          entity = find_entity_by_id(numeric_id) if numeric_id > 0
          if entity
            trans = entity.transformation
            position = trans ? trans.origin.to_a : [0, 0, 0]
            # Convert from inches to mm
            position_mm = position.map { |v| (v * 25.4).round(2) }
            sync.update_entity_position(numeric_id, position_mm)
          end
        end
      else
        # For create operations, sync the entire model to capture new entities
        sync.sync_to_file!
      end
    rescue => e
      puts "[SuBridge] Sync failed: #{e.message}"
    end

    # Find entity by numeric ID
    # @param entity_id [Integer] Numeric entity ID
    # @return [Sketchup::Entity, nil] The entity or nil if not found
    def find_entity_by_id(entity_id)
      model = sketchup.active_model
      return nil unless model

      model.entities.find { |e| e.entityID == entity_id }
    end

    # Get Sketchup reference dynamically to avoid constant resolution issues
    def sketchup
      ::Object.const_get('Sketchup')
    end

    def error_code_for(exception)
      if exception.is_a?(SuBridge::UndoManager::ValidationError)
        -32001
      elsif exception.is_a?(SuBridge::UndoManager::EntityNotFoundError)
        -32004
      elsif exception.is_a?(SuBridge::UndoManager::PermissionError)
        -32005
      elsif exception.is_a?(SuBridge::UndoManager::RollbackError)
        -32002
      else
        -32000
      end
    end

    def handle_create_face(payload)
      vertices = payload["vertices"]
      raise ::SuBridge::UndoManager::ValidationError, "vertices required" unless vertices

      face = SuBridge::Entities::FaceBuilder.create_from_vertices(vertices, payload)
      {
        entity_ids: [face.entityID.to_s],
        spatial_delta: SuBridge::Entities::FaceBuilder.spatial_delta(face),
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_create_box(payload)
      corner = payload["corner"]
      width = payload["width"]
      depth = payload["depth"]
      height = payload["height"]

      raise ::SuBridge::UndoManager::ValidationError, "corner required" unless corner
      raise ::SuBridge::UndoManager::ValidationError, "width required" unless width
      raise ::SuBridge::UndoManager::ValidationError, "depth required" unless depth
      raise ::SuBridge::UndoManager::ValidationError, "height required" unless height

      box = SuBridge::Entities::FaceBuilder.create_box(corner, width, depth, height, payload)
      {
        entity_ids: [box.entityID.to_s],
        spatial_delta: SuBridge::Entities::FaceBuilder.spatial_delta(box),
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_create_wall(payload)
      start = payload["start"]
      end_point = payload["end"]
      height = payload["height"]
      thickness = payload["thickness"]
      alignment = payload.fetch("alignment", "center")

      raise ::SuBridge::UndoManager::ValidationError, "start required" unless start
      raise ::SuBridge::UndoManager::ValidationError, "end required" unless end_point
      raise ::SuBridge::UndoManager::ValidationError, "height required" unless height
      raise ::SuBridge::UndoManager::ValidationError, "thickness required" unless thickness

      wall = SuBridge::Entities::WallBuilder.create(
        start: start,
        end_point: end_point,
        height: height,
        thickness: thickness,
        alignment: alignment,
        options: payload
      )

      {
        entity_ids: [wall.entityID.to_s],
        spatial_delta: SuBridge::Entities::WallBuilder.spatial_delta(wall),
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_get_scene_info(payload)
      model = sketchup.active_model
      bbox = model.bounds

      # Count entities by type
      entity_counts = {
        "faces" => 0,
        "edges" => 0,
        "groups" => 0,
        "components" => 0,
      }

      model.entities.each do |entity|
        case entity
        when sketchup.const_get("Face") then entity_counts["faces"] += 1
        when sketchup.const_get("Edge") then entity_counts["edges"] += 1
        when sketchup.const_get("Group") then entity_counts["groups"] += 1
        when sketchup.const_get("ComponentInstance") then entity_counts["components"] += 1
        end
      end

      # Get layer names
      layers = model.layers.map(&:name)

      {
        entity_ids: [],
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
        scene_info: {
          bounding_box: {
            min: [bbox.min.x, bbox.min.y, bbox.min.z],
            max: [bbox.max.x, bbox.max.y, bbox.max.z],
          },
          entity_counts: entity_counts,
          layers: layers,
        },
      }
    end

    def handle_place_component(payload)
      skp_path = payload["skp_path"]
      position = payload["position"]
      rotation = payload.fetch("rotation", 0.0)
      scale = payload.fetch("scale", 1.0)
      component_id = payload["component_id"]
      instance_id = payload["instance_id"]
      procedural_fallback = payload["procedural_fallback"]
      dimensions = payload["dimensions"]
      layer = payload["layer"]
      name = payload["name"]

      raise ::SuBridge::UndoManager::ValidationError, "skp_path required" unless skp_path
      raise ::SuBridge::UndoManager::ValidationError, "position required" unless position

      result = SuBridge::Entities::ComponentManager.place(
        skp_path: skp_path,
        position: position,
        rotation: rotation,
        scale: scale,
        component_id: component_id,
        instance_id: instance_id,
        procedural_fallback: procedural_fallback,
        dimensions: dimensions,
        layer: layer,
        name: name
      )

      spatial_delta = result[:spatial_delta]
      unless spatial_delta
        entity = sketchup.active_model.entities.find { |e| e.entityID.to_s == result[:entity_id] }
        spatial_delta = SuBridge::Entities::ComponentManager.spatial_delta(entity)
      end

      {
        entity_ids: [result[:entity_id]],
        spatial_delta: spatial_delta,
        model_revision: 1,
        elapsed_ms: 0,
        placement_info: {
          definition_name: result[:definition_name],
          component_id: component_id,
          instance_id: instance_id,
          fallback_used: result[:fallback_used] || false,
          fallback_reason: result[:fallback_reason],
          bounds: result[:bounds],
        },
      }
    end

    def handle_apply_material(payload)
      entity_ids = payload["entity_ids"]
      material_id = payload["material_id"]
      color = payload["color"]
      texture_scale = payload["texture_scale"]

      raise ::SuBridge::UndoManager::ValidationError, "entity_ids required" unless entity_ids

      result = SuBridge::Entities::MaterialApplier.apply(
        entity_ids,
        material_id: material_id,
        color: color,
        texture_scale: texture_scale
      )

      {
        entity_ids: entity_ids,
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
        material_info: result,
      }
    end

    def handle_apply_style(payload)
      style_name = payload["style_name"]
      entity_ids = payload["entity_ids"]

      raise ::SuBridge::UndoManager::ValidationError, "style_name required" unless style_name

      result = SuBridge::Entities::MaterialApplier.apply_style(
        style_name,
        entity_ids: entity_ids
      )

      {
        entity_ids: entity_ids || [],
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
        style_info: {
          style_name: style_name,
          applied_count: result.length,
          applications: result,
        },
      }
    rescue SuBridge::Entities::MaterialApplier::ValidationError => e
      raise ::SuBridge::UndoManager::ValidationError, e.message
    end

    def handle_place_lighting(payload)
      lighting_type = payload["lighting_type"]
      position = payload["position"]
      ceiling_height = payload["ceiling_height"]
      mount_height = payload["mount_height"]

      raise ::SuBridge::UndoManager::ValidationError, "lighting_type required" unless lighting_type
      raise ::SuBridge::UndoManager::ValidationError, "position required" unless position

      final_position = case lighting_type
                       when "spotlight"
                         [position[0], position[1], ceiling_height || 2400]
                       when "chandelier"
                         [position[0], position[1], mount_height || 2000]
                       when "floor_lamp"
                         [position[0], position[1], 0]
                       else
                         position
                       end

      result = SuBridge::Entities::ComponentManager.place(
        skp_path: "${SKETCHUP_ASSETS}/lighting/#{lighting_type}.skp",
        position: final_position,
        rotation: payload.fetch("rotation", 0),
        scale: payload.fetch("scale", 1),
        component_id: "lighting_#{lighting_type}"
      )

      {
        entity_ids: [result[:entity_id]],
        spatial_delta: SuBridge::Entities::ComponentManager.spatial_delta(
          sketchup.active_model.entities.find { |e| e.entityID.to_s == result[:entity_id] }
        ),
        model_revision: 1,
        elapsed_ms: 0,
        placement_info: { lighting_type: lighting_type, final_position: final_position },
      }
    end

    def handle_set_camera_view(payload)
      view_preset = payload["view_preset"]
      eye = payload["eye"]
      target = payload["target"]
      up = payload["up"]

      view = sketchup.active_model.active_view

      case view_preset
      when "panoramic"
        set_camera_position(view, [0, 0, 1500], [5000, 0, 1000], [0, 0, 1])
      when "living_room_birdseye"
        set_camera_position(view, [2500, -3000, 4000], [2500, 2500, 800], [0, 0, 1])
      when "master_bedroom"
        set_camera_position(view, [2000, 3000, 1200], [4000, 2000, 1000], [0, 0, 1])
      when "dining_area"
        set_camera_position(view, [1600, 1000, 1500], [1600, 4000, 800], [0, 0, 1])
      when "front_entrance"
        set_camera_position(view, [0, -2000, 1600], [2000, 3000, 800], [0, 0, 1])
      else
        if eye && target
          set_camera_position(view, eye, target, up || [0, 0, 1])
        else
          raise ::SuBridge::UndoManager::ValidationError, "Invalid camera parameters"
        end
      end

      {
        entity_ids: [],
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
        view_info: { preset: view_preset, camera_eye: view.camera.eye.to_a, camera_target: view.camera.target.to_a },
      }
    end

    def set_camera_position(view, eye, target, up)
      view.camera.set(Geom::Point3d.new(*eye), Geom::Point3d.new(*target), Geom::Vector3d.new(*up))
    end

    def handle_capture_design(payload)
      output_path = payload["output_path"]
      view_preset = payload["view_preset"]
      width = payload.fetch("width", 1920)
      height = payload.fetch("height", 1080)

      raise ::SuBridge::UndoManager::ValidationError, "output_path required" unless output_path

      view = sketchup.active_model.active_view

      if view_preset
        handle_set_camera_view({ "view_preset" => view_preset })
      end

      view.write_image(filename: output_path, width: width, height: height, antialias: true, compression: 0.8, transparent: false)

      {
        entity_ids: [],
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
        capture_info: { output_path: output_path, width: width, height: height, view_preset: view_preset },
      }
    rescue => e
      raise ::SuBridge::UndoManager::ValidationError, "Capture failed: #{e.message}"
    end

    def handle_cleanup_model(payload)
      layer_names = payload["layer_names"]
      tag = payload["tag"]

      if tag
        result = EntityManager.cleanup_by_tag(tag)
      else
        result = EntityManager.delete_all(layer_names: layer_names)
      end

      {
        entity_ids: result[:deleted_ids] || [],
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
        cleanup_info: {
          deleted_count: result[:deleted_count],
          layers_cleaned: result[:layers_cleaned] || [],
          tag: result[:tag],
        },
      }
    end

    def handle_create_group(payload)
      entity_ids = payload["entity_ids"]
      raise ::SuBridge::UndoManager::ValidationError, "entity_ids required" unless entity_ids

      group = SuBridge::Entities::GroupBuilder.create(entity_ids, payload["name"])
      {
        entity_ids: [group.entityID.to_s],
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_create_door(payload)
      wall_id = payload["wall_id"]
      position_x = payload["position_x"]
      position_y = payload.fetch("position_y", 0)
      width = payload.fetch("width", 900)
      height = payload.fetch("height", 2100)
      swing_direction = payload.fetch("swing_direction", "left")

      raise ::SuBridge::UndoManager::ValidationError, "wall_id required" unless wall_id
      raise ::SuBridge::UndoManager::ValidationError, "position_x required" unless position_x

      result = SuBridge::Entities::DoorBuilder.create(
        wall_id: wall_id,
        position_x: position_x,
        position_y: position_y,
        width: width,
        height: height,
        swing_direction: swing_direction
      )

      {
        entity_ids: result[:entity_ids],
        spatial_delta: result[:spatial_delta],
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_create_window(payload)
      wall_id = payload["wall_id"]
      position_x = payload["position_x"]
      position_y = payload.fetch("position_y", 0)
      width = payload.fetch("width", 1200)
      height = payload.fetch("height", 1000)
      sill_height = payload.fetch("sill_height", 900)

      raise ::SuBridge::UndoManager::ValidationError, "wall_id required" unless wall_id
      raise ::SuBridge::UndoManager::ValidationError, "position_x required" unless position_x

      result = SuBridge::Entities::WindowBuilder.create(
        wall_id: wall_id,
        position_x: position_x,
        position_y: position_y,
        width: width,
        height: height,
        sill_height: sill_height
      )

      {
        entity_ids: result[:entity_ids],
        spatial_delta: result[:spatial_delta],
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_create_stairs(payload)
      start_x = payload["start_x"]
      start_y = payload["start_y"]
      start_z = payload["start_z"]
      end_x = payload["end_x"]
      end_y = payload["end_y"]
      end_z = payload["end_z"]
      width = payload.fetch("width", 1000)
      num_steps = payload["num_steps"]

      raise ::SuBridge::UndoManager::ValidationError, "start_x required" unless start_x
      raise ::SuBridge::UndoManager::ValidationError, "start_y required" unless start_y
      raise ::SuBridge::UndoManager::ValidationError, "start_z required" unless start_z
      raise ::SuBridge::UndoManager::ValidationError, "end_x required" unless end_x
      raise ::SuBridge::UndoManager::ValidationError, "end_y required" unless end_y
      raise ::SuBridge::UndoManager::ValidationError, "end_z required" unless end_z

      result = SuBridge::Entities::StairsBuilder.create(
        start_x: start_x,
        start_y: start_y,
        start_z: start_z,
        end_x: end_x,
        end_y: end_y,
        end_z: end_z,
        width: width,
        num_steps: num_steps
      )

      {
        entity_ids: result[:entity_ids],
        spatial_delta: result[:spatial_delta],
        model_revision: 1,
        elapsed_ms: 0,
        stairs_info: result[:stairs_info],
      }
    end

    def handle_delete_entity(payload)
      entity_ids = payload["entity_ids"]
      raise ::SuBridge::UndoManager::ValidationError, "entity_ids required" unless entity_ids

      deleted = EntityManager.delete(entity_ids)
      {
        entity_ids: deleted,
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_set_material(payload)
      entity_ids = payload["entity_ids"]
      material_id = payload["material_id"]

      raise ::SuBridge::UndoManager::ValidationError, "entity_ids required" unless entity_ids
      raise ::SuBridge::UndoManager::ValidationError, "material_id required" unless material_id

      SuBridge::Entities::MaterialApplier.apply(entity_ids, material_id)
      {
        entity_ids: entity_ids,
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_query_entities(payload)
      entity_type = payload["entity_type"]
      layer = payload["layer"]
      limit = payload.fetch("limit", 100)

      all_entities = sketchup.active_model.entities.to_a
      results = []

      all_entities.each do |entity|
        # Filter by entity_type
        if entity_type
          type_match = case entity_type.downcase
                       when "face" then entity.is_a?(sketchup.const_get("Face"))
                       when "edge" then entity.is_a?(sketchup.const_get("Edge"))
                       when "group" then entity.is_a?(sketchup.const_get("Group"))
                       when "component" then entity.is_a?(sketchup.const_get("ComponentInstance"))
                       else false
                       end
          next unless type_match
        end

        # Filter by layer
        if layer
          next unless entity.layer && entity.layer.name == layer
        end

        # Get layer name safely
        layer_name = entity.layer&.name || "Unassigned"

        # Get bounding box
        bbox = entity.bounds
        bounding_box = {
          min: [bbox.min.x.to_mm, bbox.min.y.to_mm, bbox.min.z.to_mm],
          max: [bbox.max.x.to_mm, bbox.max.y.to_mm, bbox.max.z.to_mm],
        }

        # Determine entity type string
        type_str = case entity
                   when sketchup.const_get("Face") then "face"
                   when sketchup.const_get("Edge") then "edge"
                   when sketchup.const_get("Group") then "group"
                   when sketchup.const_get("ComponentInstance") then "component"
                   else "unknown"
                   end

        results << {
          entityID: entity.entityID.to_s,
          type: type_str,
          layer: layer_name,
          bounding_box: bounding_box,
        }

        break if results.length >= limit
      end

      # Calculate overall spatial delta
      if results.any?
        all_mins = results.map { |r| r[:bounding_box][:min] }
        all_maxs = results.map { |r| r[:bounding_box][:max] }

        overall_bbox = {
          min: [
            all_mins.map { |m| m[0] }.min,
            all_mins.map { |m| m[1] }.min,
            all_mins.map { |m| m[2] }.min,
          ],
          max: [
            all_maxs.map { |m| m[0] }.max,
            all_maxs.map { |m| m[1] }.max,
            all_maxs.map { |m| m[2] }.max,
          ],
        }
      else
        overall_bbox = { min: [0, 0, 0], max: [0, 0, 0] }
      end

      {
        entity_ids: results.map { |r| r[:entityID] },
        spatial_delta: { bounding_box: overall_bbox },
        model_revision: 1,
        elapsed_ms: 0,
        entities: results,
      }
    end

    def handle_query_model_info(payload)
      # Delegate to get_scene_info
      handle_get_scene_info(payload)
    end

    # Conversion factor: mm to inches (SketchUp internal units)
    MM_TO_INCH = 1.0 / 25.4

    def mm_to_inches(mm)
      mm * MM_TO_INCH
    end

    def find_entities_by_ids(entity_ids)
      model = sketchup.active_model
      entities = model.entities
      found = []
      missing = []

      entity_ids.each do |eid|
        entity = entities.find { |e| e.entityID.to_s == eid }
        if entity
          found << entity
        else
          missing << eid
        end
      end

      raise ::SuBridge::UndoManager::EntityNotFoundError, "Entities not found: #{missing.join(', ')}" unless missing.empty?

      found
    end

    def handle_move_entity(payload)
      entity_ids = payload["entity_ids"]
      delta = payload["delta"] # [dx, dy, dz] in mm

      raise ::SuBridge::UndoManager::ValidationError, "entity_ids required" unless entity_ids
      raise ::SuBridge::UndoManager::ValidationError, "delta required" unless delta

      # Convert delta from mm to inches
      dx = mm_to_inches(delta[0] || 0)
      dy = mm_to_inches(delta[1] || 0)
      dz = mm_to_inches(delta[2] || 0)

      vector = Geom::Vector3d.new(dx, dy, dz)
      transformation = Geom::Transformation.translation(vector)

      entities = find_entities_by_ids(entity_ids)
      entities.each do |entity|
        entity.transformation = transformation * entity.transformation
      end

      {
        entity_ids: entity_ids,
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_rotate_entity(payload)
      entity_ids = payload["entity_ids"]
      center = payload["center"] # [cx, cy, cz] in mm
      axis = payload["axis"] || "+z" # axis string
      angle = payload["angle"] # angle in degrees

      raise ::SuBridge::UndoManager::ValidationError, "entity_ids required" unless entity_ids
      raise ::SuBridge::UndoManager::ValidationError, "center required" unless center
      raise ::SuBridge::UndoManager::ValidationError, "angle required" unless angle

      # Convert center from mm to inches
      cx = mm_to_inches(center[0] || 0)
      cy = mm_to_inches(center[1] || 0)
      cz = mm_to_inches(center[2] || 0)
      center_pt = Geom::Point3d.new(cx, cy, cz)

      # Parse axis
      axis_vector = case axis.to_s.downcase
                    when "+x", "x" then Geom::Vector3d.new(1, 0, 0)
                    when "-x" then Geom::Vector3d.new(-1, 0, 0)
                    when "+y", "y" then Geom::Vector3d.new(0, 1, 0)
                    when "-y" then Geom::Vector3d.new(0, -1, 0)
                    when "+z", "z" then Geom::Vector3d.new(0, 0, 1)
                    when "-z" then Geom::Vector3d.new(0, 0, -1)
                    else raise ::SuBridge::UndoManager::ValidationError, "Invalid axis: #{axis}"
                    end

      # Convert angle from degrees to radians
      angle_rad = angle * Math::PI / 180.0

      transformation = Geom::Transformation.rotation(center_pt, axis_vector, angle_rad)

      entities = find_entities_by_ids(entity_ids)
      entities.each do |entity|
        entity.transformation = transformation * entity.transformation
      end

      {
        entity_ids: entity_ids,
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_scale_entity(payload)
      entity_ids = payload["entity_ids"]
      center = payload["center"] # [cx, cy, cz] in mm
      scale = payload["scale"] # uniform scale factor or [sx, sy, sz]

      raise ::SuBridge::UndoManager::ValidationError, "entity_ids required" unless entity_ids
      raise ::SuBridge::UndoManager::ValidationError, "center required" unless center
      raise ::SuBridge::UndoManager::ValidationError, "scale required" unless scale

      # Convert center from mm to inches
      cx = mm_to_inches(center[0] || 0)
      cy = mm_to_inches(center[1] || 0)
      cz = mm_to_inches(center[2] || 0)
      center_pt = Geom::Point3d.new(cx, cy, cz)

      # Parse scale factor(s)
      if scale.is_a?(Numeric)
        sx = sy = sz = scale.to_f
      elsif scale.is_a?(Array) && scale.length == 3
        sx = scale[0].to_f
        sy = scale[1].to_f
        sz = scale[2].to_f
      else
        raise ::SuBridge::UndoManager::ValidationError, "scale must be a number or [sx, sy, sz]"
      end

      transformation = Geom::Transformation.scaling(center_pt, sx, sy, sz)

      entities = find_entities_by_ids(entity_ids)
      entities.each do |entity|
        entity.transformation = transformation * entity.transformation
      end

      {
        entity_ids: entity_ids,
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_copy_entity(payload)
      entity_ids = payload["entity_ids"]
      delta = payload["delta"] # [dx, dy, dz] in mm

      raise ::SuBridge::UndoManager::ValidationError, "entity_ids required" unless entity_ids
      raise ::SuBridge::UndoManager::ValidationError, "delta required" unless delta

      model = sketchup.active_model
      entities = model.entities

      # Convert delta from mm to inches
      dx = mm_to_inches(delta[0] || 0)
      dy = mm_to_inches(delta[1] || 0)
      dz = mm_to_inches(delta[2] || 0)

      vector = Geom::Vector3d.new(dx, dy, dz)
      transformation = Geom::Transformation.translation(vector)

      original_entities = find_entities_by_ids(entity_ids)
      new_entity_ids = []

      original_entities.each do |entity|
        # Use add_copy to create a copy, then apply transformation
        copy = entities.add_copy(entity)
        copy.transformation = transformation * copy.transformation
        new_entity_ids << copy.entityID.to_s
      end

      {
        entity_ids: new_entity_ids,
        spatial_delta: {},
        model_revision: 1,
        elapsed_ms: 0,
      }
    end

    def handle_export_gltf(payload)
      output_path = payload["output_path"]
      include_textures = payload.fetch("include_textures", true)

      raise ::SuBridge::UndoManager::ValidationError, "output_path required" unless output_path

      # SketchUp's GLTF exporter is available via the SketchupExchange gem
      # or we can use the built-in 3D warehouse export options
      # For now, use SketchUp's native export functionality
      model = sketchup.active_model

      # Ensure output path has .gltf or .glb extension
      unless output_path.end_with?(".gltf", ".glb")
        output_path = output_path + ".glb"
      end

      # Use SketchUp's native GLTF export (available in SketchUp 2021+)
      options = {
        "exportTextures" => include_textures,
        "binary" => output_path.end_with?(".glb"),
      }

      # SketchUp exports to a temporary location then we move it
      temp_path = output_path + ".tmp"

      begin
        # Call SketchUp's GLTF exporter
        # The exporter is accessed via the Model export method
        status = model.export(temp_path, options)

        unless status
          raise ::SuBridge::UndoManager::ValidationError, "GLTF export failed - SketchUp may not support this format"
        end

        # Rename temp file to final path
        ::FileUtils.mv(temp_path, output_path) if ::File.exist?(temp_path)

        {
          entity_ids: [],
          spatial_delta: {},
          model_revision: 1,
          elapsed_ms: 0,
          export_info: {
            format: "gltf",
            output_path: output_path,
            include_textures: include_textures,
          },
        }
      rescue => e
        # Clean up temp file if it exists
        ::FileUtils.rm_f(temp_path) if defined?(::FileUtils)
        raise ::SuBridge::UndoManager::ValidationError, "GLTF export failed: #{e.message}"
      end
    end

    def handle_export_ifc(payload)
      output_path = payload["output_path"]

      raise ::SuBridge::UndoManager::ValidationError, "output_path required" unless output_path

      # Ensure output path has .ifc extension
      unless output_path.end_with?(".ifc")
        output_path = output_path + ".ifc"
      end

      model = sketchup.active_model

      begin
        # SketchUp IFC export
        # Note: IFC export requires SketchUp Pro or the IFC extension
        options = {
          "exportLayers" => true,
          "exportSelectionOnly" => false,
        }

        status = model.export(output_path, options)

        unless status
          raise ::SuBridge::UndoManager::ValidationError, "IFC export failed - ensure SketchUp Pro is activated or IFC extension is installed"
        end

        {
          entity_ids: [],
          spatial_delta: {},
          model_revision: 1,
          elapsed_ms: 0,
          export_info: {
            format: "ifc",
            output_path: output_path,
          },
        }
      rescue => e
        raise ::SuBridge::UndoManager::ValidationError, "IFC export failed: #{e.message}"
      end
    end
  end
end
