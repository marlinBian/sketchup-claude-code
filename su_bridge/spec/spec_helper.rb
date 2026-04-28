# frozen_string_literal: true

require "rspec"
require "fileutils"
require "json"
require "tmpdir"

$LOAD_PATH.unshift(File.expand_path("../lib", __dir__))

module Sketchup
  class ModelObserver; end
  class Group; end
  class ComponentInstance; end

  class FakeModel
    def start_operation(_name, _disable_ui = true); end
    def commit_operation; end
    def abort_operation; end
  end

  def self.active_model
    @active_model ||= FakeModel.new
  end
end

SketchUp = Sketchup unless defined?(SketchUp)

module UI
  def self.start_timer(_interval, _repeat = false)
    yield if block_given?
  end
end

module Geom
  class Point3d
    attr_reader :x, :y, :z

    def initialize(x = 0, y = 0, z = 0)
      @x = x.to_f
      @y = y.to_f
      @z = z.to_f
    end

    def to_a
      [x, y, z]
    end
  end

  class Vector3d < Point3d; end

  class Transformation
    attr_reader :origin

    def initialize(origin = Point3d.new)
      @origin = origin
    end

    def self.translation(vector)
      new(Point3d.new(vector.x, vector.y, vector.z))
    end

    def self.rotation(_point, _axis, _angle)
      new
    end

    def self.scaling(*_args)
      new
    end

    def *(_other)
      self
    end

    def [](_row, _column)
      0
    end
  end
end

ORIGIN = Geom::Point3d.new(0, 0, 0) unless defined?(ORIGIN)
Z_AXIS = Geom::Vector3d.new(0, 0, 1) unless defined?(Z_AXIS)

class Numeric
  def degrees
    self * Math::PI / 180.0
  end

  def to_mm
    self * 25.4
  end
end
