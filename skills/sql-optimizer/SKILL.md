---
name: sql-optimizer
description: 面向 MyBatis 项目的 SQL 优化 Skill。扫描识别慢 SQL → 执行获取性能数据 → 分析瓶颈 → 优化建议 → 应用补丁。支持精准范围分析。
---

# SQL Optimizer Skill

## 概述

SQL Optimizer 是一个用于优化 MyBatis SQL 的 Skill，支持：
- 三种执行模式：单条SQL、多条指定SQL、批量文件
- 5步优化流程
- 规则+大模型双模式优化

## 安装

### 全局安装

安装到全局配置目录（`~/.config/opencode/`）：

```bash
python install/install_skill.py --global
```

安装后：
- Skill: `~/.config/opencode/skills/sql-optimizer/`
- 命令: `~/.config/opencode/commands/sql-*.md`

### 项目安装

安装到项目目录（`<project>/.opencode/`）：

```bash
python install/install_skill.py --project /path/to/your/project
```

安装后：
- Skill: `<project>/.opencode/skills/sql-optimizer/`
- 命令: `<project>/.opencode/commands/sql-*.md`

### 选择哪种安装方式？

| 场景 | 推荐方式 |
|------|----------|
| 多项目共享同一版本 | 全局安装 |
| 项目需要独立版本 | 项目安装 |
| CI/CD 自动化 | 项目安装 |
| 个人开发环境 | 全局安装 |

## 执行模式

**核心原则**：用户指定哪个范围，就只分析哪个范围，不扩散。

| 模式 | 说明 | 示例 |
|------|------|------|
| 单个 SQL | 只分析指定的一个 SQL | "扫描 findUsers" |
| 多个 SQL | 只分析指定的几个 SQL | "扫描 findUsers, findOrders" |
| 文件范围 | 只分析指定文件 | "扫描 UserMapper.xml" |
| 配置批量 | 从配置文件读取范围 | "扫描 @sql-list.txt" |

**⚠️ 禁止行为**：
- 不要主动列出所有 SQL 让用户选择
- 不要在用户指定范围后扫描其他文件
- 不要在报告中列出无关的 SQL

## 执行流程

```
用户输入（指定范围）
    │
    ▼
Step 1: Scan (扫描)
    │  - 解析用户指定的范围
    │  - 提取 SQL，识别潜在慢 SQL
    │
    ▼
Step 2: Execute (执行) [交互提示]
    │  ⚠️ Agent 提示: "是否执行这些 SQL 获取实际性能数据？"
    │  - 用户确认后执行
    │  - 收集执行计划和耗时
    │
    ▼
Step 3: Analyze (分析)
    │  - 分析执行结果
    │  - 确认慢 SQL 及其瓶颈
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

## 详细流程

### Step 1: Scan (扫描)

**目标**：识别潜在的慢 SQL，不做深度优化建议

**输入范围**（用户指定哪个就只扫描哪个）：
- 单个 SQL ID：`findUsers`
- 多个 SQL ID：`findUsers, findOrders, findProducts`
- 文件范围：`UserMapper.xml`
- 配置文件批量：`@sql-list.txt`

**输出**：
- 潜在慢 SQL 列表（基于规则：SELECT *、LIKE %x%、缺少索引等）
- **不输出**：详细的优化建议（留到优化阶段）

### Step 2: Execute (执行)

**⚠️ 必须交互提示**：
```
发现 3 个潜在慢 SQL：
  - findUsers (可能全表扫描)
  - findOrders (LIKE 前缀通配符)
  - getReport (嵌套子查询)

是否执行这些 SQL 获取实际性能数据？[Y/n]
```

**执行后收集**：
- 实际执行时间
- EXPLAIN 分析结果
- 扫描行数 vs 返回行数

### Step 3: Analyze (分析)

**目标**：确认真正的慢 SQL 及其瓶颈

**分析内容**：
- 实际耗时排序
- 识别瓶颈（全表扫描、索引缺失、N+1 问题等）

### Step 4: Optimize (优化)

- 简单场景 → 规则优化 (Rules)
- 复杂场景 → 大模型优化 (LLM)

### Step 5: Apply (应用)

- 生成 XML 补丁
- 用户确认后应用

## 交互节点

| 节点 | 交互内容 | 触发条件 |
|------|----------|----------|
| **执行确认** | "是否执行这些 SQL 获取性能数据？" | 扫描完成后，必须提示 |
| 数据库配置 | 提示配置 DSN | 需要执行但未配置时 |
| 确认修改 | 是否应用补丁 | Apply 前确认 |

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

## 流程指引

```
/sql-scan → [提示执行] → /sql-execute → /sql-analyze → /sql-optimize → /sql-apply
    ↓                          ↓               ↓              ↓             ↓
 识别慢SQL    用户确认后执行    收集性能数据    确认瓶颈      生成补丁
```

**每个阶段的下一步建议**：
- 扫描后 → **必须提示用户**："是否执行获取性能数据？"
- 执行后 → 执行 `/sql-analyze` (分析执行结果)
- 分析后 → 执行 `/sql-optimize` (生成优化建议)
- 优化后 → 执行 `/sql-apply` (应用补丁)

## 扫描策略

**扫描阶段目标**：识别潜在的慢 SQL，不做深度优化建议。

### 慢 SQL 识别规则

| 规则 | 模式 | 风险等级 |
|------|------|----------|
| 全字段查询 | `SELECT *` | 高 |
| 前缀通配符 | `LIKE '%xxx'` | 高 |
| 双端通配符 | `LIKE '%xxx%'` | 高 |
| 函数包裹索引列 | `UPPER(column)` | 中 |
| 嵌套子查询 | `SELECT ... WHERE ... IN (SELECT ...)` | 中 |
| 无 WHERE 条件 | `DELETE FROM table` | 高 |

**扫描输出格式**：
```
发现 3 个潜在慢 SQL：

1. findUsers (UserMapper.xml:15)
   - 风险: SELECT * 全字段查询
   - 风险: LIKE '%name%' 双端通配符

2. findOrders (OrderMapper.xml:23)
   - 风险: 嵌套子查询

3. getReport (ReportMapper.xml:45)
   - 风险: UPPER(status) 函数包裹索引列

是否执行这些 SQL 获取实际性能数据？[Y/n]
```

### Maven 标准结构 (优先)

如果项目根目录有 `pom.xml`，自动使用以下搜索路径：

| 优先级 | 路径 | 说明 |
|--------|------|------|
| 1 | `src/main/resources/**/*.xml` | 标准 Maven 资源目录 |
| 2 | `src/main/resources/mapper/**/*.xml` | MyBatis mapper 子目录 |
| 3 | `src/main/resources/mybatis/**/*.xml` | MyBatis 配置子目录 |
| 4 | `**/*Mapper.xml` | 任意 Mapper 文件 |
| 5 | `**/*mapper.xml` | 任意小写 mapper 文件 |

### 自动排除

以下目录会被自动排除：
- `target/` - Maven 构建输出
- `.git/` - Git 目录
- `node_modules/` - Node.js 依赖
- `**/test/**` - 测试目录

## 分析范围限制

**重要**：当用户指定了特定的 SQL ID 或方法名时，只分析指定的 SQL，不要列出全部 SQL。

| 用户输入 | 正确行为 | 错误行为 |
|----------|----------|----------|
| "扫描 findUsers" | 只扫描 findUsers | 列出所有 SQL 再选一个 |
| "扫描 UserMapper.xml" | 只扫描 UserMapper.xml | 扫描所有 Mapper 文件 |
| "扫描 findUsers, findOrders" | 只扫描这两个方法 | 列出所有方法让用户选择 |
| "扫描所有 SQL" | 扫描全部 | - |

**精准分析原则**：
1. 用户指定了哪些 SQL，就只扫描哪些 SQL
2. 不要主动列出所有 SQL 让用户选择
3. 不要在报告中列出无关的 SQL
4. 保持输出简洁，聚焦用户关注的目标
