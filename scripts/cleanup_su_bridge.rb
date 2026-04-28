#!/usr/bin/env ruby
# frozen_string_literal: true

# Cleanup script for su_bridge Ruby plugin
# CRITICAL: Must stop server BEFORE removing constants

SOCKET_PATH = "/tmp/su_bridge.sock"
SU_BRIDGE_ROOT = "/Users/avenir/Code/personal/sketchup-agent-harness/su_bridge/lib"

puts "[su_bridge] Cleanup starting..."

# Step 1: CRITICAL - Stop the server FIRST
if defined?(SuBridge) && SuBridge.respond_to?(:stop)
  puts "[su_bridge] Stopping server..."
  SuBridge.stop
  # Wait a moment for timers to settle
  sleep 0.5
end

# Step 2: Remove socket file immediately
if File.exist?(SOCKET_PATH)
  puts "[su_bridge] Removing socket: #{SOCKET_PATH}"
  File.delete(SOCKET_PATH)
else
  puts "[su_bridge] Socket not found"
end

# Step 3: Clear Ruby load cache
$LOADED_FEATURES.reject! { |f| f.include?("su_bridge") || f.include?("su_bridge/lib") }
puts "[su_bridge] Cleared Ruby load cache"

# Step 4: Remove SuBridge constant and all nested constants
# Must be done AFTER stop() to prevent reconnect attempts
if defined?(SuBridge)
  # Get all nested constants first
  nested = []
  if SuBridge.respond_to?(:constants)
    nested = SuBridge.constants.dup
  end

  # Remove nested constants from the module
  nested.each do |c|
    begin
      SuBridge.send(:remove_const, c) rescue nil
    end
  end

  # Remove the main module
  Object.send(:remove_const, :SuBridge) rescue nil
  puts "[su_bridge] Removed SuBridge constant"
end

# Step 5: Clean global state that might reference old server
# Remove any lingering timer references by clearing related constants
%w[
  ServerListener
  CommandDispatcher
  UndoManager
  EntityManager
  JsonRpcHandler
].each do |const|
  begin
    if Object.const_defined?(const)
      Object.send(:remove_const, const.to_sym) rescue nil
      puts "[su_bridge] Removed: #{const}"
    end
  rescue
  end
end

puts "[su_bridge] Cleanup complete!"
puts ""
puts "[su_bridge] To restart fresh, copy-paste this EXACT sequence:"
puts ""
puts "=" * 60
puts "# Step 1: Load the plugin (this will re-define SuBridge module)"
puts "load '#{SU_BRIDGE_ROOT}/su_bridge.rb', true"
puts ""
puts "# Step 2: Start the server"
puts "SuBridge.start"
puts "=" * 60
