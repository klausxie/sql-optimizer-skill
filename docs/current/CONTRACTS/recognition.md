# 阶段三：Recognition（识别阶段）

## 阶段简介
- 输入：ParseOutput
- 输出：RecognitionOutput, PerformanceBaseline
- 职责：执行 EXPLAIN 获取执行计划，收集性能基线

## 数据契约

### PerformanceBaseline
每个分支的性能基准数据。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sql_unit_id | str | 是 | SQL Unit 标识 |
| path_id | str | 是 | 分支标识 |
| original_sql | str | 是 | 可执行的 SQL |
| plan | dict|None | 是 | EXPLAIN 执行计划 |
| estimated_cost | float | 是 | 估算成本 |
| actual_time_ms | float|None | 是 | 实际执行时间（毫秒） |
| rows_returned | int|None | 是 | 返回行数 |
| rows_examined | int|None | 是 | 扫描行数 |
| result_signature | dict|None | 是 | 结果集校验和 |
| execution_error | str|None | 是 | 执行异常，None=成功 |
| branch_type | str|None | 是 | 分支类型 |

### RecognitionOutput
顶级输出容器。

| 字段 | 类型 | 说明 |
|------|------|------|
| baselines | list | 所有分支的基准数据 |

## 执行模式

| 模式 | 说明 |
|------|------|
| DB 模式 | 实际连接数据库执行 EXPLAIN |
| LLM 模式 | 调用 LLM 生成模拟 EXPLAIN |
| Mock 模式 | 使用启发式生成 |

## 错误参考

| 错误格式 | 含义 |
|----------|------|
| baseline_generation_failed:{detail} | EXPLAIN 执行失败 |
| query_execution_failed:{detail} | 实际查询执行失败 |

## 输出文件清单

| 文件路径 | 内容 | 生成时机 | 用途 |
|----------|------|----------|------|
| runs/{run_id}/recognition/units/{unit_id}.json | 单个 Unit 基准 | Recognition 结束时 | Optimize 输入 |
| runs/{run_id}/recognition/units/_index.json | Unit ID 列表 | Recognition 结束时 | 索引 |

## 常见问题

### Q: 什么时候 actual_time_ms 为 null？
非 SELECT 语句或 LLM/Mock 模式下为 null。

### Q: execution_error 不为 null 表示什么？
EXPLAIN 执行失败，如语法错误、表不存在、权限不足等。