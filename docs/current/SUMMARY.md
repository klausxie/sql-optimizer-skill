# Project Summary

SQL Optimizer is a five-stage pipeline for finding and validating slow SQL in MyBatis XML.

## Core idea

The project is optimized for this workflow:

1. discover SQL and dynamic branches in MyBatis XML
2. enrich them with schema and data-distribution facts
3. validate candidates with `EXPLAIN` and optional baseline execution
4. generate optimized SQL
5. validate the optimized SQL and rank the final findings

## Why the project exists

The hardest part of MyBatis SQL optimization is not generating rewrite suggestions. It is finding the branches that are actually risky:

- optional predicates can disappear
- `foreach` can change cardinality
- `choose` can switch plans entirely
- field selectivity can make the same mapper behave very differently

This project tries to make those branches visible and testable.

## Current strengths

- Real MyBatis XML scanning.
- Dynamic branch expansion.
- Field-distribution extraction for query predicates.
- Baseline collection with plan, execution time, rows examined, rows returned, and result signature.
- Proposal validation against the same baseline.
- Per-unit outputs for larger projects.
- Safer concurrency and clearer CLI progress output.

## Current operating model

- Production runtime traces are optional, not required.
- The main supported validation path is a representative test database.
- MySQL and PostgreSQL are supported.
- Mock mode is available for local development and CI.

## Where to go next

- [Architecture](ARCHITECTURE.md)
- [Data Flow](DATAFLOW.md)
- [Stage design](STAGES/README.md)
- [Data contracts](CONTRACTS/overview.md)
