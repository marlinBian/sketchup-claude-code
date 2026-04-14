# frozen_string_literal: true

module SuBridge
  # Wraps SketchUp Model undo operations to provide atomic transactions with rollback.
  class UndoManager
    class Error < StandardError; end
    class RollbackError < Error; end
    class ValidationError < Error; end
    class EntityNotFoundError < Error; end
    class PermissionError < Error; end

    def self.with_transaction(name:, rollback_on_failure: true)
      # Get Sketchup from the top-level namespace dynamically
      sketchup = ::Object.const_get('Sketchup')
      model = sketchup.active_model
      model.start_operation(name, true)

      begin
        result = yield
        model.commit_operation
        result
      rescue => e
        if rollback_on_failure
          begin
            model.abort_operation
          rescue => rollback_error
            raise RollbackError, "Original: #{e.message}, Rollback: #{rollback_error.message}"
          end
        end
        raise e
      end
    end
  end
end
