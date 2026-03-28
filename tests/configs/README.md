# Test Configurations

This directory contains test configurations for different scenarios.

## Scenarios

### 1. quick-smoke.yml
- **Purpose**: Fast smoke test without real DB
- **LLM**: Disabled (mock mode)
- **Branches**: 50 per SQL unit, max_cap 500
- **Concurrency**: Enabled
- **Use case**: CI/CD pipeline, pre-commit checks

### 2. single-sql-real-db.yml
- **Purpose**: Single complex SQL with real PostgreSQL database
- **LLM**: Disabled
- **Branches**: 100 per SQL, max_cap 500
- **Concurrency**: Disabled (sequential)
- **Use case**: Debugging a specific SQL branch issue
- **Prereq**: PostgreSQL running with `tests/real/mybatis-test/src/main/resources/schema.sql` and `data.sql` loaded

### 3. full-pipeline-llm.yml
- **Purpose**: Full 5-stage pipeline with LLM optimization
- **LLM**: Enabled (local LM Studio at localhost:1234)
- **Model**: qwen2.5-14b-instruct
- **Branches**: 100 per SQL, max_cap 1000
- **Concurrency**: Enabled
- **Use case**: End-to-end testing with real LLM optimization
- **Prereq**: LM Studio running with loaded model

### 4. max-branches-stress.yml
- **Purpose**: Stress test with maximum branch exploration
- **LLM**: Disabled
- **Branches**: 100 per SQL, max_cap 1000
- **Concurrency**: Enabled
- **Use case**: Testing branch explosion handling

## Running Tests

```bash
# Quick smoke test
sqlopt run 1 --config tests/configs/quick-smoke.yml
sqlopt run 2 --config tests/configs/quick-smoke.yml

# Single SQL with real DB
sqlopt run 1 --config tests/configs/single-sql-real-db.yml
sqlopt run 2 --config tests/configs/single-sql-real-db.yml
sqlopt run 3 --config tests/configs/single-sql-real-db.yml

# Full pipeline with LLM
sqlopt run 1 --config tests/configs/full-pipeline-llm.yml
sqlopt run 2 --config tests/configs/full-pipeline-llm.yml
sqlopt run 3 --config tests/configs/full-pipeline-llm.yml
sqlopt run 4 --config tests/configs/full-pipeline-llm.yml
sqlopt run 5 --config tests/configs/full-pipeline-llm.yml
```

## Database Setup for Real DB Tests

```bash
# Connect to PostgreSQL
psql -h localhost -p 5432 -U postgres -d postgres

# Load schema
\i tests/real/mybatis-test/src/main/resources/schema.sql

# Load data
\i tests/real/mybatis-test/src/main/resources/data.sql
```
