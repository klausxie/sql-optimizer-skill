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

## 流程指引

```
/sql-scan → /sql-optimize → /sql-validate → /sql-patch → /sql-report
    ↓            ↓               ↓              ↓            ↓
  扫描XML     生成建议        验证效果       生成补丁      完成报告
```

**每个阶段的下一步建议**：
- 扫描后 → 执行 `/sql-optimize` (如果发现问题)
- 优化后 → 执行 `/sql-validate` (验证优化效果)
- 验证后 → 执行 `/sql-patch` (如果验证通过)
- 补丁后 → 执行 `/sql-report` (生成报告)

## 扫描策略

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
| "优化 findUsers 方法" | 只分析和优化 findUsers | 列出所有 SQL 再选一个 |
| "优化 UserMapper.xml" | 只分析 UserMapper.xml | 扫描所有 Mapper 文件 |
| "优化 findUsers, findOrders" | 只分析这两个方法 | 列出所有方法让用户选择 |
| "优化所有 SQL" | 扫描并分析全部 | - |

**精准分析原则**：
1. 用户指定了哪些 SQL，就只分析哪些 SQL
2. 不要主动列出所有 SQL 让用户选择
3. 不要在分析报告中列出无关的 SQL
4. 保持输出简洁，聚焦用户关注的目标
