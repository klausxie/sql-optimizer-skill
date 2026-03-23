# SQL Optimizer Architecture (V8)

> Last updated: 2026-03-19

This document describes the V8 architecture and execution flow of SQL Optimizer.

> **Note**: V9 is the current default architecture. V8 (7-stage) has been superseded.
> See [V9 Architecture Overview](./v9-design/V9_ARCHITECTURE_OVERVIEW.md) for details.

---

## 1. V8 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         User Interaction Layer                             │
│  ┌─────────────────┐           ┌─────────────────┐                       │
│  │   sqlopt-cli    │           │   OpenCode      │                       │
│  │  (Engineering)  │           │    Skill        │                       │
│  │                 │           │   (LLM AI)      │                       │
│  └────────┬────────┘           └────────┬────────┘                       │
└───────────┼─────────────────────────────┼─────────────────────────────────┘
            │                             │
            │    CLI handles execution     │
            │◄──────────────────────────►│
            │    Skill handles AI/LLM     │
            ▼                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        7-Stage Processing Pipeline                          │
│                                                                             │
│  [1.Discovery] → [2.Branching] → [3.Pruning] → [4.Baseline] →            │
│  [5.Optimize] → [6.Validate] → [7.Patch]                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. V8 Seven-Stage Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Discovery                                                          │
│ • Connect to database, validate DSN [DB] 🐢                                 │
│ • Collect table structure, indexes, data volume [DB] 🐢                      │
│ • Parse MyBatis XML, extract SQL templates                                   │
│ • Identify involved tables, embed table structure info                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 2: Branching                                                          │
│ • Expand branches based on strategy: all_combinations / pairwise / boundary  │
│ • Record branch conditions                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Pruning                                                            │
│ • Static analysis of each branch SQL [CPU] ⚡                                │
│ • Mark risk types + severity level                                           │
│ • Branch aggregation: deduplication + classification                          │
│ • Pruning: filter low-risk branches                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 4: Baseline                                                           │
│ • Execute EXPLAIN for high-risk branches [DB] 🐢                            │
│ • Execute SQL actually [DB] 🐢                                              │
│ • Collect performance data + result set hash/sample                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 5: Optimize                                                          │
│ • Rule engine: apply built-in optimization rules [CPU] ⚡                    │
│ • LLM optimization: call large language model [API] ⏱️                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 6: Validate                                                           │
│ • Semantic equivalence verification [DB] 🐢                                  │
│ • Performance comparison [DB] 🐢                                            │
│ • Result set consistency verification [DB] 🐢                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 7: Patch                                                             │
│ • Generate XML patch                                                         │
│ • Display patch diff                                                         │
│ • User confirmation [interaction] 📋                                          │
│ • Backup and apply patch [FS] 💾                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Legend**: 🐢 IO-bound (slow) | ⚡ CPU-bound (fast) | ⏱️ LLM API call | 📋 User interaction | 💾 File operation

---

## 3. Stage Overview

| Stage | Name | Function | Time-consuming Node |
|-------|------|----------|---------------------|
| 1 | Discovery | Connect to DB, collect schema, parse XML | DB 🐢 |
| 2 | Branching | Branch expansion (3 strategies) | - |
| 3 | Pruning | Static analysis, risk marking, aggregation pruning | CPU ⚡ |
| 4 | Baseline | EXPLAIN, execute SQL, collect performance | DB 🐢 |
| 5 | Optimize | Rule engine + LLM optimization | LLM ⏱️ |
| 6 | Validate | Semantic verification, performance comparison, result set verification | DB 🐢 |
| 7 | Patch | Generate patch, user confirmation, apply | FS 💾 |

---

## 4. Stage Details

### Stage 1: Discovery

| Function | Description |
|----------|-------------|
| Connect to database | Connect to target database, obtain connection info |
| Collect table structure | Get column info, indexes, primary keys for all tables |
| Parse XML | Parse MyBatis Mapper XML files |
| Extract SQL | Extract all SELECT/INSERT/UPDATE/DELETE statements |
| Identify dynamic SQL | Identify `<if>`, `<choose>`, `<foreach>` and other dynamic tags |

**Output**:
- `sqlunits.jsonl` - SQL unit list
- `fragments.jsonl` - SQL fragment catalog

---

### Stage 2: Branching

| Function | Description |
|----------|-------------|
| Branch generation strategy | Support three strategies: AllCombinations / Pairwise / Boundary |
| Condition expansion | Expand dynamic SQL into concrete branches |
| Risk marking | Mark risk points for each branch |

**Output**:
- `branches.jsonl` - Branch list

---

### Stage 3: Pruning

| Function | Description |
|----------|-------------|
| Prefix wildcard detection | Detect `LIKE '%value'` patterns |
| Suffix wildcard detection | Detect `LIKE 'value%'` patterns |
| Function wrap detection | Detect `WHERE UPPER(col) = ?` |
| SELECT * detection | Detect full column queries |
| N+1 detection | Detect subquery N+1 patterns |
| Missing index hints | Detect WHERE conditions without indexes |

**Output**:
- `risks.jsonl` - Risk list

---

### Stage 4: Baseline

| Function | Description |
|----------|-------------|
| EXPLAIN analysis | Execute EXPLAIN to get execution plan |
| Performance collection | Collect execution time, scanned rows |
| Statistics | Collect table statistics |
| Parameter binding | Bind actual parameter values |

**Output**:
- `baseline.jsonl` - Performance baseline data

---

### Stage 5: Optimize

| Function | Description |
|----------|-------------|
| Rule engine | Apply built-in optimization rules |
| LLM optimization | Call LLM to generate optimization suggestions |
| Candidate generation | Generate multiple optimization candidates |
| Cost estimation | Estimate post-optimization performance improvement |

**Output**:
- `proposals/` - Optimization suggestions directory

---

### Stage 6: Validate

| Function | Description |
|----------|-------------|
| Semantic verification | Verify semantic equivalence of optimized SQL |
| Performance comparison | Compare pre/post optimization performance |
| Result set verification | Verify result consistency |
| Rollback plan | Generate rollback plan |

**Output**:
- `acceptance.jsonl` - Verification results

---

### Stage 7: Patch

| Function | Description |
|----------|-------------|
| Patch generation | Generate MyBatis XML patch |
| User confirmation | Wait for user confirmation |
| Backup original file | Backup original XML |
| Apply patch | Apply optimization suggestions to XML |

**Output**:
- `patches/` - Patch file directory

---

## 5. CLI Commands

| Command | Function | Typical Usage |
|---------|----------|---------------|
| `validate-config` | Validate config file and DB connectivity | `sqlopt-cli validate-config --config sqlopt.yml` |
| `run` | Execute full V8 optimization flow from start | `sqlopt-cli run --config sqlopt.yml` |
| `resume` | Resume interrupted run | `sqlopt-cli resume --run-id <run-id>` |
| `status` | View current run status | `sqlopt-cli status --run-id <run-id>` |
| `apply` | Apply generated patches | `sqlopt-cli apply --run-id <run-id>` |

### Command Options

- `--config`: Config file path (default: `sqlopt.yml`)
- `--run-id`: Specify run ID
- `--to-stage`: Target stage
- `--sql-key`: Specify SQL key
- `--mapper-path`: Specify mapper file path
- `--max-steps`: Maximum step limit
- `--max-seconds`: Maximum time limit
- `--force` (apply): Force apply patch without confirmation

---

## 6. CLI + Skill Responsibility Split

SQL Optimizer uses a **CLI + Skill** dual-layer architecture:

| Component | Responsibility | Description |
|-----------|---------------|-------------|
| **CLI** | Engineering capabilities | Scan XML, generate branches, build prompts, execute SQL, apply patches |
| **Skill** | AI/LLM capabilities | Call LLM to generate optimization suggestions |

### Complete Flow

```
CLI Discovery → CLI Branching → CLI Pruning → CLI Baseline → Skill Optimize → CLI Validate → CLI Patch
```

---

## 7. Data Directory Structure

```
runs/<run_id>/
├── sqlmap_catalog/              # SQL catalog
│   ├── index.json              # Index file
│   └── <sql_key>.json         # Individual SQL details
├── branches/                    # Branch data
│   └── <sql_key>.json
├── risks/                      # Risk data
│   └── <sql_key>.json
├── baseline/                   # Baseline data
│   └── <sql_key>.json
├── proposals/                  # Optimization suggestions
│   └── <sql_key>/
│       ├── prompt.json
│       └── proposal.json
├── acceptance/                 # Verification results
│   └── <sql_key>.json
├── patches/                   # Patch files
│   └── <sql_key>/
│       └── patch.xml
└── supervisor/                # Run state
    ├── meta.json
    ├── state.json
    └── plan.json
```

---

## 8. Configuration Structure

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql  # or mysql
  dsn: postgresql://user:pass@host:5432/db

llm:
  enabled: true
  provider: opencode_run

stages:
  branching:
    strategy: all_combinations  # all_combinations | pairwise | boundary
    max_branches: 100
  pruning:
    risk_threshold: medium  # high | medium | low
  baseline:
    timeout_ms: 5000
    sample_size: 100
  optimize:
    max_candidates: 3
  validate:
    verify_semantics: true
    verify_performance: true
  patch:
    auto_backup: true
    require_confirm: true
```

---

## 9. Risk Marking Types

| Risk Type | Pattern | Severity |
|-----------|---------|----------|
| `prefix_wildcard` | `'%'+name+'%'` | High |
| `suffix_wildcard_only` | `name+'%'` | Low |
| `concat_wildcard` | `CONCAT('%',name)` | High |
| `function_wrap` | `UPPER(name)` | Medium |

---

## 10. Failure Codes Overview

### Classification Semantics

| Classification | Meaning |
|----------------|---------|
| `retryable` | Can retry and recover |
| `degradable` | Can continue but results are degraded |
| `fatal` | Requires fixing input or logic before continuing |

### Common Failure Codes

**Validate Stage**:
| Code | Classification | Default Action |
|------|---------------|----------------|
| `VALIDATE_DB_UNREACHABLE` | degradable | Retry with delay |
| `VALIDATE_PARAM_INSUFFICIENT` | degradable | Skip parameter validation |
| `VALIDATE_PERF_NOT_IMPROVED` | degradable | Continue without performance improvement |
| `VALIDATE_SEMANTIC_ERROR` | degradable | Mark as failed, continue to next |
| `VALIDATE_EQUIVALENCE_MISMATCH` | fatal | Stop validation for this SQL |
| `VALIDATE_TIMEOUT` | retryable | Retry with extended timeout |

**Patch Stage**:
| Code | Classification | Default Action |
|------|---------------|----------------|
| `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` | degradable | Skip dynamic statement |
| `PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE` | degradable | Skip fragment with include |
| `PATCH_TEMPLATE_MATERIALIZATION_MISSING` | degradable | Do not auto-patch |
| `PATCH_FRAGMENT_LOCATOR_AMBIGUOUS` | degradable | Skip ambiguous locator |
| `PATCH_GENERATION_ERROR` | retryable | Retry patch generation |

**Runtime / Global**:
| Code | Classification | Default Action |
|------|---------------|----------------|
| `RUNTIME_STAGE_TIMEOUT` | retryable | Retry current stage |
| `RUNTIME_RETRY_EXHAUSTED` | retryable | Abort run |
| `RUNTIME_SCHEMA_VALIDATION_FAILED` | fatal | Stop execution |
| `UNSUPPORTED_PLATFORM` | fatal | Abort |

---

## 11. Supported Databases

| Database | Supported Versions | Special Restrictions |
|----------|-------------------|---------------------|
| PostgreSQL | All versions | None |
| MySQL | 5.6+ | MariaDB not supported |

---

## 12. Quick Start

```bash
# 1. Validate configuration
sqlopt-cli validate-config --config sqlopt.yml

# 2. Run optimization
sqlopt-cli run --config sqlopt.yml

# 3. Check status
sqlopt-cli status --run-id <run-id>

# 4. Resume if interrupted
sqlopt-cli resume --run-id <run-id>

# 5. Apply patches
sqlopt-cli apply --run-id <run-id>
```

---

## 13. Known Limitations

1. MySQL 5.6 does not support `MAX_EXECUTION_TIME`
2. PostgreSQL dialects (e.g., `ILIKE`) are not automatically converted for MySQL
3. Template-level patches require `rewriteMaterialization.replayVerified=true`

---

## 15. V9 Architecture (Current)

V9 simplifies the 7-stage V8 pipeline into 5 stages:

| V9 Stage | V8 Equivalent | Description |
|----------|---------------|-------------|
| Init | Discovery | XML parsing, SQL extraction |
| Parse | Branching + Pruning | Branch expansion, risk detection |
| Recognition | Baseline | EXPLAIN collection, performance baseline |
| Optimize | Optimize + Validate | Rule engine + LLM (iterative) |
| Patch | Patch | XML patch generation |

See [V9 Architecture Overview](./v9-design/V9_ARCHITECTURE_OVERVIEW.md) for details.

---

## 14. Related Documents

- [V8 Summary](V8_SUMMARY.md)
- [V8 Stages Overview](V8_STAGES_OVERVIEW.md)
- [Quick Start](QUICKSTART.md)
- [Installation Guide](INSTALL.md)
- [Troubleshooting](TROUBLESHOOTING.md)
