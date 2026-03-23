# Recognition Stage Overview

## 执行摘要
识别完成，共分析 16 个 SQL 执行计划，发现 8 个慢查询和 8 个高成本查询。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| EXPLAIN 分析数 | 16 |
| 成功 | 8 |
| 失败 | 8 |
| 慢查询 (>20ms) | 8 |
| 高成本查询 (>50) | 8 |
| 平均执行时间 | 21.11ms |
| 最长执行时间 | 40.92ms |

## 性能分布

| 执行时间范围 | SQL 数量 | 占比 |
| ------------ | -------- | ---- |
| < 5ms | 0 | 0.0% |
| 5-20ms | 8 | 50.0% |
| 20-100ms | 8 | 50.0% |
| > 100ms | 0 | 0.0% |

## 扫描类型分布

| 扫描类型 | 数量 |
| -------- | ---- |
| Index Scan | 3 |
| Seq Scan | 2 |
| Index Range Scan | 6 |

## 慢查询 TOP 5

| SQL Key | 执行时间 | 扫描行数 | 扫描类型 |
| -------- | -------- | -------- | -------- |
| com.test.mapper.UserMapper.findByEmail#b1 | 21.74ms | 67,298 | Index Scan |
| com.test.mapper.UserMapper.searchUsers#b3 | 31.41ms | 75,982 | Bitmap Heap Scan |
| com.test.mapper.UserMapper.testTwoIf#b5 | 31.22ms | 36,947 | Index Range Scan |

## 数据库平台分布

| 平台 | 数量 | 占比 |
| ---- | ---- | ---- |
| PostgreSQL | 9 | 56.2% |
| MySQL | 7 | 43.8% |

## 下一步建议

1. **Optimize 阶段**: 优先优化慢查询 TOP 5
2. **索引建议**: 为高频查询字段添加索引
3. **SQL 重写**: 消除全表扫描

## 详情
- 基线数据: `recognition/baselines.json`
- 统计数据: `recognition/execution_statistics.json`
- 执行时间阈值: 慢查询 > 20ms, 高成本 > 50
