# DECISION-007: Parse Stage (Phase 2) Code Audit

**Date:** 2026-04-03
**Auditor:** Oracle (via Sisyphus)
**Stage:** Parse Stage / Branching Module
**Status:** Open (issues identified)

---

## 背景

Parse Stage 是 5 阶段流水线的第 2 阶段，负责将 MyBatis XML 动态 SQL 标签展开为可执行的 SQL 分支。其核心诉求是：**尽可能筛选出可能的慢 SQL 分支**。

本次审计旨在发现可能导致慢 SQL 漏检的代码缺陷和改进空间。

---

## 总体评估

**架构评级:** 良好 ✅

Parse Stage 采用"维度提取 → 渲染 → 评分"的两阶段设计，MyBatis 动态 SQL 标签覆盖完整。问题主要集中在**规则覆盖度**和 **Ladder 采样广度**，均为可修复的工程问题。

**预估慢 SQL 检测率:** ~75-85%

| 场景 | 检测率 |
|------|--------|
| 简单 SQL (≤8 条件) | ~90-95% |
| 复杂动态 SQL (10+ 条件, ladder 模式) | ~70-80% |
| Foreach + 函数包装列 | ~50-60% |

---

## 🔴 Critical Finding 1: Ladder 策略跳过高风险中间组合

**严重程度:** Critical
**影响:** 可能漏检需要 5+ 条件组合才触发的慢 SQL
**预估修复工作量:** Short (1-2h)

### 问题描述

`planner.py` 的 `RiskGuidedLadderPlanner.generate()` 只生成以下组合：

1. 空组合（all-false baseline）
2. Top N 单条件
3. Top 12 的配对 (pairs)
4. Top 8 的三元组 (triples)
5. Top 8 的四元组 (quads)

### 盲点分析

当 mapper 中有 10+ 个 `<if>` 条件时，Ladder 策略**永远不会生成 5+ 条件的组合**。然而，某些慢 SQL 恰好需要多个特定条件同时激活才能触发全表扫描，例如：

- 缺失索引 + LIKE 前缀 + ORDER BY + 无 LIMIT 组合

### 根因

Ladder planner 按 `score` 降序排序选择条件，但 Phase 1 评分基于**维度文本**（渲染前），而非实际渲染的 SQL。例如：

```xml
<if test="status != null">AND status IS NOT NULL</if>
```

此条件在 Phase 1 评分低，但实际渲染出的 `IS NOT NULL` 在与其他 5+ 条件组合时可能导致索引失效。

### 建议修复

在现有 Ladder 生成后，添加**"补全扫描"(complement sweep)**：

```python
def _generate_complement_sweep(self, dimensions: list[BranchDimension], budget: int) -> list[ConditionCombination]:
    """Generate 3-5 random combinations that include at least one 
    condition NOT in the top-12 candidates. Minimal cost, catches 
    combinatorial risk."""
    top_12 = set(d.score for d in sorted(dimensions, key=lambda d: -d.score)[:12])
    non_top = [d for d in dimensions if d not in top_12]
    # Generate random combos mixing top + non-top conditions
```

---

## 🔴 Critical Finding 2: `<bind>` / `VarDeclSqlNode` 条件在 Ladder 模式下缺失

**严重程度:** Critical
**影响:** 假阳性 risk flags 污染风险评分
**预估修复工作量:** Short (1-2h)

### 问题描述

`branch_generator.py` 第 377-381 行：

```python
if isinstance(sql_node, VarDeclSqlNode):
    return [[f"bind:{sql_node.name}"]]
```

每个 `<bind>` 标签无条件地将 `bind:pattern` 添加为活跃条件。这本身是正确的——`<bind>` 确实总是执行。

**但问题在于：** `DimensionExtractor` 根本不将 `VarDeclSqlNode` 提取为 dimension。因此在 Ladder 模式下，条件组合时从不考虑 `bind:*`，但渲染时它们仍然被添加。

### 影响

在 `_collect_bind_expressions()` 中，bind 表达式的风险分析（如 `prefix_wildcard`）对**所有分支**执行，不管父 `<if>` 条件是否激活。对于嵌套 bind：

```xml
<if test="search != null">
    <bind name="pattern" value="'%' + search + '%'"/>
</if>
```

当 `<if test="search != null">` 未激活时，bind 表达式仍被收集并标记风险。

### 建议修复

在 `_collect_bind_expressions()` 中传播父条件上下文，只收集**父 `<if>` 节点全部激活**的 bind 表达式。

---

## 🔴 Critical Finding 3: `FUNCTION_ON_INDEXED_COLUMN` Phase 2 规则缺失

**严重程度:** Critical
**影响:** 生产环境最常见的慢 SQL 原因无法被检测
**预估修复工作量:** Quick (<30min)

### 问题描述

`risk_assessment.py` 中 `FUNCTION_ON_INDEXED_COLUMN` 被列为 **CRITICAL** 级别，但在 `rules.py` 的 Phase 2 规则中**根本没有实际检测规则**。

Phase 1 的 `dim_regex_function_wrap` 只能捕获维度文本（渲染前）中的函数包装。但大多数 MyBatis 代码直接将函数写在 SQL 中：

```xml
<if test="name != null">AND UPPER(name) LIKE CONCAT('%', #{name}, '%')</if>
```

这类模式在 Phase 2 完全漏检。

### 根因

Phase 2 规则基于**渲染后的实际 SQL** 检测风险，但当前 Phase 2 没有针对函数包装列的检测规则。

### 建议修复

添加 Phase 2 规则：

```python
rules["sql_regex_function_on_column"] = RiskRule(
    name="sql_regex_function_on_column",
    signal="regex",
    pattern=r"(?:UPPER|LOWER|TRIM|SUBSTRING|SUBSTR|DATE|YEAR|MONTH|DAY|"
            r"DATE_FORMAT|EXTRACT|CAST|CONVERT|COALESCE|IFNULL|NVL|ISNULL|"
            r"ABS|ROUND|FLOOR|CEIL|LENGTH|CHAR_LENGTH)\s*\(\s*\w+\s*\)",
    weight=3.0,
    phase=2,
    reason_tag="function_on_column",
)
```

并映射到 `_PHASE2_TO_FACTOR_CODE` 中的 `FUNCTION_ON_INDEXED_COLUMN`。

---

## 🟡 Significant Finding 4: `ChooseSqlNode` 在 `all_combinations` 模式下 mutex 过滤缺失

**严重程度:** Significant
**影响:** 生成错误的分支，risk 评分不准确
**预估修复工作量:** Short (1h)

### 问题描述

`_enumerate_valid_condition_combinations` 不检查 `mutex_group`，导致在 `all_combinations` 模式下，可能生成激活同一 `choose` 节点下多个 `when` 条件的分支。

但 `ChooseSqlNode.apply()` 实现的是"首个匹配优先"语义，只会渲染第一个匹配的 when 条件。结果是：

- `active_conditions` 显示两个条件都激活
- 但 SQL 只反映其中一个

### 影响

在 `all_combinations` 模式下，risk 评分基于 `active_conditions` 而非实际渲染的 SQL，导致假阳性和漏检。

### 建议修复

在 `_enumerate_valid_condition_combinations` 中添加 `mutex_group` 过滤逻辑：

```python
# Filter out combinations that activate mutually exclusive conditions
valid_combos = []
for combo in candidates:
    if self._has_mutex_conflict(combo):
        continue
    valid_combos.append(combo)
```

---

## 🟡 Significant Finding 5: 错误 Fallback 标记 `is_valid=True`

**严重程度:** Significant
**影响:** 垃圾 SQL 流入 Recognition 阶段产生误导性 EXPLAIN
**预估修复工作量:** Quick (<5min)

### 问题描述

`branch_expander.py` 第 161-177 行：

```python
except (AttributeError, ValueError, RuntimeError, TypeError, xml.etree.ElementTree.ParseError) as e:
    return [ExpandedBranch(
        path_id="default",
        condition=None,
        expanded_sql=self._strip_xml_tags(sql_text),
        is_valid=True,  # ← BUG
    )]
```

XML 解析失败时，回退的 SQL 几乎肯定包含原始文本片段、OGNL 表达式、`#{}` 占位符等畸形内容。但被标记为 `is_valid=True`，流入 Recognition 阶段。

### 建议修复

```python
is_valid=False,
risk_flags=["parse_error"],
```

---

## 🟡 Special Finding: `IN_CLAUSE_LARGE` 永远不会触发

**严重程度:** Significant
**影响:** `foreach` 生成的分支无法触发此风险检测
**预估修复工作量:** Quick (<30min)

### 问题描述

`foreach` 的 `sample_size=2` 配置只产生最多 8 个 items：

```python
large_bucket = [f"item_{i}" for i in range(sample_size)]  # sample_size=2 → 8 items
```

但 Phase 2 规则要求 `{10,}` 个逗号分隔的值才能触发 `IN_CLAUSE_LARGE`：

```python
rules["sql_regex_in_many"] = RiskRule(
    pattern=r"IN\s*\(\s*\d+(?:\s*,\s*\d+){10,}\s*\)",  # 要求 10+ 个值
)
```

### 修复建议

二选一：
1. 降低 regex 阈值到 `{5,}`
2. 将 `large` bucket 的 `sample_size` 调整到 12

---

## 风险检测覆盖度评估

| 风险因子 | 检测状态 | 阶段 | 盲点 |
|---------|---------|------|------|
| LIKE_PREFIX | ✅ 完整 | Phase 2 + bind analysis | - |
| FUNCTION_ON_INDEXED_COLUMN | ⚠️ 部分 | Phase 1 仅 | **缺少 Phase 2 规则** |
| NO_INDEX_ON_FILTER | ✅ 完整 | 元数据收集 | 依赖 schema metadata 质量 |
| NOT_IN_LARGE_TABLE | ✅ 完整 | Phase 2 | - |
| DEEP_OFFSET | ✅ 完整 | Phase 2 | - |
| SUBQUERY | ✅ 完整 | Phase 2 | - |
| JOIN_WITHOUT_INDEX | ⚠️ 基础 | Phase 2 关键字检测 | 不交叉验证实际索引 |
| IN_CLAUSE_LARGE | ⚠️ 失效 | Phase 2 | **Foreach 永远不触发** |
| UNION_WITHOUT_ALL | ✅ 完整 | Phase 2 | - |
| SKEWED_DISTRIBUTION | ✅ 完整 | 字段分布收集 | 依赖数据质量 |
| SELECT_STAR | ✅ 完整 | Phase 2 | - |
| DISTINCT | ✅ 完整 | Phase 2 | - |
| HIGH_NULL_RATIO | ✅ 完整 | 字段分布收集 | 依赖数据质量 |
| LOW_CARDINALITY | ✅ 完整 | 字段分布收集 | 依赖数据质量 |

---

## 改进建议汇总

| # | 建议 | 工作量 | 优先级 |
|---|------|--------|--------|
| 1 | 添加 Phase 2 `FUNCTION_ON_INDEXED_COLUMN` 规则 | Quick (<30min) | **P0** |
| 2 | Ladder 后添加随机组合补充扫描 | Short (1-2h) | **P0** |
| 3 | 错误 fallback 改为 `is_valid=False` | Quick (<5min) | **P1** |
| 4 | Bind 表达式收集限定到活跃祖先条件 | Short (1-2h) | **P1** |
| 5 | `all_combinations` 模式添加 mutex_group 过滤 | Short (1h) | **P1** |
| 6 | 修复 `IN_CLAUSE_LARGE` 触发条件 | Quick (<30min) | **P2** |
| 7 | 添加 Phase 2 `OR` 条件检测 | Quick (<30min) | **P2** |

---

## 结论

Parse Stage 架构设计良好，核心问题是：
1. **Phase 2 规则缺失** — `FUNCTION_ON_INDEXED_COLUMN` 作为 CRITICAL 级别却无 Phase 2 检测
2. **Ladder 采样盲区** — 组合数超过 4 时存在漏检风险
3. **IN_CLAUSE_LARGE 永不触发** — 实际使用中无法捕获 foreach 生成的慢 SQL

以上问题均可在不改变架构的情况下修复，建议按优先级逐步迭代。

---

## 参考文件

- `python/sqlopt/stages/parse/stage.py`
- `python/sqlopt/stages/parse/branch_expander.py`
- `python/sqlopt/stages/parse/expander.py`
- `python/sqlopt/stages/branching/branch_generator.py`
- `python/sqlopt/stages/branching/sql_node.py`
- `python/sqlopt/stages/branching/risk_scorer.py`
- `python/sqlopt/stages/branching/planner.py`
- `python/sqlopt/stages/branching/mutex_branch_detector.py`
- `python/sqlopt/common/risk_assessment.py`
- `python/sqlopt/common/rules.py`
