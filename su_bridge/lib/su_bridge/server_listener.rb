# frozen_string_literal: true

require "socket"
require "json"
require "time"

module SuBridge
  # Non-blocking socket server for receiving JSON-RPC requests.
  # Uses UI.start_timer for deferred execution to keep SketchUp responsive.
  # Features automatic self-healing if socket is disrupted.
  class ServerListener
    SOCKET_PATH = "/tmp/su_bridge.sock"
    TIMER_INTERVAL = 0.1 # seconds
    PROTOCOL_VERSION = "1.0"
    SERVER_VERSION = "0.1.0"
    RECONNECT_DELAY = 1.0 # seconds before attempting reconnect
    MAX_RECONNECT_ATTEMPTS = 3

    def initialize
      @socket = nil
      @running = false
      @connected_clients = []
      @last_ping_time = nil
      @reconnect_attempts = 0
      @socket_valid = false
    end

    def start
      return if @running
      return unless defined?(UI) && defined?(UI.start_timer)

      setup_socket
      @running = true
      @reconnect_attempts = 0
      schedule_polling
      puts "[su_bridge] Server started on #{SOCKET_PATH}"
    end

    def stop
      @running = false
      @socket_valid = false
      @connected_clients.each(&:close)
      @connected_clients.clear
      close_socket
      puts "[su_bridge] Server stopped"
    end

    def running?
      @running
    end

    private

    def setup_socket
      close_socket

      # Clean up any stale socket file
      File.delete(SOCKET_PATH) if File.exist?(SOCKET_PATH)

      begin
        @socket = UNIXServer.new(SOCKET_PATH)
        @socket.listen(5)
        @socket.autoclose = false
        @socket_valid = true
        @reconnect_attempts = 0
        puts "[su_bridge] Socket ready on #{SOCKET_PATH}"
      rescue => e
        @socket_valid = false
        puts "[su_bridge] Socket setup error: #{e.message}"
        raise
      end
    end

    def close_socket
      if @socket
        begin
          @socket.close
        rescue => e
          puts "[su_bridge] Socket close error: #{e.message}"
        end
        @socket = nil
      end
    end

    def schedule_polling
      UI.start_timer(TIMER_INTERVAL, false) do
        poll_socket
        schedule_polling if @running
      end
    end

    def poll_socket
      return unless @running

      # Check if socket needs recreation
      unless socket_healthy?
        handle_socket_disconnect
        return
      end

      begin
        # Check for incoming connections without blocking
        io = IO.select([@socket], nil, nil, 0)
        return unless io && !io[0].empty?

        client = @socket.accept_nonblock
        @connected_clients << client
        handle_client(client)
      rescue IO::EAGAINWaitReadable, Errno::EAGAIN
        # No pending connections - this is normal
      rescue Errno::EBADF, IOError => e
        # Socket was closed or became invalid
        puts "[su_bridge] Socket invalid: #{e.message}"
        handle_socket_disconnect
      rescue => e
        puts "[su_bridge] Error polling socket: #{e.message}"
        # Continue running - don't crash on transient errors
      end
    end

    def socket_healthy?
      return false unless @socket
      return false unless @socket_valid

      # Check if socket file still exists
      unless File.exist?(SOCKET_PATH)
        puts "[su_bridge] Socket file missing"
        @socket_valid = false
        return false
      end

      true
    rescue => e
      puts "[su_bridge] Socket health check failed: #{e.message}"
      @socket_valid = false
      false
    end

    def handle_socket_disconnect
      @socket_valid = false
      close_socket

      if @running && @reconnect_attempts < MAX_RECONNECT_ATTEMPTS
        @reconnect_attempts += 1
        puts "[su_bridge] Attempting reconnect (#{@reconnect_attempts}/#{MAX_RECONNECT_ATTEMPTS})..."

        # Schedule reconnect with delay
        UI.start_timer(RECONNECT_DELAY, false) do
          attempt_reconnect
        end
      elsif @reconnect_attempts >= MAX_RECONNECT_ATTEMPTS
        puts "[su_bridge] Max reconnect attempts reached. Run .start to restart."
      end
    end

    def attempt_reconnect
      return unless @running

      begin
        setup_socket
        puts "[su_bridge] Reconnected successfully"
      rescue => e
        puts "[su_bridge] Reconnect failed: #{e.message}"
        handle_socket_disconnect
      end
    end

    def handle_client(client)
      begin
        # Read request with timeout using readpartial for better control
        request_data = client.read_nonblock(65536)
        return if request_data.empty?

        request = JSON.parse(request_data)
        response = process_request(request)

        client.write(JSON.generate(response) + "\n")
      rescue JSON::ParserError => e
        error_response = SuBridge::JsonRpcHandler.error_response(
          -32001,
          "Invalid JSON: #{e.message}",
          request&.dig("id")
        )
        client.write(JSON.generate(error_response) + "\n")
      rescue Errno::EPIPE, Errno::ECONNRESET, IOError => e
        # Client disconnected - normal behavior
        puts "[su_bridge] Client disconnected: #{e.message}"
      rescue => e
        puts "[su_bridge] Error handling client: #{e.message}"
        error_response = SuBridge::JsonRpcHandler.error_response(
          -32000,
          "Internal error: #{e.message}",
          nil
        )
        begin
          client.write(JSON.generate(error_response) + "\n")
        rescue => write_error
          puts "[su_bridge] Failed to write error: #{write_error.message}"
        end
      ensure
        client.close unless client.closed?
        @connected_clients.delete(client)
      end
    end

    def process_request(request)
      method = request["method"]
      id = request["id"]
      params = request["params"] || {}

      case method
      when "ping"
        handle_ping(params, id)
      when "handshake"
        handle_handshake(params, id)
      when "execute_operation"
        handle_execute_operation(params, id)
      else
        SuBridge::JsonRpcHandler.error_response(
          -32000,
          "Unknown method: #{method}",
          id
        )
      end
    end

    def handle_ping(params, id)
      @last_ping_time = Time.now

      SuBridge::JsonRpcHandler.success_response({
        status: "pong",
        server_version: SERVER_VERSION,
        protocol_version: PROTOCOL_VERSION,
        timestamp: params["timestamp"],
        server_time: Time.now.to_f,
        socket_valid: @socket_valid,
      }, id)
    end

    def handle_handshake(params, id)
      client_version = params["client_version"] || "unknown"

      SuBridge::JsonRpcHandler.success_response({
        status: "handshake_complete",
        server_version: SERVER_VERSION,
        protocol_version: PROTOCOL_VERSION,
        client_version: client_version,
      }, id)
    end

    def handle_execute_operation(params, id)
      operation_id = params["operation_id"] || "op_#{SecureRandom.hex(4)}"
      operation_type = params["operation_type"]
      payload = params["payload"] || {}
      rollback_on_failure = params.fetch("rollback_on_failure", true)

      handler = CommandDispatcher.new.dispatch_operation(
        operation_id,
        operation_type,
        payload,
        rollback_on_failure
      )

      SuBridge::JsonRpcHandler.success_response(handler, id)
    rescue => e
      rollback_status = rollback_on_failure ? "completed" : "skipped"
      error_code = error_code_for(e)

      SuBridge::JsonRpcHandler.error_response(
        error_code,
        e.message,
        id,
        {
          operation_id: operation_id,
          rollback_status: rollback_status,
          model_revision: 1,
        }
      )
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
  end
end
