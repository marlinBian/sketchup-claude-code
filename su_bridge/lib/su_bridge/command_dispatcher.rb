# frozen_string_literal: true

require "securerandom"

module SuBridge
  # Routes JSON-RPC requests to appropriate Ruby API handlers.
  class CommandDispatcher
    OPERATION_HANDLERS = {
      "create_face" => :handle_create_face,
      "create_box" => :handle_create_box,
      "create_wall" => :handle_create_wall,
      "create_group" => :handle_create_group,
      "delete_entity" => :handle_delete_entity,
      "set_material" => :handle_set_material,
      "apply_material" => :handle_apply_material,
      "apply_style" => :handle_apply_style,
      "query_entities" => :handle_query_entities,
      "query_model_info" => :handle_query_model_info,
      "get_scene_info" => :handle_get_scene_info,
      "place_component" => :handle_place_component,
      "place_lighting" => :handle_place_lighting,
      "set_camera_view" => :handle_set_camera_view,
      "capture_design" => :handle_capture_design,
      "cleanup_model" => :handle_cleanup_model,
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

      raise ::SuBridge::UndoManager::ValidationError, "skp_path required" unless skp_path
      raise ::SuBridge::UndoManager::ValidationError, "position required" unless position

      result = SuBridge::Entities::ComponentManager.place(
        skp_path: skp_path,
        position: position,
        rotation: rotation,
        scale: scale,
        component_id: component_id
      )

      {
        entity_ids: [result[:entity_id]],
        spatial_delta: SuBridge::Entities::ComponentManager.spatial_delta(
          sketchup.active_model.entities.find { |e| e.entityID.to_s == result[:entity_id] }
        ),
        model_revision: 1,
        elapsed_ms: 0,
        placement_info: {
          definition_name: result[:definition_name],
          component_id: component_id,
        },
      }
    rescue FileNotFoundError => e
      raise ::SuBridge::UndoManager::ValidationError, "SKP file not found: #{e.message}"
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
      # Stub - would query ::Sketchup model
      { entity_ids: [], spatial_delta: {}, model_revision: 1, elapsed_ms: 0 }
    end

    def handle_query_model_info(payload)
      # Delegate to get_scene_info
      handle_get_scene_info(payload)
    end
  end
end
