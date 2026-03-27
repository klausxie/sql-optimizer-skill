# Parse Contracts

Source: `python/sqlopt/contracts/parse.py`

## Main types

### `SQLBranch`

单个展开后的 SQL 分支。

| Field | Type | Meaning |
|-------|------|---------|
| `path_id` | `str` | 分支标识，如 `branch_0`、`branch_1` |
| `condition` | `str \| None` | 激活条件的可读描述，如 `"status != null AND userId != null"` |
| `expanded_sql` | `str` | 展开后的完整 SQL 文本 |
| `is_valid` | `bool` | 结构是否合法（语法完整、无残缺关键字） |
| `risk_flags` | `list[str]` | 风险标记，如 `["select_star", "order_by", "like_prefix", "join"]` |
| `active_conditions` | `list[str]` | 此分支激活的条件列表 |
| `risk_score` | `float \| None` | 风险评分（0.0 = 无风险，越高越差） |
| `score_reasons` | `list[str]` | 评分原因，如 `["select_star", "table:orders:large", "field_skewed:status"]` |
| `branch_type` | `str \| None` | 分支类型：`None`（正常）、`"error"`（解析失败）、`"baseline_only"`（特殊） |

### `SQLUnitWithBranches`

属于同一个 `sql_unit_id` 的所有分支。

| Field | Type | Meaning |
|-------|------|---------|
| `sql_unit_id` | `str` | SQL Unit 标识 |
| `branches` | `list[SQLBranch]` | 该 Unit 展开出的所有分支 |

### `ParseOutput`

顶级输出容器。

| Field | Type | Meaning |
|-------|------|---------|
| `sql_units_with_branches` | `list[SQLUnitWithBranches]` | 所有 SQL Unit 及其分支列表 |

---

## Risk Flags Reference

由 `risk_scorer.py` 生成的风险标记：

| Flag | 含义 |
|------|------|
| `select_star` | SQL 包含 `SELECT *` |
| `order_by` | SQL 包含 `ORDER BY` |
| `group_by` | SQL 包含 `GROUP BY` |
| `having` | SQL 包含 `HAVING` |
| `like_prefix` | `LIKE` 以通配符开头（如 `LIKE '%abc'`） |
| `in_clause` | 包含 `IN(...)` 子句 |
| `not_in` | 包含 `NOT IN(...)` |
| `exists` | 包含 `EXISTS` |
| `pagination` | 包含 `LIMIT` 或 `OFFSET` |
| `distinct` | 包含 `DISTINCT` |
| `union` | 包含 `UNION` |
| `subquery` | 包含子查询 `SELECT ... FROM (SELECT ...)` |
| `join` | 包含 `JOIN` |
| `function:{name}` | 包含特定函数包裹模式 |
| `table:{name}:large` | 涉及大表（size=large） |
| `table:{name}:medium` | 涉及中等表（size=medium） |
| `field_null_high:{col}` | 字段 null 比例 >10% |
| `field_low_card:{col}` | 字段基数 <10 |
| `field_skewed:{col}` | 字段数据倾斜，top 值 >80% |
| `parse_error:{detail}` | 解析异常，branch_type="error" |

---

## Output files

| File | 说明 |
|------|------|
| `parse/units/{unit_id}.json` | Per-Unit 分支数据（主存储） |
| `parse/units/_index.json` | Unit ID 列表 |
| `parse/sql_units_with_branches.json` | 兼容性汇总文件（冗余堆积，建议移除） |
