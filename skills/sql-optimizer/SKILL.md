---
name: sql-optimizer
description: 面向 MyBatis 项目的 SQL 优化 Skill，支持三种执行模式(单条/多条/批量)，5步优化流程(Parse/Scan/Execute/Analyze/Optimize/Apply)，规则+大模型双模式优化。
---

# SQL Optimizer Skill (V2)

## 概述

SQL Optimizer 是一个用于优化 MyBatis SQL 的 Skill，支持：
- 三种执行模式：单条SQL、多条指定SQL、批量文件
- 5步优化流程
- 规则+大模型双模式优化

## 执行模式

| 模式 | 说明 | 示例 |
|------|------|------|
| 单条SQL | 优化单条SQL | `"优化这条SQL: select * from users"` |
| 多条指定SQL | 优化指定的多条SQL | `"优化findUsers, findOrders这3个方法"` |
| 批量文件 | 优化整个Mapper文件 | `"优化UserMapper.xml"` |

## 执行流程

```
用户输入
    │
    ▼
Step 1: Parse (解析输入)
    │
    ▼
Step 2: Scan (扫描)
    │
    ▼
Step 3: Execute (执行) [可选]
    │
    ▼
Step 4: Analyze (分析)
    │
    ▼
Step 5: Optimize (优化)
    │
    ▼
Step 6: Apply (应用)
    │
    ▼
完成
```

## 详细流程

### Step 1: Parse (解析输入)
解析用户输入，提取优化目标

### Step 2: Scan (扫描)
解析XML文件，提取SQL，展开动态标签

### Step 3: Execute (执行) [可选]
- real模式：实际执行SQL，采集EXPLAIN + 性能数据
- mock模式：LLM推测执行计划

### Step 4: Analyze (分析)
分析问题 + 判断复杂度 + 选择优化方式

### Step 5: Optimize (优化)
- 简单场景 → 规则优化 (Rules Skill)
- 复杂场景 → 大模型优化 (LLM)

### Step 6: Apply (应用)
生成Diff + 用户确认 + 修改XML

## 交互节点

| 节点 | 交互内容 | 触发条件 |
|------|----------|----------|
| 数据库配置 | 提示配置DSN | 需要验证但未配置时 |
| 执行模式 | real vs mock | optimize开始时 |
| 确认修改 | 是否执行修改 | apply前确认 |

## 配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--mode` | `real` | 实际执行，需要数据库 |
| `--mode` | `mock` | Mock模式，不需要数据库 |
| `--method` | `rules` | 使用规则优化 |
| `--method` | `diff` | 使用大模型Diff |

## 产物结构

```
task_xxx/
├── requirements.md      # 需求文档
├── plan.md            # 方案文档
├── tasks.md           # 任务清单
├── steps/
│   ├── 1_scan/
│   │   ├── status.json
│   │   ├── scan.sqlunits.jsonl
│   │   └── scan.branches.jsonl
│   ├── 2_execute/          [可选]
│   │   ├── status.json
│   │   └── execute_results.jsonl
│   ├── 3_analyze/
│   │   ├── status.json
│   │   └── analysis.json
│   ├── 4_optimize/
│   │   ├── status.json
│   │   └── proposals/
│   └── 5_apply/
│       ├── status.json
│       └── diff/
└── summary.md         # 执行总结
```

## 复杂度判断

| 场景 | 方式 |
|------|------|
| SELECT * | Rules |
| 缺少索引 | Rules |
| LIKE %xxx% | Rules |
| 业务逻辑复杂 | LLM |
| 多表关联 | LLM |
| 嵌套子查询 | LLM |

## 相关文档

- [功能全景图](../docs/ARCHITECTURE.md)
- [快速入门](../docs/QUICKSTART.md)
- [配置说明](../docs/CONFIG.md)
