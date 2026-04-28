# frozen_string_literal: true

require_relative "spec_helper"
require "su_bridge"

RSpec.describe SuBridge do
  before do
    described_class.instance_variable_set(:@listener, nil)
    described_class.instance_variable_set(:@design_sync, nil)
  end

  it "has a version number" do
    expect(SuBridge::VERSION).not_to be nil
  end

  it "starts the bridge listener only once" do
    fake_listener_class = Class.new do
      attr_reader :start_count

      def initialize
        @running = false
        @start_count = 0
      end

      def running?
        @running
      end

      def start
        @start_count += 1
        @running = true
      end
    end
    fake_sync = spy("design_sync")

    stub_const("SuBridge::ServerListener", fake_listener_class)
    allow(described_class).to receive(:design_sync).and_return(fake_sync)

    listener = described_class.start
    described_class.start

    expect(listener.start_count).to eq(1)
    expect(fake_sync).to have_received(:register_observer).once
  end

  it "stops the bridge listener when one exists" do
    fake_listener = double("listener", stop: true)

    described_class.instance_variable_set(:@listener, fake_listener)
    described_class.stop

    expect(fake_listener).to have_received(:stop)
  end
end

RSpec.describe SuBridge::JsonRpcHandler do
  describe ".success_response" do
    it "returns valid JSON-RPC success format" do
      result = { "status" => "success" }
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
      data = { "operation_id" => "op_123" }
      response = described_class.error_response(-32001, "Error", 1, data)

      expect(response["error"]["data"]).to eq(data)
    end
  end
end
