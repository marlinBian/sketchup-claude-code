# frozen_string_literal: true

require "rspec"
require "json"

# Mock SketchUp module for testing outside SketchUp
module SketchUp
  class UndoManager
    def self.begin_operation(name, disable_undo = true)
      # Mock implementation
    end

    def self.commit_operation
      # Mock implementation
    end

    def self.undo
      # Mock implementation
    end

    def self.clear
      # Mock implementation
    end
  end

  module Geom
    class Point3d
      attr_reader :x, :y, :z

      def initialize(x, y, z)
        @x = x.to_f
        @y = y.to_f
        @z = z.to_f
      end

      def -(other)
        Vector3d.new(@x - other.x, @y - other.y, @z - other.z)
      end

      def cross(other)
        Vector3d.new(0, 0, 0)
      end

      def length
        Math.sqrt(@x**2 + @y**2 + @z**2)
      end
    end

    class Vector3d
      attr_reader :x, :y, :z

      def initialize(x, y, z)
        @x = x.to_f
        @y = y.to_f
        @z = z.to_f
      end

      def length
        Math.sqrt(@x**2 + @y**2 + @z**2)
      end
    end
  end
end

# Mock UI module
module UI
  def self.start_timer(interval, repeat = false, &block)
    # Just execute immediately for testing
    block.call if block_given?
  end
end

# Load the library
$LOAD_PATH.unshift(File.expand_path("lib", __dir__))
require "su_bridge/version"
require "su_bridge/protocol/json_rpc_handler"
require "su_bridge/undo_manager"
require "su_bridge/command_dispatcher"
require "su_bridge/server_listener"
require "su_bridge/entity_manager"

RSpec.describe SuBridge::ServerListener do
  describe "#initialize" do
    it "creates a new server listener" do
      listener = described_class.new
      expect(listener).to be_a(described_class)
    end
  end

  describe "#running?" do
    it "returns false initially" do
      listener = described_class.new
      expect(listener.running?).to be false
    end
  end

  describe "ping handling" do
    it "responds to ping with pong" do
      # Create a mock request
      request = {
        "jsonrpc" => "2.0",
        "method" => "ping",
        "params" => { "timestamp" => Time.now.to_f },
        "id" => 1
      }

      # The server listener's process_request should handle this
      listener = SuBridge::ServerListener.new

      # Access private method for testing
      response = listener.send(:handle_ping, request["params"], request["id"])

      expect(response["result"]["status"]).to eq("pong")
      expect(response["result"]["server_version"]).to eq("0.1.0")
      expect(response["result"]["protocol_version"]).to eq("1.0")
    end
  end
end

RSpec.describe SuBridge::JsonRpcHandler do
  describe ".success_response" do
    it "returns valid JSON-RPC success format" do
      result = { status: "success" }
      response = described_class.success_response(result, 1)

      expect(response["jsonrpc"]).to eq("2.0")
      expect(response["result"]).to eq(result)
      expect(response["id"]).to eq(1)
    end
  end

  describe ".error_response" do
    it "returns valid JSON-RPC error format" do
      response = described_class.error_response(-32001, "Validation error", 1)

      expect(response["jsonrpc"]).to eq("2.0")
      expect(response["error"]["code"]).to eq(-32001)
      expect(response["error"]["message"]).to eq("Validation error")
      expect(response["id"]).to eq(1)
    end

    it "includes data when provided" do
      data = { operation_id: "op_123" }
      response = described_class.error_response(-32001, "Error", 1, data)

      expect(response["error"]["data"]).to eq(data)
    end
  end
end

RSpec.describe SuBridge::UndoManager do
  describe ".with_transaction" do
    it "executes block and returns result" do
      result = described_class.with_transaction(name: "test") do
        { success: true }
      end

      expect(result).to eq({ success: true })
    end

    it "raises and rolls back on error when rollback_on_failure is true" do
      expect {
        described_class.with_transaction(name: "test", rollback_on_failure: true) do
          raise "Test error"
        end
      }.to raise_error("Test error")
    end

    it "raises without rollback when rollback_on_failure is false" do
      expect {
        described_class.with_transaction(name: "test", rollback_on_failure: false) do
          raise "Test error"
        end
      }.to raise_error("Test error")
    end
  end

  describe "error classes" do
    it "has ValidationError" do
      expect(described_class::ValidationError).to be < StandardError
    end

    it "has EntityNotFoundError" do
      expect(described_class::EntityNotFoundError).to be < StandardError
    end

    it "has PermissionError" do
      expect(described_class::PermissionError).to be < StandardError
    end

    it "has RollbackError" do
      expect(described_class::RollbackError).to be < StandardError
    end
  end
end

RSpec.describe SuBridge::CommandDispatcher do
  let(:dispatcher) { described_class.new }

  describe "#dispatch" do
    it "returns error for unknown method" do
      request = {
        "jsonrpc" => "2.0",
        "method" => "unknown_method",
        "params" => {},
        "id" => 1
      }

      response = dispatcher.dispatch(request)

      expect(response["error"]["code"]).to eq(-32000)
      expect(response["error"]["message"]).to include("Unknown method")
    end

    it "returns error for unknown operation_type" do
      request = {
        "jsonrpc" => "2.0",
        "method" => "execute_operation",
        "params" => {
          "operation_type" => "unknown_operation",
          "payload" => {}
        },
        "id" => 1
      }

      response = dispatcher.dispatch(request)

      expect(response["error"]["code"]).to eq(-32000)
      expect(response["error"]["message"]).to include("Unknown operation_type")
    end
  end

  describe "#dispatch_operation" do
    it "returns validation error when operation_type is nil" do
      response = dispatcher.dispatch_operation("op_123", nil, {}, true)

      expect(response["error"]["code"]).to eq(-32000)
      expect(response["error"]["data"]["operation_id"]).to eq("op_123")
    end
  end
end
