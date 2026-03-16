# AGENTS.md - SQL Optimizer Skill 知识库

> 本文件为 AI 助手提供项目上下文，帮助理解代码结构、约定和最佳实践。

---

## 项目概述

SQL Optimizer 是一个 Python 工具，用于：
1. 扫描 MyBatis XML 映射文件中的 SQL 语句
2. 通过 LLM 生成优化建议
3. 在数据库上验证优化效果
4. 生成可应用的 XML 补丁

**支持数据库**: PostgreSQL, MySQL 5.6+ (不支持 MariaDB)

**设计目标**: 可恢复执行、产物可追溯、端到端工作流

---

## 目录结构

```
python/sqlopt/
├── application/          # 业务流程编排层
│   ├── workflow_engine.py    # 核心工作流引擎
│   ├── run_service.py        # Run 生命周期管理
│   ├── run_repository.py     # Run 状态持久化
│   └── config_service.py     # 配置加载验证
│
├── stages/               # 阶段处理 (固定顺序)
│   ├── diagnose.py           # 诊断阶段 (scan + branch + baseline)
│   ├── optimize.py           # LLM 优化建议
│   ├── validate.py           # 数据库验证
│   ├── apply.py              # 补丁应用
│   └── report.py             # 报告聚合
│
├── scripting/            # 分支推断 (新增)
│   ├── branch_generator.py   # 核心分支生成器
│   ├── sql_node.py           # SQL 节点树
│   ├── ast_utils.py          # AST 工具
│   └── ...
│
├── baseline/             # 性能基线 (新增)
│   ├── baseline_service.py   # 基线采集服务
│   └── ...
│
├── commands/             # CLI 命令实现
│   └── ...
│
├── platforms/            # SQL 方言
│   ├── postgresql/
│   └── mysql/
│
├── adapters/             # 适配器
│   └── branch_*.py           # 分支相关适配器
│
└── cli.py                # CLI 入口

tests/                    # 测试 (98+ 文件)
contracts/                # JSON Schema (15 文件)
docs/                     # 文档
scripts/                  # CI/工具脚本
install/                  # 安装脚本
java/                     # Java 相关 (已移除扫描器)
```

---

## 核心入口

| 入口 | 路径 | 说明 |
|------|------|------|
| CLI 脚本 | `scripts/sqlopt_cli.py` | 主入口 |
| CLI 命令 | `python/sqlopt/cli.py` | 子命令路由 |
| 工作流引擎 | `python/sqlopt/application/workflow_engine.py` | 阶段编排 |
| 分支推断 | `python/sqlopt/scripting/branch_generator.py` | BranchGenerator |
| Schema | `contracts/*.schema.json` | 数据契约 |

---

## 常用命令

### 开发与测试

```bash
# 运行所有测试
python3 -m pytest -q

# 运行单个测试
python3 -m pytest tests/test_scripting_branch_generator.py -v

# 发布验收
python3 scripts/ci/release_acceptance.py

# Schema 验证
python3 scripts/schema_validate_all.py
```

### CLI 使用

```bash
# 运行优化
sqlopt-cli run --config sqlopt.yml

# 查看状态
sqlopt-cli status --run-id <run_id>

# 恢复运行
sqlopt-cli resume --run-id <run_id>

# 应用补丁
sqlopt-cli apply --run-id <run_id>

# 验证证据链
sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey>
```

### 局部调试

```bash
# 调试单个 SQL
sqlopt-cli run --config sqlopt.yml \
  --mapper-path path/to/mapper.xml \
  --sql-key <sqlKey>
```

---

## 阶段流水线

```
diagnose → optimize → validate → apply → report
```

**阶段特性**:
- 固定执行顺序
- 通过 `runs/<run_id>/` 产物通信
- 失败时写入诊断事件
- `report` 阶段可单独重建

---

## 配置结构

配置文件: `sqlopt.yml`

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
  provider: opencode_run  # 推荐
```

---

## 数据契约

所有阶段产物必须符合 `contracts/` 下的 JSON Schema:

| Schema | 用途 |
|--------|------|
| `sqlunit.schema.json` | 扫描 SQL 单元 |
| `fragment_record.schema.json` | SQL 片段 |
| `optimization_proposal.schema.json` | 优化建议 |
| `acceptance_result.schema.json` | 验证结果 |
| `patch_result.schema.json` | 补丁结果 |

**关键**: Schema 验证失败默认终止运行

---

## Run 目录结构

```
runs/<run_id>/
├── supervisor/
│   ├── meta.json         # 运行元信息
│   ├── plan.json         # 固定语句列表
│   ├── state.json        # 阶段状态
│   └── results/          # 步骤结果
├── scan.sqlunits.jsonl   # 扫描产物
├── proposals/            # 优化建议
├── acceptance/           # 验证结果
├── patches/              # 补丁产物
├── verification/         # 验证证据链
├── report.json           # JSON 报告
├── report.md             # Markdown 报告
└── report.summary.md     # 摘要报告
```

---

## 分支推断 (新增功能)

```
MyBatis XML (含动态标签)
    ↓
解析为 SqlNode 树
    ↓
生成所有执行分支 (if/choose/foreach)
    ↓
风险标记
    ↓
诊断报告
```

**风险类型**:
| 标记 | 模式 | 风险等级 |
|------|------|----------|
| `prefix_wildcard` | `'%'+name+'%'` | 高 |
| `suffix_wildcard_only` | `name+'%'` | 低 |
| `concat_wildcard` | `CONCAT('%',name)` | 高 |
| `function_wrap` | `UPPER(name)` | 中 |

---

## 约定俗成

### 代码风格
- **测试**: pytest
- **包结构**: `python/sqlopt/`
- **CLI**: argparse 子命令模式
- **配置**: YAML
- **产物**: JSONL/JSON

### 命名约定
- 阶段名称: `diagnose`, `optimize`, `validate`, `apply`, `report`
- 配置版本: `v1`
- Run ID: `run_<timestamp>_<random>`

### 测试约定
- 测试文件: `tests/test_*.py`
- Fixtures: `tests/fixtures/`
- 验收脚本: `scripts/ci/*_acceptance.py`

---

## 反模式 (禁止)

| 反模式 | 原因 |
|--------|------|
| ❌ 阶段直接互调 | 必须通过 orchestrator |
| ❌ 自然语言阶段输出 | 必须是结构化对象 |
| ❌ `as any`, `@ts-ignore` | 破坏类型安全 |
| ❌ 动态模板用平面 SQL 覆盖 | 丢失动态性 |
| ❌ 恢复时重试已完成语句 | 浪费资源 |
| ❌ 删除失败测试来"通过" | 掩盖问题 |

---

## 架构决策

### 1. 移除 Java 扫描器
- **决策**: 完全使用 Python 实现
- **原因**: 简化依赖，提高可维护性
- **替代**: `scripting/` 模块的分支推断

### 2. 分支推断不精确渲染
- **决策**: 只需渲染可执行 SQL 模板
- **原因**: 主要关注性能问题，不需要完全精确的内容
- **影响**: 类型推断不需要

### 3. 可恢复执行
- **决策**: 每次调用只推进一个语句步骤
- **原因**: 尊重 120s 超时限制
- **实现**: supervisor 状态管理

---

## 用户使用流程

### 完整优化流程

```bash
# 1. 启动优化
sqlopt-cli run --config sqlopt.yml

# 2. 检查状态
sqlopt-cli status

# 3. 如中断，恢复运行
sqlopt-cli resume --run-id <run_id>

# 4. 查看报告
cat runs/<run_id>/report.summary.md

# 5. 应用补丁 (可选)
sqlopt-cli apply --run-id <run_id>
```

### 分支诊断流程

```bash
# 分支分析
sqlopt-cli branch --mapper "src/**/*.xml" --dsn postgresql://...

# 性能基线
sqlopt-cli baseline --mapper "src/**/*.xml" --dsn postgresql://...
```

---

## 文档索引

| 文档 | 用途 |
|------|------|
| `docs/QUICKSTART.md` | 10分钟快速入门 |
| `docs/INDEX.md` | 完整文档导航 |
| `docs/INSTALL.md` | 安装指南 |
| `docs/TROUBLESHOOTING.md` | 故障排查 |
| `docs/project/02-system-spec.md` | 系统规格 |
| `docs/project/03-workflow-and-state-machine.md` | 工作流 |
| `docs/project/04-data-contracts.md` | 数据契约 |

---

## 已知限制

1. MySQL 5.6 不支持 `MAX_EXECUTION_TIME`
2. PostgreSQL 方言 (如 `ILIKE`) 不会自动转换 MySQL
3. 模板级补丁需要 `rewriteMaterialization.replayVerified=true`
4. 报告阶段可重建，其他阶段不行

---

## 优先级规则

冲突时按以下顺序处理:
1. `contracts/*.schema.json` (最高)
2. 当前代码行为 (`python/sqlopt/`)
3. 历史文档 (`docs/`)
