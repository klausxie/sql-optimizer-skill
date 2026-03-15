---
name: sql-optimizer
description: 面向 MyBatis 项目的 SQL 优化 Skill，支持三种执行模式(单条/多条/批量)，5步优化流程，规则+大模型双模式优化。
---

# SQL Optimizer Skill

## 概述

SQL Optimizer 是一个用于优化 MyBatis SQL 的 Skill，支持：
- 三种执行模式：单条SQL、多条指定SQL、批量文件
- 5步优化流程
- 规则+大模型双模式优化

## 执行模式

| 模式 | 说明 | 示例 |
|------|------|------|
| 单条SQL | 优化单条SQL | "优化这条SQL: select * from users" |
| 多条指定SQL | 优化指定的多条SQL | "优化findUsers, findOrders这3个方法" |
| 批量文件 | 优化整个Mapper文件 | "优化UserMapper.xml" |

## 执行流程

```
用户输入
    │
    ▼
Step 1: Scan (扫描)
    │
    ▼
Step 2: Optimize (优化)
    │
    ▼
Step 3: Validate (验证)
    │
    ▼
Step 4: Patch Generate (生成补丁)
    │
    ▼
Step 5: Report (报告)
    │
    ▼
完成
```

## 详细流程

### Step 1: Scan (扫描)
解析XML文件，提取SQL，展开动态标签(if/foreach/choose)

### Step 2: Optimize (优化)
- 简单场景 → 规则优化 (Rules Skill)
- 复杂场景 → 大模型优化 (LLM)

### Step 3: Validate (验证)
在数据库上验证优化效果

### Step 4: Patch Generate (生成补丁)
生成可应用的XML补丁

### Step 5: Report (报告)
生成优化报告

## 交互节点

| 节点 | 交互内容 | 触发条件 |
|------|----------|----------|
| 数据库配置 | 提示配置DSN | 需要验证但未配置时 |
| 执行模式 | real vs mock | optimize开始时 |
| 确认修改 | 是否执行修改 | apply前确认 |

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
