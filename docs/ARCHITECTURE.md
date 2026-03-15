# SQL Optimizer 功能全景图

本文档描述 SQL Optimizer Skill 的完整功能架构和执行流程。

> **注意**：此文档为设计文档，可能会随着功能迭代而更新。

---

## 1. 执行模式

SQL Optimizer 支持三种执行模式：

| 模式 | 说明 | 示例 |
|------|------|------|
| **单条SQL** | 优化单条SQL | `"优化这条SQL: select * from users"` |
| **多条指定SQL** | 优化指定的多条SQL | `"优化findUsers, findOrders这3个方法"` |
| **批量文件** | 优化整个Mapper文件 | `"优化UserMapper.xml"` / `"优化所有Mapper文件"` |

---

## 2. 执行流程概览

```
用户输入（指定范围）
    │
    ▼
Step 1: Scan (扫描)
    │  - 解析用户指定范围
    │  - 推断动态分支 (if/foreach/choose)
    │  - 识别潜在慢SQL
    │
    ▼
Step 2: Execute (执行) [交互提示]
    │  ⚠️ Agent 必须提示: "是否执行获取性能数据？"
    │  - 收集执行计划 (EXPLAIN)
    │  - 收集实际耗时
    │
    ▼
Step 3: Analyze (分析)
    │  - 诊断分支问题
    │  - 确认慢SQL及其瓶颈
    │  - 判断优化方式 (rules/llm)
    │
    ▼
Step 4: Optimize (优化)
    │  - 生成针对性优化建议
    │
    ▼
Step 5: Apply (应用)
    │  - 生成 XML 补丁
    │  - 用户确认后应用
    │
    ▼
完成
```

---

## 3. 阶段职责

| 阶段 | 职责 | 不应该做 |
|------|------|----------|
| **Scan** | 解析范围、推断动态分支、识别潜在慢SQL | 问题分析、优化建议 |
| **Execute** | 执行SQL收集性能数据 | - |
| **Analyze** | 诊断分支问题、确认瓶颈 | - |
| **Optimize** | 生成优化建议 | - |
| **Apply** | 应用补丁 | - |

---

## 4. 各阶段输入输出

### Step 1: Scan (扫描)

**目标**：只推断动态分支，不做深度问题分析

**输入**:
- 用户指定范围（SQL ID、文件路径、配置文件）
- 配置: scan.mapper_globs

**处理**:
1. 解析用户指定范围（不扩散）
2. 解析XML文件
3. 推断动态分支 (if/foreach/choose)
4. 生成执行模板

**输出**:
- SQL单元列表
- 动态分支列表
- 分支数量

**产物**: runs/<run-id>/
- scan.sqlunits.jsonl     # SQL单元列表
- branches.jsonl          # 分支执行模板

**精准分析原则**：
- 用户指定哪个SQL就只分析哪个
- 不主动列出所有SQL让用户选择
- 不在报告中列出无关的SQL

---

### Step 2: Execute (执行)

**⚠️ 必须交互提示**：
```
发现 3 个潜在慢 SQL：
  - findUsers (可能全表扫描)
  - findOrders (LIKE 前缀通配符)
  - getReport (嵌套子查询)

是否执行这些 SQL 获取实际性能数据？[Y/n]
```

**输入**:
- scan.sqlunits.jsonl    # SQL单元
- branches.jsonl         # 分支执行模板
- DB连接: dsn配置

**处理**:
- real模式: 实际执行SQL，采集EXPLAIN + 性能数据
- mock模式: LLM推测执行计划

**输出**:
- 每个分支的执行计划
- 每个分支的实际耗时
- 每个分支的返回行数

**产物**: runs/<run-id>/
- execute_results.jsonl   # 执行结果

**execute_results.jsonl 示例**:
```json
{
  "branch": "branch_1",
  "sql": "SELECT * FROM users WHERE status = 1",
  "plan": "Index Scan",
  "duration_ms": 45,
  "rows": 150
}
```

---

### Step 3: Analyze (分析)

**输入**:
- scan.sqlunits.jsonl       # SQL单元
- execute_results.jsonl      # 执行结果

**处理**:
1. 诊断分支问题 (调用 diagnose_branches)
2. 确认慢SQL及其瓶颈
3. 判断复杂度 (简单/复杂)
4. 选择优化方式 (rules/llm)

**输出**:
- 问题分支列表
- 瓶颈分析
- 优化方向
- 复杂度判断

**产物**: runs/<run-id>/
- analyzed.sqlunits.jsonl  # 分析后的SQL单元

**analysis 示例**:
```json
{
  "issues": [
    {"type": "FULL_SCAN", "severity": "HIGH"},
    {"type": "NO_LIMIT", "severity": "MEDIUM"}
  ],
  "complexity": "simple",
  "optimizationMethod": "rules",
  "problemBranchCount": 3
}
```

---

### Step 4: Optimize (优化)

**输入**:
- analyzed.sqlunits.jsonl  # 分析结果
- rules/                   # 规则Skill (如用规则)
- llm/                     # LLM接口 (如用大模型)

**处理**:
- 规则优化: 应用固化规则生成优化建议
- 大模型优化: LLM生成优化建议 + Diff

**输出**:
- 优化建议列表
- 预测性能提升
- Diff内容 (如需要)

**产物**: runs/<run-id>/
- proposals/               # 优化建议

**proposals 示例**:
```json
{
  "sql_key": "UserMapper.findUsers#v1",
  "original": "SELECT * FROM users WHERE status = ?",
  "optimized": "SELECT id,name,status FROM users...",
  "strategy": "SELECT_TO_INDEX",
  "risk": "LOW"
}
```

---

### Step 5: Apply (应用)

**输入**:
- proposals/               # 优化建议
- 用户确认

**处理**:
1. 生成最终Diff
2. 展示给用户确认
3. 用户确认后修改XML

**输出**:
- 修改后的XML
- 修改对比

**产物**: runs/<run-id>/
- patches/                 # 补丁文件
- report.md                # 报告

---

## 5. 完整产物结构

```
runs/<run-id>/
├── supervisor/
│   ├── meta.json          # 运行元信息
│   ├── plan.json          # 语句列表
│   └── state.json         # 阶段状态
├── scan.sqlunits.jsonl    # 扫描产物
├── branches.jsonl         # 分支模板
├── execute_results.jsonl  # 执行结果
├── analyzed.sqlunits.jsonl # 分析结果
├── proposals/             # 优化建议
├── patches/               # 补丁产物
├── report.json            # JSON 报告
└── report.md              # Markdown 报告
```

---

## 6. 交互节点

| 节点 | 交互内容 | 触发条件 |
|------|----------|----------|
| **执行确认** | "是否执行获取性能数据？" | 扫描完成后，**必须提示** |
| **数据库配置** | 提示配置DSN | 需要执行但未配置时 |
| **确认修改** | 是否应用补丁 | Apply前确认 |

---

## 7. 复杂度判断

| 场景 | 方式 | 示例 |
|------|------|------|
| SELECT * | Rules | `SELECT *` → `SELECT id` |
| 缺少索引 | Rules | 建议添加索引 |
| LIKE %xxx% | Rules | 改用EXPLAIN分析 |
| 业务逻辑复杂 | LLM | 需要理解业务逻辑 |
| 多表关联 | LLM | 涉及JOIN优化 |
| 嵌套子查询 | LLM | 需要理解语义 |

---

## 8. 相关文档

- [快速入门](QUICKSTART.md)
- [配置说明](CONFIG.md)
- [故障排查](TROUBLESHOOTING.md)
- [系统规格](project/02-system-spec.md)
- [工作流与状态机](project/03-workflow-and-state-machine.md)
