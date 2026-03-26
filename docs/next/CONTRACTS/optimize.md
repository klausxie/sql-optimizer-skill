# 阶段 4 契约

## 目标实体

- `OptimizationProposal`
- `OptimizationValidation`
- `AcceptedAction`

## `OptimizationProposal`

```json
{
  "proposal_id": "proposal_x1y2z3",
  "finding_id": "finding_a1b2c3",
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "proposal_type": "sql_rewrite",
  "source": "rule+llm",
  "original_sql": "SELECT ...",
  "optimized_sql": "SELECT ...",
  "index_ddl": [],
  "rationale": "将热点低选择性条件后移，并补充更优排序路径",
  "risk_notes": [
    "需要确认业务允许排序字段调整"
  ]
}
```

## `OptimizationValidation`

```json
{
  "record_type": "optimization_validation",
  "proposal_id": "proposal_x1y2z3",
  "finding_id": "finding_a1b2c3",
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "case_id": "case_hot_value_001",
  "result_equivalent": true,
  "before_execution_ref": "recognition/execution/shards/part-00003.jsonl#447",
  "after_explain_cost": 8842.1,
  "after_avg_time_ms": 97.2,
  "after_rows_examined": 1210,
  "after_result_signature": {
    "row_count": 120,
    "ordered_key_digest": "2ca8b7...",
    "sample_digest": "9f01cc...",
    "ordering_columns": ["id"]
  },
  "gain_ratio": 0.885
}
```

## `AcceptedAction`

```json
{
  "proposal_id": "proposal_x1y2z3",
  "finding_id": "finding_a1b2c3",
  "recommended": true,
  "recommendation_level": "strong",
  "summary": "建议优先实施，测试环境耗时下降 88.5%"
}
```

## 存储布局

```text
optimize/
├── manifest.json
├── _index.json
├── proposals/
│   ├── _index.json
│   └── by_namespace/{namespace}/{statement_id}/{proposal_id}.json
├── validations/
│   ├── _index.json
│   └── shards/part-00001.jsonl
├── accepted_actions.json
└── SUMMARY.md
```
