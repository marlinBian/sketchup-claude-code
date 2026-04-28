# frozen_string_literal: true

require_relative "spec_helper"
require "su_bridge"

RSpec.describe SuBridge do
  it "has a version number" do
    expect(SuBridge::VERSION).not_to be nil
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
