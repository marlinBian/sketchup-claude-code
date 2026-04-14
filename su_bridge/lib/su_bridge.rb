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

module SuBridge
  class Error < StandardError; end

  # SOCKET_PATH is now in version.rb to ensure it's defined before other files load

  def self.start
    ServerListener.new.start
  end
end
