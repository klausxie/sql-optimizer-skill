# 阶段四：Optimize（优化阶段）

## 阶段简介
- 输入：ParseOutput + RecognitionOutput
- 输出：OptimizeOutput, OptimizationProposal
- 职责：基于风险和性能基线生成优化建议

## 数据契约

### OptimizationProposal
优化提案。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sql_unit_id | str | 是 | 上游 SQL Unit ID |
| path_id | str | 是 | 上游分支 ID |
| original_sql | str | 是 | 优化前 SQL |
| optimized_sql | str | 是 | 优化后 SQL |
| rationale | str | 是 | 优化理由 |
| confidence | float | 是 | 置信度 0.0-1.0 |
| before_metrics | dict|None | 是 | 优化前指标 |
| after_metrics | dict|None | 是 | 优化后指标 |
| result_equivalent | bool | 是 | 结果是否等价 |
| validation_status | str | 是 | passed/failed/skipped |
| validation_error | str|None | 是 | 验证失败详情 |
| gain_ratio | float|None | 是 | 性能提升比例 |

### OptimizeOutput
顶级输出容器。

| 字段 | 类型 | 说明 |
|------|------|------|
| proposals | list | 所有优化提案 |

## 输出文件清单

| 文件路径 | 内容 | 生成时机 | 用途 |
|----------|------|----------|------|
| runs/{run_id}/optimize/proposals.json | 所有提案 | Optimize 结束时 | Result 输入 |
| runs/{run_id}/optimize/units/{unit_id}.json | 单个 Unit 提案 | Optimize 结束时 | Result per-unit |

## 常见问题

### Q: 什么时候 gain_ratio 为 null？
validation_status 为 skipped 或 failed 时。

### Q: confidence 如何确定？
由 LLM Provider 返回，Mock 通常返回 0.5-0.9。