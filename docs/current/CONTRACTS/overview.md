# Contracts Overview

Contracts are Python dataclasses serialized to JSON files between stages.

## Contract map

| Contract file | Main types | Produced by | Consumed by |
| --- | --- | --- | --- |
| [common.md](common.md) | shared IDs and status fields | all stages | all stages |
| [init.md](init.md) | `SQLUnit`, `SQLFragment`, `TableSchema`, `FieldDistribution`, `InitOutput` | init | parse, result |
| [parse.md](parse.md) | `SQLBranch`, `SQLUnitWithBranches`, `ParseOutput` | parse | recognition |
| [recognition.md](recognition.md) | `PerformanceBaseline`, `RecognitionOutput` | recognition | optimize, result |
| [optimize.md](optimize.md) | `OptimizationProposal`, `OptimizeOutput` | optimize | result |
| [result.md](result.md) | `Report`, `Patch`, `ResultOutput` | result | humans and downstream tooling |

## Serialization pattern

- Each contract has a Python dataclass definition under `python/sqlopt/contracts/`.
- Each stage writes a backward-compatible aggregate file.
- Parse, recognition, and optimize also write per-unit JSON files.

## Read next

- [Common IDs and status fields](common.md)
- [Init contracts](init.md)
