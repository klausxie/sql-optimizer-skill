# Parse Stage Overview

## 执行摘要
解析完成，共生成 86 个分支路径，检测到 28 个风险。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| SQL 单元数 | 16 |
| 分支路径总数 | 86 |
| 含分支的单元数 | 16 |
| 静态 SQL 数 | 0 |
| 风险总数 | 28 |
| 🔴 高风险 | 10 |
| 🟡 中风险 | 14 |
| 🟢 低风险 | 4 |

## 分支分布

| SQL 单元 | 分支数 | 类型 |
| -------- | ------ | ---- |
| UserMapper.findById | 3 | 动态 |
| UserMapper.findByEmail | 2 | 动态 |
| UserMapper.searchUsers | 7 | 复杂 |
| OrderMapper.findOrders | 4 | 动态 |

## 风险类型分布

| 风险类型 | 高 | 中 | 低 |
| -------- | -- | -- | -- |
| PREFIX_WILDCARD | 10 | 0 | 0 |
| MISSING_LIMIT | 0 | 14 | 0 |
| FULL_TABLE_SCAN | 0 | 0 | 4 |

## 问题与风险

### 🔴 高风险 (需立即处理)
- PREFIX_WILDCARD: 使用 `LIKE '%keyword%'` 无法使用索引
- FULL_TABLE_SCAN: 全表扫描影响性能

### 🟡 中风险 (建议优化)
- MISSING_LIMIT: 缺少 LIMIT 子句
- N_PLUS_1: 可能存在 N+1 查询问题

### 🟢 低风险 (可接受)
- SUFFIX_WILDCARD: 后缀通配符可使用索引

## 下一步建议

1. **Recognition 阶段**: 对所有分支执行 EXPLAIN 收集性能基线
2. **Optimize 阶段**: 优先处理高风险 SQL
3. **建议关注**: findByEmail, searchUsers 等高频查询

## 详情
- 分支数据: `parse/sql_units_with_branches.json`
- 风险数据: `parse/risks.json`
- 平均分支数: 5.4
