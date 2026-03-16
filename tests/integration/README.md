# Integration Tests

This directory is reserved for integration tests that require external resources
such as database connections or LLM providers.

## Running Integration Tests

Integration tests are typically excluded from the default test run and require
explicit opt-in:

```bash
# Run only integration tests
python -m pytest tests/integration/ -v

# Run all tests including integration
python -m pytest tests/ --include-integration
```

## Adding Integration Tests

1. Create test files with the naming pattern `test_*.py`
2. Mark tests requiring external resources with `@pytest.mark.integration`
3. Use fixtures from `conftest.py` for database setup/teardown
