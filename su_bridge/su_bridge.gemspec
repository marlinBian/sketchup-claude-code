Gem::Specification.new do |spec|
  spec.name = "su_bridge"
  spec.version = "0.1.0"
  spec.summary = "SketchUp bridge for agent CLI integration"
  spec.description = "Ruby plugin providing bidirectional communication between SketchUp Agent Harness and SketchUp"
  spec.authors = ["SketchUp Agent Harness Team"]
  spec.files = Dir.glob("lib/**/*.rb")
  spec.add_development_dependency "rspec", "~> 3.13"
end
