# V9 SQL Optimizer 架构设计

## 概述

V9 是 V8 的演进版本，将原来的 7 阶段流水线简化为 **5 阶段**，并优化了优化验证流程。

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
│                                                 ▲                                       │
│                                                 │ (迭代重试)                              │
│                                                 └─────────────────────────────────────  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 阶段详解

### 1. Init（初始化）

**职责**：解析 MyBatis XML 映射文件，提取 SQL 语句单元

**输入**：MyBatis XML 配置文件（mapper_globs）

**输出**：`init/sql_units.json` — SQL 单元列表

**处理内容**：
- 扫描 XML 文件
- 解析 `<select>`, `<insert>`, `<update>`, `<delete>` 标签
- 提取 SQL 语句和元数据（namespace, statementId）
- 识别动态标签占位符（`${}`, `#{}`）

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

---

### 2. Parse（解析）

**职责**：展开动态 SQL 生成分支路径，同时进行风险检测

**输入**：`init/sql_units.json`

**输出**：
- `parse/sql_units_with_branches.json` — 带分支的 SQL 单元
- `parse/risks.json` — 风险检测结果

**处理内容**：

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

---

### 3. Recognition（识别）

**职责**：采集当前 SQL 的执行计划作为性能基准

**输入**：`parse/sql_units_with_branches.json`

**输出**：`recognition/baselines.json` — 性能基线数据

**处理内容**：
- 对每个分支执行 `EXPLAIN`（PostgreSQL）或 `EXPLAIN ANALYZE`（MySQL）
- 采集关键指标：
  - 预计扫描行数
  - 实际扫描行数
  - 执行时间
  - 使用的索引
  - 关联方式（Nested Loop, Hash Join, etc.）
- 识别潜在性能问题（全表扫描、笛卡尔积等）

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

---

### 4. Optimize（优化）

**职责**：生成优化建议并进行语义验证，支持迭代重试

**输入**：`baseline/baselines.json`

**输出**：`optimize/proposals.json` — 优化提案（含验证状态）

**处理流程**：

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
│   └── sql_units.json      # 初始 SQL 单元
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
