# SQL Optimizer 功能全景图 (V8)

> 最后更新: 2026-03-19

本文档描述 SQL Optimizer 的 V8 架构和执行流程。

---

## 1. V8 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          用户交互层                                          │
│  ┌─────────────────┐           ┌─────────────────┐                       │
│  │   sqlopt-cli   │           │  sqlopt-data   │                       │
│  │  (SQL优化)     │           │  (数据管理)     │                       │
│  └────────┬────────┘           └────────┬────────┘                       │
└───────────┼─────────────────────────────┼─────────────────────────────────┘
            │                             │
            └──────────┬──────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         7 阶段处理流程                                      │
│                                                                           │
│  [1.发现] → [2.分支] → [3.剪枝] → [4.基线] → [5.优化] → [6.验证] → [7.补丁] │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. V8 七阶段详解

### 阶段概览

| 阶段 | 名称 | 功能 | 耗时节点 |
|------|------|------|----------|
| 1 | Discovery | 连接数据库、采集表结构、解析 XML | DB 🐢 |
| 2 | Branching | 分支展开（3种策略） | - |
| 3 | Pruning | 静态分析、风险标记、聚合剪枝 | CPU ⚡ |
| 4 | Baseline | EXPLAIN、执行 SQL、采集性能 | DB 🐢 |
| 5 | Optimize | 规则引擎 + LLM 优化 | LLM ⏱️ |
| 6 | Validate | 语义验证、性能对比、结果集验证 | DB 🐢 |
| 7 | Patch | 生成补丁、用户确认、应用 | FS 💾 |

**图例**: 🐢 耗时操作(IO) | ⚡ 快速操作(CPU) | ⏱️ 大模型调用 | 📋 用户交互 | 💾 文件操作

### 各阶段详细功能

#### 阶段 1: Discovery（发现）
| 功能项 | 描述 |
|--------|------|
| 连接数据库 | 连接目标数据库，获取连接信息 |
| 采集表结构 | 获取所有表的列信息、索引、主键 |
| 解析 XML | 解析 MyBatis Mapper XML 文件 |
| 提取 SQL | 提取所有 SELECT/INSERT/UPDATE/DELETE 语句 |
| 识别动态 SQL | 识别 `<if>`, `<choose>`, `<foreach>` 等动态标签 |

#### 阶段 2: Branching（分支）
| 功能项 | 描述 |
|--------|------|
| 分支生成策略 | 支持三种策略：AllCombinations / Pairwise / Boundary |
| 条件展开 | 将动态 SQL 展开为具体分支 |
| 风险标记 | 标记每个分支的风险点 |

#### 阶段 3: Pruning（剪枝）
| 功能项 | 描述 |
|--------|------|
| 前缀通配符检测 | 检测 `LIKE '%value'` 模式 |
| 后缀通配符检测 | 检测 `LIKE 'value%'` 模式 |
| 函数包裹检测 | 检测 `WHERE UPPER(col) = ?` |
| SELECT * 检测 | 检测全列查询 |

#### 阶段 4: Baseline（基线）
| 功能项 | 描述 |
|--------|------|
| EXPLAIN 分析 | 执行 EXPLAIN 获取执行计划 |
| 性能采集 | 采集执行时间、扫描行数 |
| 统计信息 | 采集表统计信息 |

#### 阶段 5: Optimize（优化）
| 功能项 | 描述 |
|--------|------|
| 规则引擎 | 应用内置优化规则 |
| LLM 优化 | 调用 LLM 生成优化建议 |
| 候选生成 | 生成多个优化候选方案 |

#### 阶段 6: Validate（验证）
| 功能项 | 描述 |
|--------|------|
| 语义验证 | 验证优化后 SQL 语义等价 |
| 性能对比 | 对比优化前后性能 |
| 结果集验证 | 验证返回结果一致 |

#### 阶段 7: Patch（补丁）
| 功能项 | 描述 |
|--------|------|
| 补丁生成 | 生成 MyBatis XML 补丁 |
| 用户确认 | 等待用户确认 |
| 备份原文件 | 备份原始 XML |
| 应用补丁 | 将优化建议应用到 XML |

---

## 3. CLI 命令

| 命令 | 功能 | 典型用法 |
|------|------|----------|
| `validate-config` | 验证配置文件和数据库连通性 | `sqlopt-cli validate-config --config sqlopt.yml` |
| `run` | 从头开始执行 V8 优化流程 | `sqlopt-cli run --config sqlopt.yml` |
| `resume` | 继续已中断的运行 | `sqlopt-cli resume --run-id <run-id>` |
| `status` | 查看当前运行状态 | `sqlopt-cli status --run-id <run-id>` |
| `apply` | 应用生成的补丁 | `sqlopt-cli apply --run-id <run-id>` |

### 命令选项

- `--config`: 配置文件路径 (默认: `sqlopt.yml`)
- `--run-id`: 指定运行 ID
- `--to-stage`: 目标阶段
- `--sql-key`: 指定 SQL key
- `--mapper-path`: 指定 mapper 文件路径
- `--max-steps`: 最大步数限制
- `--max-seconds`: 最大时间限制
- `--force` (apply): 强制应用补丁，无需确认

---

## 4. 架构说明：CLI 与 Skill 分工

SQL Optimizer 采用 **CLI + Skill** 双层架构：

| 组件 | 职责 | 说明 |
|------|------|------|
| **CLI** | 工程化能力 | 扫描 XML、生成分支、构建 prompt、执行 SQL、应用补丁 |
| **Skill** | AI/LLM 能力 | 调用 LLM 生成优化建议 |

### 完整流程

```
CLI Discovery → CLI Branching → CLI Pruning → CLI Baseline → Skill Optimize → CLI Validate → CLI Patch
```

---

## 5. 核心模块 (V8 实现)

### 5.1 命令行入口
- `cli/main.py`: CLI 命令解析和路由

### 5.2 应用层
- `workflow_v8.py`: V8 工作流引擎，7阶段编排
- `run_service.py`: Run 生命周期管理
- `run_repository.py`: Run 状态持久化
- `config_service.py`: 配置加载验证

### 5.3 V8 阶段处理
```
stages/
├── discovery/      # 阶段1: 发现
├── branching/      # 阶段2: 分支
├── pruning/       # 阶段3: 剪枝
├── baseline/       # 阶段4: 基线
├── optimize/       # 阶段5: 优化
├── validate/       # 阶段6: 验证
└── patch/          # 阶段7: 补丁
```

---

## 6. 数据流与产物

### Run 目录结构

```
runs/<run_id>/
├── sqlmap_catalog/           # SQL 目录
│   ├── index.json          # 索引文件
│   └── <sql_key>.json     # 单个 SQL 详情
├── branches/               # 分支数据
├── risks/                  # 风险数据
├── baseline/               # 基线数据
├── proposals/              # 优化建议
├── acceptance/            # 验证结果
├── patches/               # 补丁文件
└── supervisor/            # 运行状态
    ├── meta.json
    ├── state.json
    └── plan.json
```

---

## 7. 配置结构

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql  # 或 mysql
  dsn: postgresql://user:pass@host:5432/db

llm:
  enabled: true
  provider: opencode_run

stages:
  branching:
    strategy: all_combinations  # all_combinations | pairwise | boundary
  pruning:
    risk_threshold: medium  # high | medium | low
  baseline:
    timeout_ms: 5000
  optimize:
    max_candidates: 3
  validate:
    verify_semantics: true
  patch:
    auto_backup: true
    require_confirm: true
```

---

## 8. 支持的数据库

| 数据库 | 支持版本 | 特殊限制 |
|--------|----------|----------|
| PostgreSQL | 全部 | 无 |
| MySQL | 5.6+ | 不支持 MariaDB |

---

## 9. 风险标记

| 风险类型 | 模式 | 风险等级 |
|----------|------|----------|
| `prefix_wildcard` | `'%'+name+'%'` | 高 |
| `suffix_wildcard_only` | `name+'%'` | 低 |
| `concat_wildcard` | `CONCAT('%',name)` | 高 |
| `function_wrap` | `UPPER(name)` | 中 |

---

## 10. 快速开始

```bash
# 1. 验证配置
sqlopt-cli validate-config --config sqlopt.yml

# 2. 运行优化
sqlopt-cli run --config sqlopt.yml

# 3. 查看状态
sqlopt-cli status --run-id <run-id>

# 4. 恢复运行（如中断）
sqlopt-cli resume --run-id <run-id>

# 5. 应用补丁
sqlopt-cli apply --run-id <run-id>
```

---

## 11. 已知限制

1. MySQL 5.6 不支持 `MAX_EXECUTION_TIME`
2. PostgreSQL 方言 (如 `ILIKE`) 不会自动转换 MySQL

---

## 12. 相关文档

- [V8 架构总览](V8/V8_SUMMARY.md)
- [V8 阶段详解](V8/V8_STAGES_OVERVIEW.md)
- [快速入门](QUICKSTART.md)
- [安装指南](INSTALL.md)
- [故障排查](TROUBLESHOOTING.md)
