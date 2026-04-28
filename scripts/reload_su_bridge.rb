#!/usr/bin/env ruby
# frozen_string_literal: true

# Hot-reload script for su_bridge - reloads without restart
# Use this when you want to pick up code changes without restarting SketchUp

SOCKET_PATH = "/tmp/su_bridge.sock"
SU_BRIDGE_PATH = "/Users/avenir/Code/personal/sketchup-agent-harness/su_bridge/lib/su_bridge.rb"

puts "[su_bridge] Hot-reload starting..."

# Step 1: Stop current server
if defined?(SuBridge) && SuBridge.respond_to?(:stop)
  puts "[su_bridge] Stopping server..."
  SuBridge.stop
  sleep 0.3
end

# Step 2: Delete socket immediately
if File.exist?(SOCKET_PATH)
  File.delete(SOCKET_PATH) rescue nil
  puts "[su_bridge] Deleted socket"
end

# Step 3: Clear ALL su_bridge related constants
# This is aggressive but necessary for true reload
constants_to_remove = []
ObjectSpace.each_object(Module) do |m|
  if m.name && (m.name.include?("SuBridge") || m.name.include?("su_bridge"))
    constants_to_remove << m.name
  end
rescue
  # Ignore errors from anonymous modules
end

constants_to_remove.uniq.each do |name|
  begin
    parts = name.split("::")
    if parts.length == 1 || (parts.length == 2 && parts[0] == "SuBridge")
      const_name = parts.last.to_sym
      Object.send(:remove_const, const_name) rescue nil
      puts "[su_bridge] Removed: #{name}"
    end
  rescue
  end
end

# Step 4: Clear load cache for su_bridge files
$LOADED_FEATURES.reject! { |f| f =~ /su_bridge/i }
puts "[su_bridge] Cleared load cache"

# Step 5: Force garbage collection to clean up old instances
GC.start
sleep 0.1

puts "[su_bridge] Hot-reload complete!"
puts ""
puts "=" * 60
puts "Now run these commands:"
puts ""
puts "load '#{SU_BRIDGE_PATH}', true"
puts "SuBridge.start"
puts "=" * 60
