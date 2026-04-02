# SQL Optimizer Skill - 数据契约字段解释

## 阶段一：Init（初始化阶段）

### InitOutput

| 字段 | 类型 | 说明 |
|------|------|------|
| `sql_units` | `List[SQLUnit]` | 从 mapper XML 中提取的所有 SQL 单元 |
| `run_id` | `str` | 唯一运行标识符，格式：`run-YYYYMMDD-HHMMSS` |
| `timestamp` | `str` | ISO 格式时间戳 |
| `sql_fragments` | `List[SQLFragment]` | 可复用的 SQL 片段（`<sql id="">`） |
| `table_schemas` | `Dict[str, TableSchema]` | 表名 → 表结构映射 |
| `xml_mappings` | `XMLMapping \| None` | 所有 XML 文件的完整映射结构 |
| `table_relationships` | `List[TableRelationship]` | 表关系（从 JOIN/WHERE 推断） |
| `table_hotspots` | `Dict[str, TableHotspot]` | 表热度/风险 profile |

---

### SQLUnit

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | 唯一标识符 |
| `mapper_file` | `str` | 相对于 `project_root` 的 XML 文件路径 |
| `sql_id` | `str` | MyBatis `<select\|insert\|update\|delete>` 的 `id` 属性 |
| `sql_text` | `str` | 原始 SQL 文本 |
| `statement_type` | `str` | 语句类型：`select` / `insert` / `update` / `delete` |

---

### SQLFragment

| 字段 | 类型 | 说明 |
|------|------|------|
| `fragment_id` | `str` | 片段唯一标识 |
| `xml_path` | `str` | XML 文件路径 |
| `start_line` | `int` | 起始行号 |
| `end_line` | `int` | 结束行号 |
| `xml_content` | `str` | 原始 XML 内容 |

---

### TableSchema

| 字段 | 类型 | 说明 |
|------|------|------|
| `columns` | `List[Dict]` | 列信息列表，每项含 `name`, `type`, `nullable` 等 |
| `indexes` | `List[Dict]` | 索引信息列表 |
| `statistics` | `Dict` | 表统计信息（行数、大小等） |

---

### TableRelationship

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_table` | `str` | 源表名 |
| `target_table` | `str` | 目标表名 |
| `via_column` | `str` | 连接列（源） |
| `target_column` | `str` | 连接列（目标） |
| `direction` | `str` | 方向：`one_to_one` / `one_to_many` / `many_to_many` |
| `confidence` | `float` | 推断置信度 0.0-1.0 |
| `sql_keys` | `List[str]` | 涉及此关系的 SQL 单元 ID 列表 |
| `join_condition` | `str` | 原始 JOIN 条件文本 |
| `is_explicit_join` | `bool` | 是否为显式 `JOIN` 关键字（否则从 WHERE 推断） |

---

### TableHotspot

| 字段 | 类型 | 说明 |
|------|------|------|
| `table_name` | `str` | 表名 |
| `incoming_ref_count` | `int` | 被引用次数（作为 JOIN 目标） |
| `outgoing_ref_count` | `int` | 引用他人次数（作为 JOIN 源） |
| `co_occurrence_tables` | `List[str]` | 常一起出现的表 |
| `hotspot_score` | `float` | 热度得分（综合计算） |
| `risk_level` | `str` | 风险等级：`high` / `medium` / `low` |
| `sql_keys` | `List[str]` | 使用该表的 SQL 单元 ID 列表 |

---

## 阶段二：Parse（解析阶段）

### ParseOutput

| 字段 | 类型 | 说明 |
|------|------|------|
| `sql_units_with_branches` | `List[SQLUnitWithBranches]` | 所有 SQL 单元及其展开的分支 |
| `run_id` | `str` | 唯一运行标识符 |
| `strategy` | `str` | 采样策略：`all_combinations` / `each` / `boundary` / `ladder` |
| `max_branches` | `int` | 最大分支上限（0=无限制） |

---

### SQLUnitWithBranches

| 字段 | 类型 | 说明 |
|------|------|------|
| `sql_unit_id` | `str` | SQL 单元唯一标识符（格式：`com.test.mapper.XxxMapper.yyy`） |
| `branches` | `List[SQLBranch]` | 该单元的所有分支 |
| `theoretical_branches` | `int` | 理论分支数（2^n，n=IF条件数）；超过 1,000,000 标记为极端单元 |

---

### SQLBranch

| 字段 | 类型 | 说明 |
|------|------|------|
| `path_id` | `str` | 分支路径 ID（格式：`unit_id/path_0`） |
| `condition` | `str \| None` | 触发该分支的条件表达式 |
| `expanded_sql` | `str` | 展开后的完整 SQL 文本 |
| `is_valid` | `bool` | 分支是否有效（`false`=不可达） |
| `risk_flags` | `List[str]` | 风险标志列表（见下方风险标志说明） |
| `active_conditions` | `List[str]` | 该分支激活的所有条件 |
| `risk_score` | `float \| None` | 综合风险评分（0.0-1.0+），越高越危险 |
| `score_reasons` | `List[str]` | 风险得分原因（与 `risk_flags` 相同） |
| `branch_type` | `str \| None` | 分支类型：`normal` / `baseline_only` / `error` |
| `risk_factors` | `List[Dict]` | 详细风险因素列表，每项含 `flag`, `weight`, `severity` |
| `risk_level` | `str \| None` | 风险等级：`HIGH` / `MEDIUM` / `LOW` |

---

### 风险标志说明

| 标志 | 说明 | 严重程度 |
|------|------|----------|
| `SELECT_STAR` | 使用了 `SELECT *` | CRITICAL |
| `LIKE_PREFIX` | `LIKE 'xxx%'` 前缀匹配 | CRITICAL |
| `JOIN_WITHOUT_INDEX` | JOIN 列无索引 | CRITICAL |
| `SUBQUERY` | 包含子查询 | WARNING |
| `DISTINCT` | 使用 `DISTINCT` | WARNING |
| `UNION_WITHOUT_ALL` | `UNION` 无 `ALL` | WARNING |
| `NOT_IN_LARGE_TABLE` | `NOT IN` 大表 | WARNING |
| `ACTIVE_CONDITION` | 活跃条件数量（仅供参考，非风险标志） | INFO |

---

## 阶段三：Recognition（识别阶段）

### RecognitionOutput

| 字段 | 类型 | 说明 |
|------|------|------|
| `baselines` | `List[PerformanceBaseline]` | 所有分支的性能基线 |
| `run_id` | `str` | 唯一运行标识符 |

---

### PerformanceBaseline

| 字段 | 类型 | 说明 |
|------|------|------|
| `sql_unit_id` | `str` | SQL 单元 ID |
| `path_id` | `str` | 分支路径 ID |
| `original_sql` | `str` | 原始 SQL 文本 |
| `plan` | `Dict \| None` | EXPLAIN 输出（执行计划） |
| `estimated_cost` | `float` | 优化器估算的代价 |
| `actual_time_ms` | `float \| None` | 实际执行时间（毫秒） |
| `rows_returned` | `int \| None` | 返回行数 |
| `rows_examined` | `int \| None` | 扫描行数 |
| `result_signature` | `Dict \| None` | 结果签名（用于去重） |
| `execution_error` | `str \| None` | 执行错误信息（如果有） |
| `branch_type` | `str \| None` | 分支类型（继承自 Parse 阶段） |

---

## 阶段四：Optimize（优化阶段）

### OptimizationProposal

| 字段 | 类型 | 说明 |
|------|------|------|
| `sql_unit_id` | `str` | SQL 单元 ID |
| `path_id` | `str \| None` | 分支路径 ID（`None`=整单元优化） |
| `original_sql` | `str` | 原始 SQL |
| `optimized_sql` | `str` | LLM 建议的优化 SQL |
| `rationale` | `str` | 优化理由 |
| `expected_improvement` | `str \| None` | 预期改进 |
| `risk_assessment` | `str \| None` | 风险评估 |

---

## 阶段五：Result（结果阶段）

### ResultOutput

| 字段 | 类型 | 说明 |
|------|------|------|
| `proposals` | `List[OptimizationProposal]` | 所有优化建议 |
| `patches` | `List[Patch]` | 要应用的补丁 |
| `run_id` | `str` | 唯一运行标识符 |

---

### Patch

| 字段 | 类型 | 说明 |
|------|------|------|
| `sql_unit_id` | `str` | SQL 单元 ID |
| `path_id` | `str \| None` | 分支路径 ID |
| `original_xml` | `str` | 原始 XML 片段 |
| `patched_xml` | `str` | 补丁后的 XML 片段 |
| `diff` | `str` | Unified diff 格式 |

---

## 风险评分公式

```
综合风险分 = Σ(风险标志权重 × 风险严重程度系数)

系数：
- CRITICAL: 1.0
- WARNING: 0.6
- INFO: 0.3
- ACTIVE_CONDITION: 0.1

风险等级：
- HIGH: 风险分 ≥ 0.8
- MEDIUM: 风险分 0.5 - 0.8
- LOW: 风险分 < 0.5
```

---

## 采样策略说明

| 策略 | 说明 | 分支数 |
|------|------|--------|
| `all_combinations` | 全组合（2^n） | 指数增长 |
| `each` | 每条件单独 true/false | n×2 |
| `boundary` | 极值（全 true/全 false/各一 false） | n+1 |
| `ladder` | 智能加权采样 | 可控 |

---

## 文件路径约定

- 所有 `mapper_file` 字段相对于 `project_root`
- 所有文件路径使用正斜杠 `/`
- SQLUnit ID 格式：`{mapper_file_relative_path}:{sql_id}`

示例：
```
com/test/mapper/OrderMapper.xml:findByStatus
```
