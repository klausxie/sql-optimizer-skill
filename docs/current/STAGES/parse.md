# Parse Stage

## Purpose

Parse 阶段将 MyBatis XML 中的**动态 SQL**（`<if>`, `<choose>`, `<foreach>`, `<bind>`, `<include>`）展开为可独立验证的**分支 SQL**。

一个 SQL Unit 可能产生多个分支，例如：

```xml
<select id="findOrders">
  SELECT * FROM orders
  <if test="status != null">
    WHERE status = #{status}
  </if>
  <if test="userId != null">
    AND user_id = #{userId}
  </if>
</select>
```

展开后得到 4 个分支：
- `branch_0`: `SELECT * FROM orders`（两个条件都为 false）
- `branch_1`: `SELECT * FROM orders WHERE status = #{status}`（只有 status）
- `branch_2`: `SELECT * FROM orders AND user_id = #{userId}`（只有 userId）
- `branch_3`: `SELECT * FROM orders WHERE status = #{status} AND user_id = #{userId}`（两个都有）

---

## Inputs

| File | 内容 |
|------|------|
| `init/sql_units.json` | 从 XML 提取的所有 SQL Unit（id、mapper 文件、原始 SQL 文本） |
| `init/sql_fragments.json` | `<sql id="...">` 片段注册表，供 `<include refid="...">` 引用 |
| `init/table_schemas.json` | 表元数据（表名、大小分类） |
| `init/field_distributions.json` | 字段分布统计（null 比例、去重基数、高频值） |

---

## Process

### 1. Fragment 解析（`<include>` 展开）

从 `sql_fragments.json` 构建 `FragmentRegistry`，解析所有 `<include refid="...">` 引用，将片段内容内联到引用位置。

### 2. 动态标签展开（`<if>`, `<choose>`, `<foreach>`, `<bind>`）

使用 `XMLLanguageDriver` 解析 MyBatis XML AST，再用 `BranchGenerator` 按策略生成条件组合。

#### 分支生成策略（`parse_strategy` 配置）

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| `ladder`（默认） | 逐个添加条件，找到最高风险分支后停止 | 大型项目，优先找最差情况 |
| `all_combinations` | 生成 2^n 个组合（n=条件数） | 小型项目，需要全覆盖 |
| `pairwise` | 成对组合，覆盖所有两两条件交互 | 中型项目 |
| `boundary` | 边界值组合（全 true、全 false、单个 true） | 特定测试场景 |

#### 分支数量限制

`parse_max_branches`（默认 50）限制每个 SQL Unit 最多生成的分支数。超过限制时按策略截断。

### 3. 风险评分

每个分支通过 `SQLDeltaRiskScorer` 计算 `risk_score`（0.0 ~ 最高），并附加 `risk_flags` 和 `score_reasons`。

**评分维度**：

| 维度 | 检查项 | 影响 |
|------|--------|------|
| **SQL 结构** | `JOIN`, `SELECT *`, `ORDER BY`, `GROUP BY`, `HAVING`, `LIKE prefix`, `IN`, `NOT IN`, `EXISTS`, `DISTINCT`, `UNION`, `Subquery` | +0.5~2.0 |
| **分页** | `LIMIT`, `OFFSET` | +0.5 |
| **条件嵌套深度** | 嵌套层数 | +0.25/层 |
| **表大小** | 表 size=large 或 medium | +1.0~2.0 |
| **字段分布** | null 比例 >10%，低基数（<10），数据倾斜（top 值 >80%） | +1.0~2.0 |
| **函数包裹** | `#{...}`, `${...}` 等参数写法 | +0.5 |

### 4. 分支验证

`BranchValidator` 验证展开后的 SQL 是否**结构合法**：
- 关键字完整性（无残缺的 SELECT/FROM/WHERE）
- 括号匹配
- 引号匹配

无效分支标记 `is_valid=False`，但仍保留供人工审查。

### 5. 错误处理

展开失败的 SQL Unit（XML 解析错误、条件评估异常等）生成一个 `branch_type="error"` 的分支，记录 `parse_error:{具体异常}` 到 `score_reasons`，阶段不中断，继续处理其他 Unit。

---

## Outputs

### Per-Unit 文件（主存储）

```
runs/{run_id}/parse/units/{unit_id}.json
runs/{run_id}/parse/units/_index.json
```

### 兼容性文件（冗余堆积，建议移除）

```
runs/{run_id}/parse/sql_units_with_branches.json
```

### 字段说明

#### `SQLBranch`

| 字段 | 含义 |
|------|------|
| `path_id` | 分支标识，如 `branch_0`、`branch_1` |
| `condition` | 条件的可读描述，如 `"status != null AND userId != null"` |
| `expanded_sql` | 展开后的完整 SQL 文本 |
| `is_valid` | 结构是否合法（语法完整、无残缺关键字） |
| `risk_flags` | 风险标记列表，如 `["select_star", "order_by", "like_prefix"]` |
| `active_conditions` | 此分支激活的条件列表 |
| `risk_score` | 风险评分（0.0 = 无风险，越高越差） |
| `score_reasons` | 评分原因列表，如 `["select_star", "table:orders:large", "field_skewed:status"]` |
| `branch_type` | 分支类型：`None`（正常）、`error`（解析失败）、`baseline_only`（特殊） |

---

## Risks（潜在问题）

### 高风险

| 问题 | 描述 | 后果 |
|------|------|------|
| **分支爆炸** | 多个 `<if>` 嵌套时，2^n 组合数指数增长 | 超过 `max_branches` 截断，可能漏掉高风险分支 |
| **`${}` 注入** | `BranchExpander` 不做 SQL 转义，原样保留 `${var}` | 生成的 SQL 不可执行（recognition 会失败） |
| **`#{...}` 参数未绑定** | 展开后 SQL 包含未替换的 `#{}` 占位符 | recognition 阶段执行失败 |
| **Fragment 循环依赖** | `<include>` 形成 A→B→A 循环 | 栈溢出或无限循环 |

### 中风险

| 问题 | 描述 | 后果 |
|------|------|------|
| **空分支** | 条件全部为 false 时生成空 SQL | `is_valid=False`，但仍写入输出 |
| **歧义 choose** | `<choose>` 只有 `<when>` 没有 `<otherwise>`，且所有 when 都为 false | 生成空 SQL 分支 |
| **`foreach` 展开** | 大列表 `foreach` 可能生成超长 SQL | 超过数据库 `max_allowed_packet` |
| **XML 实体未解码** | `&lt;`, `&gt;` 等实体在展开时未正确处理 | 生成非法 SQL |

### 低风险

| 问题 | 描述 | 后果 |
|------|------|------|
| **风险评分依赖元数据** | 无 `table_schemas.json` 时评分降低 | 漏检某些大表风险 |
| **跨文件 include** | `FragmentRegistry` 仅解析本文件内的 include | 跨 mapper 文件的 include 可能失败 |

---

## 已知限制

1. **不执行 SQL**：Parse 阶段只做静态展开，不连接数据库验证
2. **OGNL 表达式不求值**：`<if test="status != null">` 中的表达式只做文本替换，不实际求值
3. **`foreach` 仅文本展开**：`foreach` 生成的 IN 子句是占位符而非实际值列表
4. **策略截断不确定**：分支超过 `max_branches` 时截断，不保证最高风险分支被保留（`ladder` 策略会尽量先找高风险的）

---

## 相关文件

- 核心实现：`python/sqlopt/stages/parse/stage.py`
- 分支展开：`python/sqlopt/stages/parse/branch_expander.py`
- 分支生成：`python/sqlopt/stages/branching/branch_generator.py`
- 风险评分：`python/sqlopt/stages/branching/risk_scorer.py`
- 契约定义：`python/sqlopt/contracts/parse.py`
- 配置项：`python/sqlopt/common/config.py` 中的 `parse_strategy`、`parse_max_branches`
