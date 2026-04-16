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

- [ ] Ruby syntax check: `for f in su_bridge/lib/su_bridge/**/*.rb su_bridge/spec/**/*.rb; do ruby -c "$f" || exit 1; done`
- [ ] Python syntax check: `python3 -m py_compile mcp_server/mcp_server/**/*.py`
- [ ] Python tests: `cd mcp_server && python3 -m pytest tests/ -v`

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
