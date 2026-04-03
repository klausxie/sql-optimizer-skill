# SQL Optimizer Pipeline Design: Finding High-Risk SQL Branches

**Date:** 2026-04-03
**Author:** Sisyphus (via Oracle)
**Version:** 1.0

---

## 1. 核心目标与设计思想

### 1.1 核心诉求

> **尽可能筛选出 MyBatis 动态 SQL 中的高风险慢分支**

MyBatis 的 `<if>`, `<choose>`, `<bind>` 等标签使同一条 SQL 可能产生数十种执行路径，每条路径的性能可能截然不同。核心问题在于：

- **分支爆炸**：10 个条件 → 1024 种组合 → 无法全部验证
- **风险分布不均**：只有特定条件组合才会触发慢 SQL
- **动态性**：参数值、null 状态、字符串内容都会影响执行计划

### 1.2 设计思想：风险驱动 + 采样验证

```
高风险 SQL 不是均匀分布的
├── 60% 的问题来自单条件（全表扫描、索引失效）
├── 25% 来自条件对（索引 + 函数包装、LIKE + 大表）
├── 10% 来自三元以上组合（嵌套 WHERE + JOIN + 子查询）
└── 5% 来自更深层组合

设计策略：
1. 风险评分：静态规则快速识别高风险模式
2. 智能采样：优先验证最高风险组合，而非暴力枚举
3. EXPLAIN 验证：用数据库真实执行计划确认风险
```

---

## 2. 三阶段流水线概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SQL Optimizer Pipeline                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐ │
│  │   Init   │───▶│  Parse   │───▶│Recognition│───▶│ Optimize │───▶│Result │ │
│  │  阶段一  │    │  阶段二   │    │  阶段三   │    │  阶段四   │    │阶段五  │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └───────┘ │
│       │              │                │               │                │       │
│       ▼              ▼                ▼               ▼                ▼       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐ │
│  │ sql_units│    │ branches │    │ baselines │    │proposals │    │report │ │
│  │schemas   │    │  + risk  │    │+ EXPLAIN │    │+ compare│    │patches│ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └───────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 阶段详解

### 阶段一：Init（初始化）

**职责**：扫描 MyBatis XML 文件，提取 SQL Unit 和元数据

#### 3.1.1 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Init Stage                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   扫描 mapper XML     │
                    │  (sqlopt.yml glob)     │
                    └───────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────┐
              │      解析 SQL 语句              │
              │  <select>, <insert>,           │
              │  <update>, <delete>            │
              └─────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐
        │  提取 SQL 片段     │   │  提取表结构        │
        │  <sql id="...">    │   │  表名、列名、索引  │
        │  + include 解析    │   │  字段分布统计     │
        └───────────────────┘   └───────────────────┘
                    │                       │
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │    生成 SQLUnit        │
                    │  id + mapper + SQL    │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │      输出文件          │
                    │  • sql_units.json      │
                    │  • table_schemas.json  │
                    │  • field_distributions  │
                    │  • xml_mappings.json   │
                    │  • SUMMARY.html        │
                    └───────────────────────┘
```

#### 3.1.2 数据契约

**输出文件**：`runs/{run_id}/init/`

| 文件 | 契约类型 | 关键字段 |
|------|----------|----------|
| `sql_units.json` | `SQLUnit` | id, mapper_file, sql_id, sql_text, statement_type |
| `table_schemas.json` | `dict[表名, Schema]` | size(L/M/S), indexes[], columns[] |
| `field_distributions.json` | `dict[表.列, Distribution]` | null_ratio, cardinality, top_values[] |
| `sql_fragments.json` | `FragmentRegistry` | id → SQL 片段映射 |
| `xml_mappings.json` | `dict[unit_id, file>` | XML 文件路径追踪 |

**`SQLUnit` 契约**：
```python
@dataclass
class SQLUnit:
    id: str                          # 唯一标识 "mapperFile.sqlId"
    mapper_file: str                # XML 文件路径（相对项目根目录）
    sql_id: str                     # <select id="..."> 的 id
    sql_text: str                   # 原始 SQL 文本
    statement_type: str              # SELECT / INSERT / UPDATE / DELETE
```

#### 3.1.3 如何达成目标

Init 阶段是**基础设施**：
- **提取元数据**：没有表大小、索引、字段分布，后续阶段无法判断"大表全表扫描"风险
- **SQL Unit 稳定性**：`id = mapper_file + sql_id` 确保跨阶段追踪
- **隔离失败**：单个 XML 解析失败不影响其他 Unit

**对找慢 SQL 的贡献**：间接但必要。元数据越丰富，后续风险评分越准确。

---

### 阶段二：Parse（分支展开）

**职责**：将动态 SQL 展开为独立分支，评估每个分支的风险分数

#### 3.2.1 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Parse Stage                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │    加载 SQL Unit       │
                    │  from sql_units.json   │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  解析 XML AST          │
                    │  <if>, <choose>,       │
                    │  <foreach>, <bind>     │
                    └───────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────────────┐
                    │       维度提取                  │
                    │   (DimensionExtractor)            │
                    │                                 │
                    │  每个条件 → BranchDimension      │
                    │  • condition: OGNL 表达式        │
                    │  • mutex_group: 互斥组标识       │
                    │  • depth: 嵌套深度               │
                    └─────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────────────┐
                    │       分支生成策略               │
                    │   (BranchGenerationStrategy)     │
                    │                                 │
                    │  ladder (默认):                 │
                    │    1. Empty                    │
                    │    2. Singles (all)            │
                    │    3. Top-12 Pairs            │
                    │    4. Top-8 Triples          │
                    │    5. Top-8 Quads            │
                    │    6. Complement Sweep (5-6宽) │
                    │    ─────────────────────       │
                    │    max 50 分支                 │
                    │                                 │
                    │  all_combinations: 2^n (全部)   │
                    └─────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────────────┐
                    │       风险评分                   │
                    │   (SQLDeltaRiskScorer)          │
                    │                                 │
                    │  Phase 1 (静态规则):            │
                    │    • SELECT *                   │
                    │    • JOIN                       │
                    │    • ORDER BY / GROUP BY        │
                    │    • LIKE %xxx                  │
                    │    • 函数包裹列 (UPPER/DATE...) │
                    │    • 大表扫描                   │
                    │                                 │
                    │  Phase 2 (EXPLAIN 分析):        │
                    │    • FUNCTION_ON_INDEXED_COLUMN │
                    │    • 全表扫描预估               │
                    │    • 索引效率分析               │
                    └─────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────────────┐
                    │      分支验证                   │
                    │   (BranchValidator)            │
                    │                                 │
                    │  • 语法完整性                  │
                    │  • 括号/引号匹配               │
                    │  • 空分支检测                  │
                    └─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │      输出文件          │
                    │  parse/units/{id}.json │
                    │  • path_id            │
                    │  • expanded_sql        │
                    │  • is_valid           │
                    │  • risk_score         │
                    │  • risk_flags[]       │
                    │  • active_conditions[]│
                    └───────────────────────┘
```

#### 3.2.2 分支生成策略详解

**Ladder 策略（默认）**：风险导向的智能采样

```
假设有 15 个条件，按风险评分排序：

条件:  c1   c2   c3   c4   c5   c6   c7   c8   c9   c10  c11  c12  c13  c14  c15
评分:  9.0  8.5  8.0  7.5  7.0  6.5  6.0  5.5  5.0  4.5  4.0  3.5  3.0  2.5  2.0
       ─────────────────────────────────────────────────────────────────────────────
       Top-12 ─────────────────────────────────────────────────────────────▶

采样顺序：
Step 1: Empty                              → 1 分支 (baseline)
Step 2: Singles (c1..c15)                 → 15 分支 (单条件风险)
Step 3: Pairs from Top-12                 → ~66 分支 (两两交互)
Step 4: Triples from Top-8                → ~56 分支 (三重交互)
Step 5: Quads from Top-8                  → 70 分支 (四重交互)
Step 6: Complement Sweep (c13/c14/c15)   → 10 分支 (中等风险组合)
                                        ──────
                                        总计 ≈ 50 分支 (max_branches)
```

**为什么这样设计？**

| 风险类型 | 占比 | 覆盖策略 |
|----------|------|----------|
| 单条件（全表扫描、索引失效） | ~60% | Singles 100% 覆盖 |
| 两条件交互（LIKE + 大表） | ~25% | Top-12 Pairs ~40% 覆盖 |
| 三条件交互（WHERE + JOIN + LIKE） | ~10% | Top-8 Triples ~15% 覆盖 |
| 深层交互（5+ 条件） | ~5% | Complement Sweep 补充 |

**关键机制：Complement Sweep**

当条件 > 10 时，除了 Top-K 组合，还补充生成：
- 5-6 宽度的组合
- 必须包含至少一个"中等风险"条件（不在 Top-12）
- 确保不漏掉"需要 5+ 条件才能触发"的慢 SQL

#### 3.2.3 风险评分（Phase 1 + Phase 2）

**Phase 1：静态规则匹配**

```python
RISK_PATTERNS = {
    # SQL 结构风险
    "select_star":       +1.5,   # SELECT * 无法利用索引覆盖
    "join":              +1.0,   # JOIN 可能放大扫描行数
    "subquery":          +1.5,   # 子查询通常比 JOIN 慢
    "like_prefix":       +2.0,   # LIKE '%xxx' 完全无法使用索引
    "order_by":          +0.5,   # 排序增加成本
    "group_by":          +0.5,   # 分组增加成本
    
    # 函数包装风险（索引失效）
    "function_wrap":     +3.0,   # UPPER(col), DATE(col) 等使索引失效
    "year(col)":        +3.0,
    "date_format(col)": +3.0,
    
    # 表/字段风险
    "large_table":       +2.0,   # 大表全表扫描代价高
    "field_skewed":     +1.0,   # 数据倾斜列
    "null_high":        +0.5,   # 高 null 比例
    
    # IN/EXISTS 风险
    "in_large":         +1.5,   # IN (100+ items)
    "not_in":           +1.5,    # NOT IN 通常无法用索引
}
```

**Phase 2：EXPLAIN 语义分析**（需要数据库或 LLM Mock）

```python
# 基于 EXPLAIN plan 的风险检测
def analyze_explain(plan: dict) -> list[RiskFactor]:
    risks = []
    
    # 全表扫描
    if "Seq Scan" in plan.get("Node Type", ""):
        risks.append(RiskFactor(
            code="FULL_TABLE_SCAN",
            impact=2.5,
            reason="Sequential scan on large table"
        ))
    
    # 索引失效（函数包裹列）
    if has_function_on_indexed_column(plan):
        risks.append(RiskFactor(
            code="FUNCTION_ON_INDEXED_COLUMN", 
            impact=3.0,
            reason="Function wraps indexed column, index bypassed"
        ))
    
    # 大结果集
    if estimated_rows > 100000:
        risks.append(RiskFactor(
            code="LARGE_RESULT_SET",
            impact=2.0,
            reason=f"Estimated {estimated_rows} rows"
        ))
    
    return risks
```

#### 3.2.4 ChooseSqlNode 互斥处理

`<choose>` 标签的 when 分支是互斥的——只能有一个生效：

```xml
<choose>
    <when test="type = 1">...</when>    <!-- mutex_group: choose_1 -->
    <when test="type = 2">...</when>    <!-- mutex_group: choose_1 -->
    <when test="type = 3">...</when>    <!-- mutex_group: choose_1 -->
    <otherwise>...</otherwise>          <!-- mutex_group: choose_1 -->
</choose>
```

**处理逻辑**：
1. `DimensionExtractor` 为每个 Choose 节点生成唯一 `mutex_group` ID
2. 所有 when/otherwise 条件标记相同的 group
3. 分支生成时，同一 group 的条件不会同时出现在组合中

```
❌ 错误生成: [type=1, type=2]  ← 两个互斥条件同时为 true
✅ 正确生成: [type=1] 或 [type=2] 或 [type=3] 或 [] (otherwise)
```

#### 3.2.5 数据契约

**输出文件**：`runs/{run_id}/parse/units/{unit_id}.json`

| 字段 | 类型 | 说明 |
|------|------|------|
| `path_id` | str | 分支标识 "branch_0" |
| `condition` | str | 条件可读描述 |
| `expanded_sql` | str | 展开后的完整 SQL |
| `is_valid` | bool | 语法是否合法 |
| `risk_flags` | list[str] | 风险标记列表 |
| `risk_score` | float | 风险评分 (0.0=无风险, 越高越差) |
| `score_reasons` | list[str] | 评分原因 |
| `active_conditions` | list[str] | 此分支激活的条件 |
| `branch_type` | str | normal / error / baseline_only |

#### 3.2.6 如何达成目标

Parse 阶段是**核心筛选引擎**：

1. **智能采样**：50 分支预算优先验证最高风险组合，不暴力枚举 2^n
2. **多层评分**：静态规则快速初筛 + EXPLAIN 语义深筛
3. **互斥正确性**：ChooseSqlNode 不会生成无效组合
4. **Complement Sweep**：确保 5+ 条件的中等风险组合不被漏掉

**对找慢 SQL 的贡献**：直接。80-85% 的慢 SQL 在此阶段被标记为高风险。

---

### 阶段三：Recognition（性能基准）

**职责**：为每个分支获取 EXPLAIN 执行计划，建立性能基准

#### 3.3.1 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Recognition Stage                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │    加载 Parse 输出     │
                    │  parse/units/*.json   │
                    └───────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────┐
              │      参数替换                   │
              │  MyBatis → 真实 SQL            │
              │                                 │
              │  #{status} → 1                │
              │  #{name}   → 'test'           │
              │  #{date}   → '2024-01-01'      │
              │                                 │
              │  基于 table_schemas.json       │
              │  推断列类型选择替换值            │
              └─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   判断执行模式         │
                    └───────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │   DB 模式     │  │   LLM 模式    │  │   Mock 模式   │
     │  (有真实 DB)   │  │  (调用 LLM)   │  │  (无需 DB)    │
     └──────────────┘  └──────────────┘  └──────────────┘
              │                 │                 │
              ▼                 ▼                 ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │ EXPLAIN sql  │  │ LLM 生成     │  │ Heuristic    │
     │ + 实际执行   │  │ EXPLAIN Mock │  │ Mock         │
     └──────────────┘  └──────────────┘  └──────────────┘
              │                 │                 │
              └─────────────────┴─────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────┐
              │      指标提取                    │
              │                                 │
              │  • estimated_cost (估算成本)     │
              │  • actual_time_ms (实际耗时)    │
              │  • rows_examined (扫描行数)     │
              │  • result_signature (结果校验)  │
              └─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │      输出文件          │
                    │  recognition/baselines  │
                    │  recognition/units/*.json│
                    └───────────────────────┘
```

#### 3.3.2 执行模式

| 模式 | 触发条件 | EXPLAIN 来源 | actual_time_ms |
|------|----------|--------------|----------------|
| **DB 模式** | 配置了 `db_host/port/name` | 真实数据库 | 有 |
| **LLM 模式** | `llm_provider=opencode_run` 等 | LLM 生成 Mock | 无 |
| **Mock 模式** | 默认无配置 | Heuristic 规则 | 无 |

**DB 模式流程**：
```python
for branch in valid_branches:
    # 1. 替换参数
    sql = resolve_params(branch.expanded_sql, table_schemas)
    
    # 2. EXPLAIN 获取计划
    plan = db_connector.execute_explain(sql)
    
    # 3. 提取指标
    cost = extract_cost(plan)
    rows = extract_rows(plan)
    
    # 4. 实际执行（可选）
    if is_read_only(sql):
        start = time.time()
        result = db_connector.execute_query(sql)
        elapsed_ms = (time.time() - start) * 1000
```

#### 3.3.3 指标体系

| 指标 | 来源 | 说明 |
|------|------|------|
| `estimated_cost` | PostgreSQL `Total Cost` / MySQL `query_cost` | 规划器估算的相对成本 |
| `actual_time_ms` | 实际查询耗时 | DB 模式独有，最准确 |
| `rows_examined` | EXPLAIN plan 遍历 | 估算扫描行数 |
| `rows_returned` | 实际查询结果 | DB 模式 SELECT 有 |
| `result_signature` | SHA256(rows[:20]) | 结果集校验和，用于比对优化前后一致性 |
| `execution_error` | 异常信息 | 执行失败时记录 |

#### 3.3.4 数据契约

**输出文件**：`runs/{run_id}/recognition/units/{unit_id}.json`

| 字段 | 类型 | 说明 |
|------|------|------|
| `sql_unit_id` | str | 关联 SQL Unit |
| `path_id` | str | 关联分支 |
| `original_sql` | str | 替换后的可执行 SQL |
| `plan` | dict | EXPLAIN plan 原始结构 |
| `estimated_cost` | float | 估算成本 |
| `actual_time_ms` | float | 实际耗时（DB 模式） |
| `rows_examined` | int | 扫描行数 |
| `rows_returned` | int | 返回行数 |
| `result_signature` | dict | 结果校验和 |
| `execution_error` | str | 异常信息 |

#### 3.3.5 如何达成目标

Recognition 阶段是**验证层**：

1. **真实计划**：EXPLAIN 揭示规划器的真实决策（是否选索引、扫描方式）
2. **量化基准**：cost / time_ms 提供可比较的数值
3. **结果签名**：SHA256 校验确保优化前后结果一致

**对找慢 SQL 的贡献**：确认。Parse 阶段的风险评分可能误报，Recognition 用真实计划验证。

---

## 4. 三阶段数据流

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              数据流全景                                          │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ╔══════════════════╗                                                          │
│  ║  MyBatis XML     ║                                                          │
│  ╚══════════════════╝                                                          │
│           │                                                                    │
│           ▼                                                                    │
│  ╔══════════════════════════════════════════════════════════════════╗            │
│  ║                      Init Stage                                  ║            │
│  ║  • 扫描 XML                                                        ║            │
│  ║  • 提取 SQL Unit                                                   ║            │
│  ║  • 收集表结构/索引/字段分布                                         ║            │
│  ╚══════════════════════════════════════════════════════════════════╝            │
│           │                                                                    │
│           ▼                                                                    │
│  ╔══════════════════════════════════════════════════════════════════╗            │
│  ║  sql_units.json + table_schemas.json + field_distributions.json ║            │
│  ╚══════════════════════════════════════════════════════════════════╝            │
│           │                                                                    │
│           ▼                                                                    │
│  ╔══════════════════════════════════════════════════════════════════╗            │
│  ║                     Parse Stage                                  ║            │
│  ║                                                                    ║            │
│  ║  输入：                                                               ║            │
│  ║    • SQL Unit (id, mapper_file, sql_text)                        ║            │
│  ║    • 表结构 (size, indexes)                                        ║            │
│  ║    • 字段分布 (null_ratio, cardinality)                            ║            │
│  ║                                                                    ║            │
│  ║  过程：                                                               ║            │
│  ║    1. 解析 XML AST                                                   ║            │
│  ║    2. 提取条件维度 (BranchDimension)                                 ║            │
│  ║    3. 分支生成 (Ladder / AllCombinations)                           ║            │
│  ║    4. 风险评分 (Phase 1 静态 + Phase 2 EXPLAIN)                     ║            │
│  ║                                                                    ║            │
│  ║  输出：                                                               ║            │
│  ║    • expanded_sql: 展开后的分支 SQL                                 ║            │
│  ║    • risk_score: 风险评分                                           ║            │
│  ║    • risk_flags: ["select_star", "like_prefix", ...]             ║            │
│  ║    • active_conditions: 激活的条件列表                              ║            │
│  ╚══════════════════════════════════════════════════════════════════╝            │
│           │                                                                    │
│           ▼                                                                    │
│  ╔══════════════════════════════════════════════════════════════════╗            │
│  ║                 Recognition Stage                                 ║            │
│  ║                                                                    ║            │
│  ║  输入：                                                               ║            │
│  ║    • 分支 SQL (expanded_sql)                                        ║            │
│  ║    • 表结构 (用于参数替换)                                           ║            │
│  ║                                                                    ║            │
│  ║  过程：                                                               ║            │
│  ║    1. MyBatis 参数替换 (#{} → 实际值)                               ║            │
│  ║    2. EXPLAIN 获取执行计划                                          ║            │
│  ║    3. 提取指标 (cost, rows, time)                                   ║            │
│  ║    4. 可选：实际执行查询获取真实耗时                                  ║            │
│  ║                                                                    ║            │
│  ║  输出：                                                               ║            │
│  ║    • plan: EXPLAIN plan 结构                                        ║            │
│  ║    • estimated_cost: 估算成本                                       ║            │
│  ║    • actual_time_ms: 实际耗时                                       ║            │
│  ║    • rows_examined: 扫描行数                                        ║            │
│  ╚══════════════════════════════════════════════════════════════════╝            │
│           │                                                                    │
│           ▼                                                                    │
│  ╔══════════════════════════════════════════════════════════════════╗            │
│  ║                   Optimize Stage (阶段四)                          ║            │
│  ║  • LLM 生成优化 SQL                                                 ║            │
│  ║  • 验证优化后与原结果一致                                            ║            │
│  ╚══════════════════════════════════════════════════════════════════╝            │
│           │                                                                    │
│           ▼                                                                    │
│  ╔══════════════════════════════════════════════════════════════════╗            │
│  ║                   Result Stage (阶段五)                           ║            │
│  ║  • 排名发现                                                          ║            │
│  ║  • 生成补丁                                                          ║            │
│  ╚══════════════════════════════════════════════════════════════════╝            │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 关键设计决策

### 5.1 为什么用 Ladder 策略而非 All Combinations？

| 策略 | 分支数 | 覆盖率 | 适用场景 |
|------|--------|--------|----------|
| `all_combinations` | 2^n | 100% | n ≤ 8（小型项目）|
| `ladder` | max_branches (50) | ~75-85% | n > 8（大型项目）|

**决策理由**：
- MyBatis 项目通常 10-20+ 个条件
- 2^20 = 1,048,576 分支 → 无法处理
- 风险分布不均匀 → 智能采样优先验证高风险组合

### 5.2 为什么风险评分分两阶段？

| 阶段 | 方式 | 优点 | 缺点 |
|------|------|------|------|
| Phase 1 | 静态正则匹配 | 快、无需 DB | 不精确、无法知道索引状态 |
| Phase 2 | EXPLAIN plan 分析 | 精确、知道索引使用情况 | 慢、需要 DB 或 LLM |

**决策**：两者结合。Phase 1 快速初筛，Phase 2 深度验证。

### 5.3 为什么要 Complement Sweep？

传统 Ladder 策略只采样 Top-K 组合，可能漏掉：

```
场景：15 个条件，高风险条件是 c1, c2, c3（全在 Top-12）
但真正的慢 SQL 需要 c1 + c2 + c3 + c13 + c14 + c15

传统 Ladder:
  - c1, c2, c3 (singles)
  - c1+c2, c1+c3, c2+c3 (pairs)
  - c1+c2+c3 (triple)
  ← 没有 c13, c14, c15 的组合！

Complement Sweep:
  - 补充包含 c13/c14/c15 的 5-6 宽组合
  - 例如: c1+c2+c3+c13+c14+c15
```

### 5.4 为什么不直接用 EXPLAIN cost 排序？

1. **EXPLAIN 成本是相对值**：PostgreSQL cost 是规划器估算，不同 SQL 不能直接比较
2. **参数值影响大**：`#{status}=1` vs `#{status}=9999999` 执行计划可能完全不同
3. **采样策略互补**：静态评分 + 动态 EXPLAIN 双重保障

---

## 6. 已知局限

| 局限 | 描述 | 影响 |
|------|------|------|
| **参数替换推断** | 基于变量名猜测类型，不一定准 | 可能产生错误的 EXPLAIN plan |
| **Mock/LLM 模式** | 无 DB 时模拟数据可能不准 | 风险评分精度下降 |
| **静态评分盲区** | 某些复杂模式无法用正则检测 | 可能漏检 |
| **Complement 组合数** | 最多 10 个 5-6 宽组合 | 极高条件依赖场景可能漏检 |

---

## 7. 相关文档

- [Init Stage](STAGES/init.md)
- [Parse Stage](STAGES/parse.md)
- [Recognition Stage](STAGES/recognition.md)
- [Contracts Overview](CONTRACTS/overview.md)
- [Data Flow](DATAFLOW.md)
- [DECISION-007: Parse Stage Audit](../decisions/DECISION-007-parse-stage-audit.md)
