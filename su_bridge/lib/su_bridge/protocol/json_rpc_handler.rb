# frozen_string_literal: true

module SuBridge
  # Handles JSON-RPC request parsing and response formatting.
  module JsonRpcHandler
    def self.success_response(result, id)
      {
        "jsonrpc" => "2.0",
        "result" => stringify_keys(result),
        "id" => id,
      }
    end

    def self.error_response(code, message, id, data = nil)
      response = {
        "jsonrpc" => "2.0",
        "error" => {
          "code" => code,
          "message" => message,
        },
        "id" => id,
      }
      response["error"]["data"] = stringify_keys(data) if data
      response
    end

    def self.parse_request(data)
      JSON.parse(data)
    rescue JSON::ParserError => e
      raise ValidationError, "Invalid JSON: #{e.message}"
    end

    def self.validate_request(request)
      unless request["jsonrpc"] == "2.0"
        raise ValidationError, "Invalid JSON-RPC version"
      end

      unless request["method"]
        raise ValidationError, "Missing method"
      end

      true
    end

    def self.stringify_keys(value)
      case value
      when Array
        value.map { |item| stringify_keys(item) }
      when Hash
        value.each_with_object({}) do |(key, item), result|
          result[key.to_s] = stringify_keys(item)
        end
      else
        value
      end
    end
  end
end
