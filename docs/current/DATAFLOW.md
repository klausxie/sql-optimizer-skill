# Data Flow

## End-to-end artifact flow

```text
Mapper XML
  -> InitOutput
  -> ParseOutput
  -> RecognitionOutput
  -> OptimizeOutput
  -> ResultOutput
```

## Stage-by-stage flow

| Stage | Reads | Produces | Main file |
| --- | --- | --- | --- |
| `init` | mapper XML files, optional DB metadata | `InitOutput` plus side files | `runs/{run_id}/init/sql_units.json` |
| `parse` | `init/sql_units.json`, fragments, schema, field distributions | `ParseOutput` | `runs/{run_id}/parse/sql_units_with_branches.json` |
| `recognition` | parse branches, optional DB connector | `RecognitionOutput` | `runs/{run_id}/recognition/baselines.json` |
| `optimize` | baselines, schema, optional DB connector and LLM provider | `OptimizeOutput` | `runs/{run_id}/optimize/proposals.json` |
| `result` | init SQL units, baselines, proposals | `ResultOutput` | `runs/{run_id}/result/report.json` |

## Object flow for one SQL unit

### 1. Init

`SQLUnit`

- stable unit ID
- mapper file
- statement ID
- original SQL text
- statement type

### 2. Parse

`SQLUnitWithBranches`

- keeps the original `sql_unit_id`
- contains one or more `SQLBranch`
- each branch gets a `path_id`

### 3. Recognition

`PerformanceBaseline`

- keyed by `sql_unit_id + path_id`
- adds plan, cost, execution time, rows, result signature, and execution error

### 4. Optimize

`OptimizationProposal`

- keyed by `sql_unit_id + path_id`
- adds optimized SQL, rationale, confidence, before/after metrics, validation status, and gain ratio

### 5. Result

`ResultOutput`

- aggregates ranked findings
- emits report text
- emits per-unit patches (`.patch` + `.meta.json`) for proposals that are safe enough to patch
- patches use unified diff format with filename-only headers for `patch -d` compatibility

## Run directory layout

```text
runs/{run_id}/
  init/
    sql_units.json
    sql_fragments.json
    table_schemas.json
    field_distributions.json
    xml_mappings.json
    SUMMARY.md
  parse/
    sql_units_with_branches.json
    units/
      _index.json
      {unit_id}.json
    SUMMARY.md
  recognition/
    baselines.json
    units/
      _index.json
      {unit_id}.json
    SUMMARY.md
  optimize/
    proposals.json
    units/
      _index.json
      {unit_id}.json
    SUMMARY.md
  result/
    report.json
    units/
      _index.json
      {unit_id}.patch
      {unit_id}.meta.json
    SUMMARY.md
```

## Cross-stage IDs

These fields are the stable links across the pipeline:

- `run_id`
- `sql_unit_id`
- `path_id`

Downstream stages should never invent a new unit identity when they can preserve the upstream one.

## Read next

- [Architecture](ARCHITECTURE.md)
- [Stage design](STAGES/README.md)
- [Contracts overview](CONTRACTS/overview.md)
