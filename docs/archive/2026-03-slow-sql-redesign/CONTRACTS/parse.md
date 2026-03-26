# 阶段 2 契约

## 目标实体

- `BranchCandidate`
- `ParameterSlot`
- `BranchPriorityEntry`

## `ParameterSlot`

```json
{
  "param_name": "status",
  "column_name": "status",
  "predicate_type": "eq",
  "allows_null": false,
  "is_collection": false,
  "value_source": "column_distribution"
}
```

## `BranchCandidate`

```json
{
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "branch_type": "static_sampled",
  "expanded_sql": "SELECT ... FROM user WHERE status = #{status} ORDER BY created_at DESC",
  "active_conditions": ["status != null"],
  "inactive_conditions": ["name != null"],
  "coverage_tags": ["single_low_selectivity", "order_by"],
  "parameter_slots": [
    {
      "param_name": "status",
      "column_name": "status",
      "predicate_type": "eq",
      "allows_null": false,
      "is_collection": false,
      "value_source": "column_distribution"
    }
  ],
  "static_risks": [
    "large_table",
    "low_selectivity_predicate",
    "sort_without_index"
  ],
  "static_risk_score": 87.5,
  "priority_tier": "high"
}
```

## `BranchPriorityEntry`

```json
{
  "statement_key": "com.foo.user.UserMapper.search",
  "path_id": "branch_000127",
  "static_risk_score": 87.5,
  "priority_tier": "high",
  "reason_summary": [
    "大表 user",
    "status 低选择性",
    "created_at 排序风险"
  ]
}
```

## 存储布局

```text
parse/
├── manifest.json
├── _index.json
├── units/
│   ├── _index.json
│   └── by_namespace/{namespace}/{statement_id}/
│       ├── statement.json
│       └── branches/
│           ├── _index.json
│           └── {path_id}.json
├── priority_queue/
│   └── top_candidates.json
└── SUMMARY.md
```
