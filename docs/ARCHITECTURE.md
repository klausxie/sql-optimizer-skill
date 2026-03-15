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
用户输入
    │
    ▼
Step 0: Parse (解析输入)
    │
    ▼
Step 1: Scan (扫描)
    │
    ▼
Step 2: Execute (执行) [可选]
    │
    ▼
Step 3: Analyze (分析)
    │
    ▼
Step 4: Optimize (优化)
    │
    ▼
Step 5: Apply (应用)
    │
    ▼
完成
```

---

## 3. 各阶段输入输出

### Step 0: Parse (解析输入)

**输入**: 用户输入文本

**处理**: 解析输入类型 + 提取目标

**输出**: Target列表

**产物**: 无

---

### Step 1: Scan (扫描)

**输入**:
- 文件路径: src/main/resources/UserMapper.xml
- 配置: scan.mapper_globs
- [DB配置]: 如需要验证则需要

**处理**:
1. 解析XML文件
2. 提取SQL语句
3. 展开动态标签(if/foreach/choose) → 生成执行模板

**输出**:
- SQL单元列表
- 分支执行模板

**产物**: steps/1_scan/
- status.json              # 扫描状态
- scan.sqlunits.jsonl     # SQL单元列表
- scan.branches.jsonl     # 分支执行模板

---

### Step 2: Execute (执行) [可选]

**输入**:
- scan.branches.jsonl    # 分支执行模板
- DB连接: dsn配置

**处理**:
- real模式: 实际执行SQL，采集EXPLAIN + 性能数据
- mock模式: LLM推测执行计划

**输出**:
- 每个分支的执行计划
- 每个分支的实际耗时
- 每个分支的返回行数

**产物**: steps/2_execute/
- status.json              # 执行状态
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
1. 分析问题 (全表扫描/缺少索引/LIMIT等)
2. 判断复杂度 (简单/复杂)
3. 选择优化方式 (规则/大模型)

**输出**:
- 问题列表
- 优化方向
- 复杂度判断

**产物**: steps/3_analyze/
- status.json              # 分析状态
- analysis.json            # 分析报告

**analysis.json 示例**:
```json
{
  "issues": [
    {"type": "FULL_SCAN", "severity": "HIGH"},
    {"type": "NO_LIMIT", "severity": "MEDIUM"}
  ],
  "complexity": "simple",
  "optimization_method": "rules"
}
```

---

### Step 4: Optimize (优化)

**输入**:
- analysis.json           # 分析结果
- rules/                 # 规则Skill (如用规则)
- llm/                   # LLM接口 (如用大模型)

**处理**:
- 规则优化: 应用固化规则生成优化建议
- 大模型优化: LLM生成优化建议 + Diff

**输出**:
- 优化建议列表
- 预测性能提升
- Diff内容 (如需要)

**产物**: steps/4_optimize/
- status.json              # 优化状态
- proposals/               # 优化建议
- diff/                   # Diff内容 (如用大模型)

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
- diff/                   # Diff内容

**处理**:
1. 生成最终Diff
2. 展示给用户确认
3. 用户确认后修改XML

**输出**:
- 修改后的XML
- 修改对比

**产物**: steps/5_apply/
- status.json              # 应用状态
- diff/                    # 最终Diff
- modified/                # 修改后的文件

---

## 4. 完整产物结构

```
task_20240315_001/
├── requirements.md          # 需求文档
├── plan.md                 # 方案文档
├── tasks.md               # 任务清单
├── steps/
│   ├── 1_scan/
│   │   ├── status.json
│   │   ├── scan.sqlunits.jsonl
│   │   └── scan.branches.jsonl
│   ├── 2_execute/                  [可选]
│   │   ├── status.json
│   │   └── execute_results.jsonl
│   ├── 3_analyze/
│   │   ├── status.json
│   │   └── analysis.json
│   ├── 4_optimize/
│   │   ├── status.json
│   │   ├── proposals/
│   │   └── diff/                   [可选]
│   └── 5_apply/
│       ├── status.json
│       ├── diff/
│       └── modified/
└── summary.md               # 执行总结
```

---

## 5. 交互节点

| 节点 | 交互内容 | 触发条件 |
|------|----------|----------|
| **数据库配置** | 提示配置DSN | 需要验证但未配置时 |
| **执行模式** | real vs mock | optimize开始时 |
| **确认修改** | 是否执行修改 | apply前确认 |

---

## 6. 执行模式参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--mode` | `real` | 实际执行，需要数据库 |
| `--mode` | `mock` | Mock模式，不需要数据库 |
| `--method` | `rules` | 使用规则优化 |
| `--method` | `diff` | 使用大模型Diff |

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
