# frozen_string_literal: true

# Ensure lib directory is in load path so requires work correctly
$LOAD_PATH.unshift(File.expand_path(".", __dir__)) unless $LOAD_PATH.include?(File.expand_path(".", __dir__))

require "su_bridge/version"
require "su_bridge/server_listener"
require "su_bridge/command_dispatcher"
require "su_bridge/undo_manager"
require "su_bridge/entities/face_builder"
require "su_bridge/entities/wall_builder"
require "su_bridge/entities/component_manager"
require "su_bridge/entities/group_builder"
require "su_bridge/entities/material_applier"
require "su_bridge/protocol/json_rpc_handler"
require "su_bridge/design_model_sync"

module SuBridge
  class Error < StandardError; end

  # SOCKET_PATH is now in version.rb to ensure it's defined before other files load

  # @return [DesignModelSync] Singleton instance for design model sync
  def self.design_sync
    @design_sync ||= DesignModelSync.new
  end

  def self.listener
    @listener ||= ServerListener.new
  end

  def self.start
    return listener if listener.running?

    design_sync.register_observer
    listener.start
    listener
  end

  def self.stop
    @listener&.stop
  end
end
