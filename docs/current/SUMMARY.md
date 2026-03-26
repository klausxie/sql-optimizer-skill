# Summary

## What is SQL Optimizer

MyBatis XML SQL optimization tool with 5-stage pipeline.

## Features

- SQL parsing and branch expansion
- Performance baseline collection
- LLM-based optimization suggestions
- Patch generation with unified diff

## Quick Start

```bash
sqlopt run 1          # Init
sqlopt run 2          # Parse
sqlopt run 3          # Recognition
sqlopt run 4          # Optimize
sqlopt run 5          # Result
```

## Documentation

- [Architecture](ARCHITECTURE.md) - System design
- [STAGES/](STAGES/) - Stage-specific documentation
- [COMMON/](COMMON/) - Common modules
- [CONTRACTS/](CONTRACTS/) - Data contracts
