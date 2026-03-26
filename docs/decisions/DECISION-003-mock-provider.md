# DECISION-003: Mock Provider for Recognition and Optimize

**Date**: 2026-03-24
**Status**: Accepted

## Context

Recognition and Optimize stages require data:
- **Recognition**: EXPLAIN plans from database
- **Optimize**: LLM-generated optimization suggestions

The original design assumed real DB connector + real LLM API integration.

## Decision

Use `MockLLMProvider` for both stages, generating realistic mock data without real infrastructure.

## Rationale

- **CI/CD friendly**: No database or LLM API required for testing
- **Isolation**: Each stage can be tested independently
- **Deterministic**: Mock data is predictable
- **Fast**: No network calls or DB queries

## Consequences

- Recognition uses `MockLLMProvider.generate_baseline()` not real EXPLAIN
- Optimize uses `MockLLMProvider.generate_optimization()` not real LLM
- Real DB + LLM integration deferred to future iteration
- `common/llm_mock_generator.py` provides `LLMProviderBase` interface

## Interface

```python
class LLMProviderBase:
    def generate_baseline(self, sql: str, platform: str) -> PerformanceBaseline
    def generate_optimization(self, sql: str, platform: str) -> OptimizationProposal
```

## Implementation

See `python/sqlopt/common/llm_mock_generator.py`
