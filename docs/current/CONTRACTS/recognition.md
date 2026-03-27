# Recognition Contracts

Source: `python/sqlopt/contracts/recognition.py`

## Main types

### `PerformanceBaseline`

每个 SQL 分支的性能基准数据。

| Field | Type | Meaning |
|-------|------|---------|
| `sql_unit_id` | `str` | SQL Unit 标识 |
| `path_id` | `str` | 分支标识（如 `branch_0`） |
| `original_sql` | `str` | 替换参数后的可执行 SQL |
| `plan` | `dict \| None` | EXPLAIN 执行计划（字典结构，PostgreSQL/MySQL 格式不同） |
| `estimated_cost` | `float` | planner 估算成本（相对值，PostgreSQL `Total Cost` 或 MySQL `query_cost`） |
| `actual_time_ms` | `float \| None` | 实际执行时间（毫秒），仅 DB 模式 SELECT 查询有值 |
| `rows_returned` | `int \| None` | 返回行数，仅 DB 模式 SELECT 有值 |
| `rows_examined` | `int \| None` | 估算扫描行数，从 plan 树中提取 `Actual Rows` / `Plan Rows` |
| `result_signature` | `dict \| None` | 结果集校验和 `{row_count, sample_size, columns, checksum}` |
| `execution_error` | `str \| None` | 执行异常信息，`None` = 成功 |
| `branch_type` | `str \| None` | 分支类型，从 Parse 阶段传递：`None`（正常）、`"error"`、`"baseline_only"` |

### `RecognitionOutput`

顶级输出容器。

| Field | Type | Meaning |
|-------|------|---------|
| `baselines` | `list[PerformanceBaseline]` | 所有分支的基准数据列表 |

---

## EXPLAIN Plan 格式差异

### PostgreSQL

```json
{
  "Plan": {
    "Node Type": "Seq Scan",
    "Relation Name": "orders",
    "Total Cost": 1234.56,
    "Actual Total Time": 45.67,
    "Actual Rows": 1000
  }
}
```

### MySQL (`EXPLAIN FORMAT=JSON`)

```json
{
  "query_block": {
    "cost_info": {
      "query_cost": "1234.56"
    }
  }
}
```

`estimated_cost` 提取优先级：PostgreSQL `Total Cost` > MySQL `query_cost` > 其他兜底。

---

## Execution Modes

| Mode | 说明 | estimated_cost 来源 |
|------|------|---------------------|
| **DB 模式** | 实际连接数据库执行 `EXPLAIN` | 真实数据库返回 |
| **LLM 模式** | 调用 LLM 生成模拟 EXPLAIN | LLM Provider 模拟 |
| **Mock 模式** | 使用 MockLLMProvider | 启发式生成 |

DB 模式下 SELECT 查询会额外执行实际查询并记录 `actual_time_ms` 和 `result_signature`。

---

## Error Reference

`execution_error` 字段可能值：

| Error | 含义 |
|-------|------|
| `baseline_generation_failed: {detail}` | EXPLAIN 执行失败（SQL 语法错误、无权限等） |
| `query_execution_failed: {detail}` | 实际查询执行失败（连接断开、超时等） |

---

## Output files

| File | 说明 |
|------|------|
| `recognition/units/{unit_id}.json` | Per-Unit 基准数据（主存储） |
| `recognition/units/_index.json` | Unit ID 列表 |
| `recognition/baselines.json` | 兼容性汇总文件（冗余堆积，建议移除） |
