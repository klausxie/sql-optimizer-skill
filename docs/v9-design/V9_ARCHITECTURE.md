# V9 SQL Optimizer 架构设计

## 概述

V9 是 V8 的演进版本，将原来的 7 阶段流水线简化为 **5 阶段**，并优化了优化验证流程。

### 设计目标 vs 当前实现

> ⚠️ **重要说明**：本文档描述 V9 的**设计目标**。当前实现（v9_stages/）与设计目标存在差距，详见各阶段的「现状分析」。

| 组件 | 设计目标 | 当前实现 | 状态 |
|------|---------|---------|------|
| Init | 统一收集 DB 元数据、参数示例、连接验证 | ✅ 已完成 | ✅ 完成 |
| Parse | 分支推断 + 风险检测 | 简化版分支推断 | ✅ 基本完成 |
| Recognition | EXPLAIN 基线采集，使用缓存元数据 | 每次单独连库查询 | ⚠️ 需优化 |
| Optimize | 使用缓存元数据生成优化建议 | 重复查询 DB 元数据 | ⚠️ 需优化 |
| Patch | 生成可应用 XML 补丁 | 功能完整 | ✅ 完成 |

### 核心变更

| V8 阶段 | V9 阶段 | 变更说明 |
|---------|---------|----------|
| Discovery | **Init** | 重命名，更清晰 |
| Branching + Pruning | **Parse** | 合并，一次遍历完成分支展开和风险检测 |
| Baseline | **Recognition** | 重命名，强调识别SQL模式 |
| Optimize + Validate | **Optimize** | 合并为迭代循环，优化→验证→重试(如需) |
| Patch | Patch | 保持不变 |

---

## 流水线全景图

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              V9 SQL Optimizer Pipeline                                   │
│                                                                                         │
│  ┌─────────┐    ┌─────────┐    ┌────────────┐    ┌─────────────────┐    ┌─────────┐  │
│  │  Init   │───▶│  Parse  │───▶│ Recognition │───▶│     Optimize     │───▶│  Patch  │  │
│  └─────────┘    └─────────┘    └────────────┘    └─────────────────┘    └─────────┘  │
│                                                                                         │
│       │                                                        ▲                        │
│       │ (缓存复用)                                              │ (迭代重试)             │
│       └────────────────────────────────────────────────────────┘                        │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 数据流图

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                              V9 数据流详解                                                          │
│                                                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐                              │
│  │                               INIT STAGE                                     │                              │
│  │  输入:                                                                      │                              │
│  │    - MyBatis XML mapper 文件 (mapper_globs)                               │                              │
│  │    - config (db 连接信息)                                                  │                              │
│  │                                                                              │                              │
│  │  处理:                                                                      │                              │
│  │    1. XML 扫描 → SQL 单元列表                                               │                              │
│  │    2. DB 连接验证 → db_connectivity.json                                   │                              │
│  │    3. 表名提取 (FROM/JOIN) → schema_metadata.tables                         │                              │
│  │    4. 列信息收集 → schema_metadata.columns                                 │                              │
│  │    5. 索引信息收集 → schema_metadata.indexes                               │                              │
│  │    6. 数据量统计 → schema_metadata.tableStats                              │                              │
│  │    7. 参数示例生成 → sql_units[].paramExample                             │                              │
│  │                                                                              │                              │
│  │  输出:                                                                      │                              │
│  │    ┌────────────────────────────────────────────────────────────────────┐  │                              │
│  │    │ init/sql_units.json           (SQL 单元 + paramExample)           │  │                              │
│  │    │ init/schema_metadata.json     (tables/columns/indexes/tableStats) │  │                              │
│  │    │ init/db_connectivity.json    (ok/driver/error)                  │  │                              │
│  │    └────────────────────────────────────────────────────────────────────┘  │                              │
│  └──────────────────────────────────────────────────────────────────────────────┘                              │
│                                          │                                                              │
│                                          │ sql_units.json (含 paramExample)                              │
│                                          │ schema_metadata.json (全局缓存)                                │
│                                          ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐                              │
│  │                               PARSE STAGE                                    │                              │
│  │  输入:  init/sql_units.json                                                │                              │
│  │  处理:                                                                      │                              │
│  │    - 分支推断 (if/choose/foreach 展开)                                     │                              │
│  │    - 风险检测 (prefix_wildcard, function_wrap 等)                         │                              │
│  │  输出:                                                                      │                              │
│  │    ┌────────────────────────────────────────────────────────────────────┐  │                              │
│  │    │ parse/sql_units_with_branches.json  (SQL + 所有分支)                │  │                              │
│  │    │ parse/risks.json                 (风险报告)                      │  │                              │
│  │    └────────────────────────────────────────────────────────────────────┘  │                              │
│  └──────────────────────────────────────────────────────────────────────────────┘                              │
│                                          │                                                              │
│                                          │ sql_units + branches + risks                                   │
│                                          ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐                              │
│  │                            RECOGNITION STAGE                                │                              │
│  │  输入:                                                                      │                              │
│  │    - parse/sql_units_with_branches.json                                    │                              │
│  │    - init/schema_metadata.json (⚠️ 当前未使用 - 需优化)                    │                              │
│  │    - init/db_connectivity.json (⚠️ 当前未使用 - 需优化)                    │                              │
│  │                                                                              │                              │
│  │  处理:                                                                      │                              │
│  │    - 对每个分支执行 EXPLAIN                                                │                              │
│  │    - 采集执行计划指标                                                      │                              │
│  │  输出:                                                                      │                              │
│  │    ┌────────────────────────────────────────────────────────────────────┐  │                              │
│  │    │ recognition/baselines.json    (每个分支的 EXPLAIN 结果)            │  │                              │
│  │    └────────────────────────────────────────────────────────────────────┘  │                              │
│  └──────────────────────────────────────────────────────────────────────────────┘                              │
│                                          │                                                              │
│                                          │ baselines + proposals                                        │
│                                          ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐                              │
│  │                             OPTIMIZE STAGE                                  │                              │
│  │  输入:                                                                      │                              │
│  │    - recognition/baselines.json                                           │                              │
│  │    - init/schema_metadata.json (⚠️ 当前未使用 - 需优化)                    │                              │
│  │    - init/sql_units.json (⚠️ 当前未使用 - 需优化)                          │                              │
│  │                                                                              │                              │
│  │  处理:                                                                      │                              │
│  │    - 规则评估 (FULL_SCAN_RISK, SELECT_STAR 等)                           │                              │
│  │    - LLM 优化建议 (可选)                                                  │                              │
│  │    - 迭代重试                                                              │                              │
│  │  输出:                                                                      │                              │
│  │    ┌────────────────────────────────────────────────────────────────────┐  │                              │
│  │    │ optimize/proposals.json        (优化建议列表)                      │  │                              │
│  │    └────────────────────────────────────────────────────────────────────┘  │                              │
│  └──────────────────────────────────────────────────────────────────────────────┘                              │
│                                          │                                                              │
│                                          │ proposals (validated=true)                                    │
│                                          ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐                              │
│  │                              PATCH STAGE                                     │                              │
│  │  输入:  optimize/proposals.json                                              │                              │
│  │  处理:                                                                      │                              │
│  │    - 生成 XML 补丁                                                         │                              │
│  │    - 备份原文件                                                           │                              │
│  │    - 支持 auto/manual 模式                                                 │                              │
│  │  输出:                                                                      │                              │
│  │    ┌────────────────────────────────────────────────────────────────────┐  │                              │
│  │    │ patch/patches.json           (补丁元数据)                           │  │                              │
│  │    │ patch/patches/*.patch       (补丁文件)                             │  │                              │
│  │    │ patch/backups/              (原始文件备份)                         │  │                              │
│  │    └────────────────────────────────────────────────────────────────────┘  │                              │
│  └──────────────────────────────────────────────────────────────────────────────┘                              │
│                                                                                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 缓存复用机制

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CACHE REUSE MECHANISM                               │
│                                                                             │
│  init/                          后续阶段复用:                               │
│  ├── schema_metadata.json  ────▶ Recognition (优化 EXPLAIN 参数)           │
│  │                               Optimize (生成更精准的优化建议)            │
│  │                               Parse (更智能的风险评估)                   │
│  │                                                                             │
│  ├── db_connectivity.json ────▶ Recognition (跳过无效连接)                  │
│  │                               Optimize (跳过无效连接)                    │
│  │                                                                             │
│  └── sql_units.json      ────▶ Parse (使用 paramExample)                    │
│                                  Optimize (生成更精准的优化建议)            │
│                                  Patch (原始 SQL 参考)                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 性能对比

| 场景 | V8/旧实现 | V9 Enhanced Init |
|------|-----------|-----------------|
| DB 连接验证 | 每阶段单独验证 | Init 一次验证 |
| 100 SQL, 每 SQL 10 分支 | 1000 次 DB 查询 (recognition+optimize) | 1 次 DB 查询 (init) |
| 元数据收集 | 每个 SQL 重复查询 | Init 批量收集一次 |
| paramExample | NULL | 基于列类型生成 |
| 缓存复用 | 无 | schema_metadata 全局共享 |

---

## 阶段详解

### 1. Init（初始化）

**职责**：解析 MyBatis XML 映射文件，提取 SQL 语句单元，**统一收集数据库元数据，为后续阶段提供缓存**

**输入**：MyBatis XML 配置文件（mapper_globs）

**输出**：
- `init/sql_units.json` — SQL 单元列表
- `init/schema_metadata.json` — 数据库元数据缓存（表结构、索引、数据量）
- `init/db_connectivity.json` — 数据库连接状态

**设计处理内容**：
- 扫描 XML 文件
- 解析 `<select>`, `<insert>`, `<update>`, `<delete>` 标签
- 提取 SQL 语句和元数据（namespace, statementId）
- 识别动态标签占位符（`${}`, `#{}`）
- **数据库连通性验证**（一次连接验证）
- **表结构收集**（tables, columns, indexes）
- **数据量统计**（tableStats）
- **参数示例生成**（paramExample）

**现状分析**（✅ 已完成）：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INIT STAGE - 已完成                                    │
│                                                                             │
│  ✅ 已实现:                                                               │
│    - XML 文件扫描 (Scanner class)                                          │
│    - SQL 解析 (namespace, statementId, sql)                                │
│    - 动态标签检测 (if, foreach, where, choose)                            │
│    - include 片段解析                                                      │
│    - 风险标记 (DOLLAR_SUBSTITUTION)                                       │
│    - 数据库连通性验证 → db_connectivity.json                               │
│    - 表结构收集 → schema_metadata.json                                     │
│    - 索引信息收集 → schema_metadata.json                                  │
│    - 数据量统计 → schema_metadata.json                                    │
│    - 参数示例生成 → paramExample (基于列类型)                              │
│                                                                             │
│  📁 产物:                                                                │
│    init/sql_units.json           (SQL + paramExample)                      │
│    init/schema_metadata.json     (tables/columns/indexes/tableStats)     │
│    init/db_connectivity.json     (连接状态)                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**产物示例**：
```json
{
  "sqlKey": "UserMapper.selectByExample",
  "namespace": "com.example.UserMapper",
  "statementId": "selectByExample",
  "sql": "SELECT * FROM users WHERE status = #{status}",
  "dynamicTags": ["#{status}"]
}
```

**改进建议**：
将元数据收集功能（tables, columns, indexes, tableStats）和参数生成功能整合到 Init 阶段，避免后续阶段重复查询数据库。

---

### 2. Parse（解析）

**职责**：展开动态 SQL 生成分支路径，同时进行风险检测

**输入**：`init/sql_units.json`

**输出**：
- `parse/sql_units_with_branches.json` — 带分支的 SQL 单元
- `parse/risks.json` — 风险检测结果

**设计处理内容**：

#### 2.1 分支展开（Branching）
- 解析 MyBatis 动态标签：`<if>`, `<where>`, `<choose>`, `<foreach>`
- 枚举所有可能的执行分支
- 生成分支的唯一标识和条件组合

**分支示例**：
```sql
-- 原始 SQL
SELECT * FROM users
<where>
  <if test="name != null">AND name = #{name}</if>
  <if test="age != null">AND age = #{age}</if>
</where>

-- 展开后分支
Branch 0: SELECT * FROM users
Branch 1: SELECT * FROM users WHERE name = #{name}
Branch 2: SELECT * FROM users WHERE age = #{age}
Branch 3: SELECT * FROM users WHERE name = #{name} AND age = #{age}
```

#### 2.2 风险检测（Pruning）
- **前缀通配符**：`'%' + column` — 无法使用索引
- **后缀通配符**：`column + '%'` — 可以使用索引
- **函数包裹**：`UPPER(column)` — 无法使用索引
- **CONCAT 通配符**：`CONCAT('%', column)` — 全表扫描

**风险标记**：
| 风险类型 | 模式 | 严重程度 | 影响 |
|----------|------|----------|------|
| prefix_wildcard | `'%'+name` | HIGH | 全表扫描 |
| suffix_wildcard_only | `name+'%'` | LOW | 可用索引 |
| function_wrap | `UPPER(name)` | MEDIUM | 索引失效 |
| concat_wildcard | `CONCAT('%',name)` | HIGH | 全表扫描 |

**现状分析**（✅ 基本完成）：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PARSE STAGE - 现状分析                                 │
│                                                                             │
│  ✅ 已实现:                                                               │
│    - BranchGenerator (adapters/branch_generator.py)                        │
│    - 分支推断 (all_combinations, pairwise, boundary 策略)                   │
│    - 风险检测 (prefix_wildcard, suffix_wildcard_only, function_wrap)       │
│    - analyze_risks 汇总分析                                                │
│                                                                             │
│  ⚠️ 可改进:                                                              │
│    - 无法利用表结构/索引信息做更智能的风险评估                              │
│    - 依赖简化版 BranchGenerator (非 V8 完整版)                              │
│                                                                             │
│  📁 产物:                                                                │
│    - parse/sql_units_with_branches.json                                    │
│    - parse/risks.json                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 3. Recognition（识别）

**职责**：采集当前 SQL 的执行计划作为性能基准

**输入**：`parse/sql_units_with_branches.json`

**输出**：`recognition/baselines.json` — 性能基线数据

**设计处理内容**：
- 对每个分支执行 `EXPLAIN`（PostgreSQL）或 `EXPLAIN ANALYZE`（MySQL）
- 采集关键指标：
  - 预计扫描行数
  - 实际扫描行数
  - 执行时间
  - 使用的索引
  - 关联方式（Nested Loop, Hash Join, etc.）
- 识别潜在性能问题（全表扫描、笛卡尔积等）

**现状分析**（⚠️ 需优化）：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RECOGNITION STAGE - 现状分析                             │
│                                                                             │
│  ✅ 已实现:                                                               │
│    - BaselineCollector (v9_stages/recognition.py)                         │
│    - PostgreSQL EXPLAIN JSON 解析                                          │
│    - MySQL EXPLAIN JSON 解析                                               │
│    - 性能指标采集 (estimated_rows, actual_rows, execution_time)            │
│    - 支持 EXPLAIN ANALYZE (可获取实际执行指标)                             │
│                                                                             │
│  ❌ 问题:                                                                 │
│    - 每个分支单独连接数据库查询                                             │
│    - 未使用 init 阶段缓存的表结构/索引信息                                  │
│    - paramExample 为空，EXPLAIN 使用 NULL 代替真实参数                      │
│                                                                             │
│  📁 产物:                                                                │
│    - recognition/baselines.json                                           │
│                                                                             │
│  性能问题:                                                                │
│    批量执行 100 个 SQL，每个 SQL 10 个分支 = 1000 次 DB 查询               │
│    而实际上只需要 1 次连接 + 批量查询表结构即可                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**产物示例**：
```json
{
  "sqlKey": "UserMapper.selectByExample:branch:1",
  "sql": "SELECT * FROM users WHERE name = 'john'",
  "executionPlan": {
    "operation": "Index Scan",
    "relation": "users",
    "rows": 150,
    "cost": 25.5,
    "usedIndex": "idx_users_name"
  },
  "performanceMetrics": {
    "estimatedRows": 150,
    "actualRows": 148,
    "executionTimeMs": 2.3
  }
}
```

**改进建议**：
在 Init 阶段统一收集表结构/索引/列类型信息，Recognition 阶段直接使用缓存数据。

---

### 4. Optimize（优化）

**职责**：生成优化建议并进行语义验证，支持迭代重试

**输入**：`baseline/baselines.json`

**输出**：`optimize/proposals.json` — 优化提案（含验证状态）

**设计处理流程**：

```
┌─────────────────────────────────────────────────────────────────┐
│                        Optimize 迭代循环                          │
│                                                                 │
│  ┌──────────────�                                               │
│  │  加载候选   │◀────────────────────────────────────────┐      │
│  └──────┬───────┘                                         │      │
│         ▼                                                 │      │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐  │      │
│  │  应用优化规则 │───▶│  语义验证    │───▶│ 通过？    │──┘      │
│  └──────────────┘    └──────────────┘    └───────────┘         │
│         │                   │                │                  │
│         │                   │ No             │ Yes             │
│         ▼                   ▼                ▼                  │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐         │
│  │  候选+1      │    │  标记失败    │    │  接受提案  │         │
│  └──────────────┘    └──────────────┘    └───────────┘         │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │ 达到最大迭代？│──────────────────────────────────────────────▶│
│  └──────────────┘                                                │
│         │                                                         │
│         │ Yes                                                     │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │  使用最佳候选 │                                                │
│  └──────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

**现状分析**（⚠️ 需优化）：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       OPTIMIZE STAGE - 现状分析                              │
│                                                                             │
│  ✅ 已实现:                                                               │
│    - evaluate_rules() 规则评估                                             │
│    - LLM 优化建议 (可选)                                                   │
│    - 优化建议生成 (platforms/sql/optimizer_sql.py)                         │
│    - 可行性评估 (actionability scoring)                                   │
│                                                                             │
│  ❌ 问题:                                                                 │
│    - 每个 SQL 单独调用 collect_sql_evidence()                              │
│    - 重复查询: tables, columns, indexes, tableStats                      │
│    - 未使用 init 阶段缓存的元数据                                          │
│                                                                             │
│  📁 产物:                                                                │
│    - optimize/proposals.json                                             │
│                                                                             │
│  性能问题:                                                                │
│    platforms/sql/optimizer_sql.py:236:                                    │
│        db_evidence, plan_summary = collect_sql_evidence(config, sql)     │
│                                                                             │
│    这会在每个 SQL 优化时单独连接 DB 查询:                                   │
│    - SHOW INDEX FROM table (MySQL)                                        │
│    - SELECT FROM information_schema.columns                               │
│    - SELECT FROM pg_indexes                                               │
│    - EXPLAIN ...                                                          │
│                                                                             │
│    100 个 SQL = 100 次重复的元数据查询                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

**优化规则示例**：

| 规则名称 | 原始 SQL | 优化后 SQL | 改进 |
|----------|----------|------------|------|
| index_hint | `SELECT * FROM t` | `SELECT * FROM t USE INDEX(idx_name)` | 强制使用索引 |
| or_to_union | `WHERE a=1 OR a=2` | `WHERE a IN (1,2)` | 避免全表扫描 |
| limit_pushdown | `SELECT * FROM t` | `SELECT * FROM t LIMIT 100` | 减少传输数据 |
| select_minimize | `SELECT * FROM t` | `SELECT col1,col2 FROM t` | 减少列读取 |

**验证逻辑**：
- 语义等价性检查（规范化后 SQL 对比）
- WHERE 子句等价性验证
- 结果集一致性验证（可选）

**产物示例**：
```json
{
  "sqlKey": "UserMapper.selectByExample:branch:1",
  "originalSql": "SELECT * FROM users WHERE status = 1",
  "ruleName": "select_minimize",
  "optimizedSql": "SELECT id, name, status FROM users WHERE status = 1",
  "improvement": {
    "estimatedCostReduction": "35%",
    "columnsReduced": 5
  },
  "iterations": 2,
  "validated": true
}
```

**改进建议**：
Optimize 阶段应直接使用 Init 阶段收集并缓存的 schema_metadata.json，而非重复查询数据库。

---

### 5. Patch（补丁）

**职责**：生成可应用的 XML 补丁

**输入**：`optimize/proposals.json`（仅 validated=true 的提案）

**输出**：`patch/patches.json` — 补丁清单

**处理内容**：
- 为每个通过的优化提案生成 XML 修改
- 生成回滚脚本（undo patch）
- 确认应用前的预览

**产物示例**：
```json
[
  {
    "sqlKey": "UserMapper.selectByExample",
    "ruleName": "select_minimize",
    "status": "ready",
    "applied": false,
    "patch": {
      "before": "<select id=\"selectByExample\" resultType=\"User\">SELECT * FROM users</select>",
      "after": "<select id=\"selectByExample\" resultType=\"User\">SELECT id, name, status FROM users</select>"
    }
  }
]
```

---

## 数据流

```
MyBatis XML
     │
     ▼
┌─────────┐     ┌─────────┐     ┌────────────┐    ┌─────────┐     ┌─────────┐
│  Init   │────▶│  Parse  │────▶│ Recognition │───▶│Optimize │────▶│  Patch  │
└─────────┘     └─────────┘     └────────────┘    └─────────┘     └─────────┘
     │               │               │                │               │
     ▼               ▼               ▼                ▼               ▼
sql_units      branches+risks   baselines         proposals       patches
.json          .json           .json            .json          .json
```

---

## 目录结构

```
runs/<run_id>/
├── supervisor/
│   ├── meta.json           # 运行元信息
│   └── state.json          # 阶段状态
├── init/
│   ├── sql_units.json      # 初始 SQL 单元
│   ├── schema_metadata.json      # ⚠️ 设计目标: DB元数据缓存
│   └── db_connectivity.json     # ⚠️ 设计目标: DB连接状态
├── parse/
│   ├── sql_units_with_branches.json  # 带分支的 SQL
│   └── risks.json          # 风险报告
├── recognition/
│   └── baselines.json      # 性能基线
├── optimize/
│   └── proposals.json      # 优化提案
└── patch/
    └── patches.json        # 最终补丁
```

> **注**：`schema_metadata.json` 和 `db_connectivity.json` 是设计目标，当前实现未生成。

---

## 配置示例

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

branching:
  strategy: all_combinations  # 分支生成策略
  max_branches: 100           # 最大分支数

recognition:
  timeout_ms: 5000           # 单条 SQL 超时
  sample_size: 1000          # 采样大小

optimize:
  max_iterations: 3          # 最大迭代次数
  rules:
    - select_minimize
    - index_hint
    - or_to_union

db:
  platform: postgresql
  dsn: postgresql://user:pass@host:5432/db

llm:
  enabled: true
  provider: opencode_run
```

---

## 设计目标：增强版 Init 阶段

### 目标

将数据库元数据收集功能整合到 Init 阶段，避免后续阶段重复查询数据库：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ENHANCED INIT STAGE                                 │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│  │ XML Scanner │───▶│ Table Extract │───▶│ DB Connector │                │
│  └──────────────┘    └──────────────┘    └──────────────┘                │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │              Metadata Collector (一次性收集)                  │            │
│  │  - tables: 所有涉及的表名                                    │            │
│  │  - columns: 列信息 (列名, 类型, 可空)                         │            │
│  │  - indexes: 索引信息 (索引名, 定义, 列)                      │            │
│  │  - tableStats: 数据量 (estimated_rows)                       │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │              Parameter Binder (参数示例生成)                    │            │
│  │  - 基于列类型生成合理参数示例                                  │            │
│  │  - 支持 camelCase/snake_case 转换                            │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                    Output Cache                              │            │
│  │  - init/sql_units.json       (SQL + paramExample)           │            │
│  │  - init/schema_metadata.json  (tables/columns/indexes)     │            │
│  │  - init/db_connectivity.json (连接状态)                    │            │
│  └─────────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 优势

1. **一次连接**：数据库只连一次，收集所有元数据
2. **批量处理**：从 SQL 中提取所有涉及的表，一次查询
3. **参数生成**：基于列类型生成合理的参数示例
4. **缓存复用**：后续阶段（parse/recognition/optimize）直接读缓存，不重复查询

### 参数绑定器 (Parameter Binder)

**职责**：基于数据库列类型生成合理的参数示例

**处理逻辑**：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Parameter Binder 处理流程                                  │
│                                                                             │
│  输入:                                                                    │
│    - SQL 语句中的 #{} 参数名 (如 #{userName}, #{user_id})                  │
│    - 数据库列信息 (column_name, data_type)                                 │
│                                                                             │
│  处理:                                                                    │
│    1. 提取参数名                                                           │
│       - 从 SQL 中正则匹配 #{}                                              │
│       - 提取参数名: #{userName} → userName                                │
│                                                                             │
│    2. 名称匹配 (支持双向转换)                                               │
│       - camelCase → snake_case: userName → user_name                      │
│       - snake_case → camelCase: user_name → userName                       │
│                                                                             │
│    3. 列类型到参数值的映射                                                 │
│       - INTEGER/INT → 1                                                   │
│       - BIGINT → 1                                                        │
│       - VARCHAR/TEXT → "example"                                          │
│       - BOOLEAN → true                                                    │
│       - DATE → "2024-01-01"                                              │
│       - TIMESTAMP → "2024-01-01T00:00:00"                               │
│       - FLOAT/DOUBLE → 1.0                                                │
│       - DECIMAL/NUMERIC → 1.0                                             │
│       - NULL (当 isNullable=true 时)                                       │
│                                                                             │
│  输出:                                                                    │
│    paramExample = {"userName": "example", "userId": 1, "active": true}   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**名称匹配规则**：

| MyBatis 参数格式 | 数据库列名 | 匹配结果 |
|-----------------|-----------|---------|
| `#{userName}` | `user_name` | ✅ 匹配 (camelCase → snake_case) |
| `#{user_name}` | `userName` | ✅ 匹配 (snake_case → camelCase) |
| `#{userName}` | `username` | ✅ 匹配 (去重后匹配) |
| `#{userName}` | `user_name` + `username` | ⚠️ 优先精确匹配 |

**类型推断规则**：

| 数据库类型 | 示例值 | 说明 |
|-----------|--------|------|
| `INTEGER`, `INT`, `INT4` | `1` | 整数 |
| `BIGINT`, `INT8` | `1` | 长整数 |
| `SMALLINT`, `INT2` | `1` | 短整数 |
| `VARCHAR`, `TEXT`, `CHAR` | `"example"` | 字符串 |
| `BOOLEAN`, `BOOL` | `true` | 布尔值 |
| `DATE` | `"2024-01-01"` | 日期 |
| `TIMESTAMP`, `DATETIME` | `"2024-01-01T00:00:00"` | 时间戳 |
| `TIME` | `"12:00:00"` | 时间 |
| `FLOAT`, `REAL` | `1.0` | 单精度浮点 |
| `DOUBLE`, `DOUBLE PRECISION` | `1.0` | 双精度浮点 |
| `DECIMAL`, `NUMERIC` | `1.0` | 精确小数 |
| `BYTEA` | `"\\x00"` | 二进制 |
| `JSON`, `JSONB` | `{}` | JSON 对象 |
| `ARRAY` | `[]` | 空数组 |

**可空列处理**：
- 当 `isNullable = true` 时，参数值为 `None` (Python) / `null` (JSON)
- 非空列始终有默认值

### 性能对比

| 场景 | 当前实现 | 增强后 |
|------|---------|--------|
| 100 SQL, 每 SQL 10 分支 | 1000 次 DB 查询 (optimize 阶段) | 1 次 DB 查询 (init 阶段) |
| EXPLAIN 执行 | paramExample=null | 使用真实参数示例 |
| 批量并行执行 | 每个 SQL 重复查元数据 | 共享缓存的元数据 |

---

## 与 V8 对比

| 维度 | V8 | V9 |
|------|-----|-----|
| 阶段数量 | 7 | 5 |
| Discovery→Init | 重命名 | 更清晰 |
| Branching+Pruning→Parse | 分离 | 合并，效率提升 |
| Baseline→Recognition | 重命名 | 强调SQL识别 |
| Optimize+Validate | 分离两阶段 | 合并为迭代循环 |
| 优化重试 | 需手动 | 自动最多3次 |
| 产物追溯 | 分离 | 统一在各自阶段目录 |
