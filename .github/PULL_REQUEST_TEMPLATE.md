# Pull Request

## Summary

<!-- What does this PR do? Provide a brief summary -->

## Type of Change

- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (fix or feature that causes existing functionality to change)
- [ ] Documentation update
- [ ] Refactoring
- [ ] Test update

## Testing

<!-- How was this tested? -->

- [ ] Python tests:
  `cd mcp_server && uv run --extra dev pytest tests/ -m "not integration" -v --tb=short`
- [ ] Product smoke:
  `cd mcp_server && uv run --extra dev sketchup-agent smoke /tmp/sah-pr-smoke --force`
- [ ] MCP startup: `./mcp_server/start.sh --startup-check`
- [ ] Ruby tests: `cd su_bridge && bundle exec rspec spec/ --format progress`
- [ ] Markdown lint: `npx markdownlint-cli2`

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code where necessary
- [ ] I have updated the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or my feature works
- [ ] New and existing tests pass locally

## Screenshots/Logs

<!-- If applicable, add screenshots or logs -->

## Additional Context

<!-- Any other context about the PR -->
