# 公共契约

## 稳定 ID

### `statement_key`

格式：

```text
{namespace}.{statement_id}
```

示例：

```text
com.foo.user.UserMapper.findById
```

### `path_id`

格式：

```text
branch_{6-digit}
```

示例：

```text
branch_000127
```

### `case_id`

格式：

```text
case_{strategy}_{sequence}
```

示例：

```text
case_hot_value_001
```

### `finding_id`

格式：

```text
finding_{statement_hash}_{path_hash}_{case_hash}
```

### `proposal_id`

格式：

```text
proposal_{finding_hash}_{sequence}
```

## `StageManifest`

```json
{
  "schema_version": "next-v1",
  "run_id": "run-20260326-220000",
  "stage_name": "recognition",
  "status": "completed",
  "started_at": "2026-03-26T22:00:00Z",
  "completed_at": "2026-03-26T22:15:00Z",
  "totals": {
    "statements": 1200,
    "branches": 8400,
    "cases": 36000,
    "findings": 620
  },
  "index_file": "_index.json"
}
```

## `PartitionRef`

```json
{
  "partition_key": "com.foo.user",
  "entity": "branch_candidates",
  "item_count": 320,
  "index_file": "units/by_namespace/com.foo.user/_index.json"
}
```

## `EntityRef`

```json
{
  "id": "branch_000127",
  "file": "units/by_namespace/com.foo.user/findById/branches/branch_000127.json"
}
```

## `ResultSignature`

用于比较优化前后结果是否一致：

```json
{
  "row_count": 120,
  "ordered_key_digest": "2ca8b7...",
  "sample_digest": "9f01cc...",
  "ordering_columns": ["id"]
}
```

## `PlanFlags`

```json
{
  "full_table_scan": true,
  "filesort": false,
  "temporary_table": false,
  "hash_aggregate": true,
  "nested_loop_amplification": false
}
```

## `RootCauseHit`

```json
{
  "code": "leading_wildcard_like",
  "severity": "high",
  "message": "LIKE 以前导百分号开头，无法使用常规索引前缀"
}
```

## 高基数 JSONL 记录公共字段

所有 JSONL 记录建议统一包含：

```json
{
  "record_type": "execution_baseline",
  "run_id": "run-20260326-220000",
  "statement_key": "com.foo.user.UserMapper.findById",
  "path_id": "branch_000127",
  "case_id": "case_hot_value_001"
}
```

## 分区规则

- statement 相关实体：按 namespace 分区
- table 相关实体：按 table 分区
- finding：按 severity + namespace 双层分区
- 高基数记录：按 shard 分片，并在 shard index 中标识 namespace 范围
