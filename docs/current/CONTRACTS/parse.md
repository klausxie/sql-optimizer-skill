# 阶段二：Parse（解析阶段）

## 阶段简介
- 输入：InitOutput
- 输出：SQLUnitWithBranches, ParseOutput
- 职责：展开 MyBatis 动态 SQL 标签，生成所有分支，评估风险

## 数据契约

### SQLBranch
单个展开后的 SQL 分支。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path_id | str | 是 | 分支标识，如 branch_0 |
| condition | str|None | 是 | 激活条件描述 |
| expanded_sql | str | 是 | 展开后的完整 SQL |
| is_valid | bool | 是 | 结构是否合法 |
| risk_flags | list[str] | 是 | 风险标记列表 |
| active_conditions | list[str] | 是 | 激活的条件列表 |
| risk_score | float|None | 是 | 风险评分 0.0-1.0+ |
| score_reasons | list[str] | 是 | 评分原因 |
| branch_type | str|None | 是 | null=正常, error=异常, baseline_only=特殊 |

### SQLUnitWithBranches
同一个 SQL Unit 的所有分支。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sql_unit_id | str | 是 | SQL Unit 标识 |
| branches | list[SQLBranch] | 是 | 该 Unit 的所有分支 |

### ParseOutput
顶级输出容器。

| 字段 | 类型 | 说明 |
|------|------|------|
| sql_units_with_branches | list | 所有 SQL Unit 及其分支 |

## 风险标记说明

| 标记 | 说明 | 严重度 |
|------|------|--------|
| select_star | SELECT * | 中 |
| order_by | ORDER BY | 低 |
| group_by | GROUP BY | 中 |
| like_prefix | LIKE '%abc' 无法用索引 | 高 |
| in_clause | IN 子句 | 低 |
| not_in | NOT IN 无法用索引 | 高 |
| pagination | LIMIT/OFFSET 深度分页 | 高 |
| union | UNION 去重合并 | 中 |
| join | JOIN 连接 | 中 |
| subquery | 子查询 | 中 |
| table:{name}:large | 涉及大表 | 高 |
| field_skewed:{col} | 字段数据倾斜 | 高 |
| parse_error:{detail} | 解析异常 | 高 |

## 输出文件清单

| 文件路径 | 内容 | 生成时机 | 用途 |
|----------|------|----------|------|
| runs/{run_id}/parse/units/{unit_id}.json | 单个 Unit 分支数据 | Parse 结束时 | Recognition 输入 |
| runs/{run_id}/parse/units/_index.json | Unit ID 列表 | Parse 结束时 | 索引 |

## 常见问题

### Q: 一个 SQL Unit 有多少分支？
取决于动态标签组合数。N 个 if 标签理论上最多 2^N 个分支。

### Q: risk_score 如何计算？
各风险标记有对应权重分数，risk_score 是所有触发标记的权重之和。