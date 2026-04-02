# 通用字段说明

## run_id
| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | str | 流水线执行唯一标识，格式 run-YYYYMMDD-HHMMSS |

## sql_unit_id
| 字段 | 类型 | 说明 |
|------|------|------|
| sql_unit_id | str | SQL Unit 稳定标识 |

## path_id
| 字段 | 类型 | 说明 |
|------|------|------|
| path_id | str | 分支标识，如 branch_0 |

## risk_level
| 值 | 说明 |
|----|------|
| HIGH | 高风险 |
| MEDIUM | 中风险 |
| LOW | 低风险 |

## branch_type
| 值 | 说明 |
|----|------|
| null/None | 正常分支 |
| error | 解析/执行异常 |
| baseline_only | 仅基线分支 |

## estimated_cost
估算成本，PostgreSQL Total Cost 或 MySQL query_cost

## actual_time_ms
实际执行时间（毫秒），仅 DB 模式 SELECT 有值

## rows_returned
返回行数

## rows_examined
扫描行数

## execution_error
执行异常，None=成功

## validation_status
passed/failed/skipped

## gain_ratio
性能提升比例，如 0.5 表示提升 50%