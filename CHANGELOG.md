# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- None

### Changed

- None

### Deprecated

- None

### Removed

- None

### Fixed

- None

### Security

- None

---

## [1.0.0] - 2026-05-04

### Added

- CLI-first SketchUp Agent Harness distribution for Claude CLI and Codex CLI.
- MCP server, SketchUp Ruby bridge, project initialization, validation, smoke,
  and bridge install flows for designer project workspaces.
- Runtime skill packaging for designer-facing natural-language workflows.
- Structured design model, design rules, component registry, asset lock, and
  project version contracts.
- Source import pipeline for images and other source references, including
  project-local dynamic import memory for source-backed iteration.
- Release smoke coverage for source checkout, installed wheel, runtime skill
  installation, and Ruby bridge behavior.

---

## [0.1.0] - 2024-04-15

### Added

- Ruby SketchUp plugin (su_bridge) with foundation modeling tools
- Python MCP server for LLM communication
- Design model JSON schema for abstract state layer
- ECC plugin configuration for Claude Code integration
- Skills for geometry composition, designer workflow, and semantic positioning
- Six design style presets
- Component search via Sketchfab and local library
- Export tools (glTF, IFC)
- CI/CD workflows for automated testing
