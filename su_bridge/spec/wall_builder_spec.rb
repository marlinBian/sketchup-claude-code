# frozen_string_literal: true

require_relative "spec_helper"
require "su_bridge"
require "su_bridge/entities/wall_builder"

RSpec.describe SuBridge::Entities::WallBuilder do
  class FakeWallFace
    attr_reader :normal

    def initialize(points)
      @normal = self.class.normal_for(points)
    end

    def reverse!
      @normal = Geom::Vector3d.new(-normal.x, -normal.y, -normal.z)
    end

    def self.normal_for(points)
      a, b, c = points
      first = [b.x - a.x, b.y - a.y, b.z - a.z]
      second = [c.x - a.x, c.y - a.y, c.z - a.z]
      cross = [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
      ]
      length = Math.sqrt(cross.map { |value| value * value }.sum)
      Geom::Vector3d.new(cross[0] / length, cross[1] / length, cross[2] / length)
    end
  end

  class FakeWallEntities
    attr_reader :faces

    def initialize
      @faces = []
    end

    def add_face(*points)
      face = FakeWallFace.new(points)
      faces << face
      face
    end
  end

  class FakeWallGroup
    attr_reader :entities

    def initialize
      @entities = FakeWallEntities.new
    end
  end

  class FakeWallModelEntities
    attr_reader :group

    def initialize(group)
      @group = group
    end

    def add_group
      group
    end
  end

  class FakeWallModel
    attr_reader :entities

    def initialize(group)
      @entities = FakeWallModelEntities.new(group)
    end
  end

  def dot(first, second)
    first.x * second.x + first.y * second.y + first.z * second.z
  end

  def normalized(vector)
    length = Math.sqrt(vector.map { |value| value * value }.sum)
    Geom::Vector3d.new(vector[0] / length, vector[1] / length, vector[2] / length)
  end

  def expected_wall_normals(vertices)
    v1, v2, _v3, v4 = vertices
    direction = normalized([v4[0] - v1[0], v4[1] - v1[1], v4[2] - v1[2]])
    positive_normal = normalized([v1[0] - v2[0], v1[1] - v2[1], v1[2] - v2[2]])

    [
      Geom::Vector3d.new(0, 0, -1),
      Geom::Vector3d.new(0, 0, 1),
      Geom::Vector3d.new(-direction.x, -direction.y, -direction.z),
      direction,
      Geom::Vector3d.new(-positive_normal.x, -positive_normal.y, -positive_normal.z),
      positive_normal,
    ]
  end

  describe ".create_wall_group" do
    it "orients every prism face outward for horizontal wall pieces" do
      group = FakeWallGroup.new
      allow(Sketchup).to receive(:active_model).and_return(FakeWallModel.new(group))

      vertices = described_class.calculate_vertices([0, 0, 0], [1000, 0, 0], 2800, 200, "center")

      described_class.create_wall_group(vertices, {})

      expect(group.entities.faces.length).to eq(6)
      group.entities.faces.zip(expected_wall_normals(vertices)).each do |face, expected_normal|
        expect(dot(face.normal, expected_normal)).to be > 0.99
      end
    end

    it "orients every prism face outward for non-horizontal wall pieces" do
      group = FakeWallGroup.new
      allow(Sketchup).to receive(:active_model).and_return(FakeWallModel.new(group))

      vertices = described_class.calculate_vertices([0, 0, 0], [800, 1200, 0], 2800, 200, "center")

      described_class.create_wall_group(vertices, {})

      expect(group.entities.faces.length).to eq(6)
      group.entities.faces.zip(expected_wall_normals(vertices)).each do |face, expected_normal|
        expect(dot(face.normal, expected_normal)).to be > 0.99
      end
    end
  end
end
