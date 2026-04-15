# Contributing to SCC

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a feature branch

## Development Setup

```bash
# Python
cd mcp_server && pip install uv && uv sync

# Ruby
cd su_bridge && bundle install
```

## Making Changes

1. Write tests for new functionality
2. Ensure tests pass
3. Check syntax
4. Submit PR

## Testing

```bash
# Python
cd mcp_server && uv run pytest tests/ -v

# Ruby
cd su_bridge && bundle exec rspec spec/
```

## Commit Format

```
type: description

Types: feat, fix, refactor, docs, test, chore
```

## Questions

Open an issue first for significant changes.
