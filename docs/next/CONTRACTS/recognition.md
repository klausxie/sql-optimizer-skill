# 阶段 3 契约

## 目标实体

- `ParameterCase`
- `ExplainBaseline`
- `ExecutionBaseline`
- `SlowSQLFinding`

## `ParameterCase`

```json
{
  "record_type": "parameter_case",
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "case_id": "case_hot_value_001",
  "generation_strategy": "hot_value",
  "parameter_values": {
    "status": "ACTIVE"
  },
  "expected_selectivity": 0.88,
  "source_columns": ["status"]
}
```

## `ExplainBaseline`

```json
{
  "record_type": "explain_baseline",
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "case_id": "case_hot_value_001",
  "plan_engine": "postgresql",
  "estimated_cost": 124552.3,
  "estimated_rows": 16200000,
  "plan_flags": {
    "full_table_scan": true,
    "filesort": false,
    "temporary_table": false,
    "hash_aggregate": false,
    "nested_loop_amplification": false
  },
  "plan_json": {}
}
```

## `ExecutionBaseline`

```json
{
  "record_type": "execution_baseline",
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "case_id": "case_hot_value_001",
  "run_count": 5,
  "avg_time_ms": 842.5,
  "p95_time_ms": 901.2,
  "rows_returned": 120,
  "rows_examined": 18500000,
  "result_signature": {
    "row_count": 120,
    "ordered_key_digest": "2ca8b7...",
    "sample_digest": "9f01cc...",
    "ordering_columns": ["id"]
  }
}
```

## `SlowSQLFinding`

```json
{
  "finding_id": "finding_a1b2c3",
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "case_id": "case_hot_value_001",
  "is_slow": true,
  "severity": "high",
  "impact_score": 91.4,
  "confidence": 0.93,
  "root_causes": [
    {
      "code": "low_selectivity_predicate",
      "severity": "high",
      "message": "status 字段热点值占比过高"
    },
    {
      "code": "full_table_scan",
      "severity": "high",
      "message": "执行计划显示顺序扫描"
    }
  ],
  "explain_ref": "explain/shards/part-00001.jsonl#128",
  "execution_ref": "execution/shards/part-00003.jsonl#447",
  "optimization_ready": true
}
```

## 存储布局

高基数测量数据采用 JSONL 分片：

```text
recognition/
├── manifest.json
├── _index.json
├── cases/
│   ├── _index.json
│   └── shards/part-00001.jsonl
├── explain/
│   ├── _index.json
│   └── shards/part-00001.jsonl
├── execution/
│   ├── _index.json
│   └── shards/part-00001.jsonl
├── findings/
│   ├── _index.json
│   └── by_severity/{severity}/{finding_id}.json
├── top_slow_sql.json
└── SUMMARY.md
```
