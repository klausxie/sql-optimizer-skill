# SQL Optimizer Skill

面向 MyBatis SQL 的分析与优化工具链，支持从发现到补丁应用的 V8 可恢复工作流。

## 核心能力

- **V8 七阶段流水线**：Discovery → Branching → Pruning → Baseline → Optimize → Validate → Patch
- 可恢复执行：支持中断后继续，支持 `report-rebuild`
- 产物可追溯：`runs/<run-id>/` 下保留状态、报告与中间产物
- 支持数据库：`postgresql`、`mysql`（5.6+，不含 MariaDB）

## V8 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         7 阶段处理流程                                      │
│                                                                           │
│  [1.发现] → [2.分支] → [3.剪枝] → [4.基线] → [5.优化] → [6.验证] → [7.补丁] │
└─────────────────────────────────────────────────────────────────────────────┘
```

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

## 安装方式

### 全局安装（推荐）

安装到 OpenCode 全局技能目录：

```bash
# Linux / macOS
python3 install/install_skill.py

# Windows (PowerShell)
python install/install_skill.py
```

验证安装：

```bash
# Linux / macOS
python3 install/install_skill.py --verify

# Windows
python install/install_skill.py --verify
```

安装后技能位置：
- Linux/macOS: `~/.opencode/skills/sql-optimizer/`
- Windows: `%USERPROFILE%\.opencode\skills\sql-optimizer\`

> 安装时会自动覆盖旧版本，无需额外操作。

### 项目内安装

安装到指定项目的 `.sqlopt` 目录：

```bash
# Linux / macOS
python3 install/install_skill.py --project /path/to/your/project

# Windows
python install/install_skill.py --project C:\path\to\project
```

### 自定义目录

安装到任意指定目录：

```bash
# Linux / macOS
python3 install/install_skill.py --project /custom/path/sqlopt-skill

# Windows
python install/install_skill.py --project C:\custom\path\sqlopt-skill
```

## 在 OpenCode 中使用

### 1. 启动 OpenCode

在项目根目录启动 OpenCode：

```bash
opencode
```

### 2. 使用 Skill

当处理 MyBatis SQL 优化任务时，OpenCode 会自动加载 sql-optimizer skill。

#### OpenCode 命令方式

Skill 提供以下命令：

| 命令 | 说明 | 使用方式 |
|------|------|----------|
| `/sql-run` | 执行完整 V8 流程 | `/sql-run --config sqlopt.yml` |
| `/sql-resume` | 恢复中断的运行 | `/sql-resume --run-id <run-id>` |
| `/sql-status` | 查看运行状态 | `/sql-status --run-id <run-id>` |
| `/sql-apply` | 应用补丁 | `/sql-apply --run-id <run-id>` |
| `/sql-verify` | 验证证据链 | `/sql-verify --run-id <run-id>` |

#### 自然语言方式

也可以直接用自然语言描述需求：

```
帮我优化 listUsers 这个 SQL
继续之前的优化
查看运行状态
应用补丁
```

#### 完整优化流程

```bash
# 1. 验证配置
sqlopt-cli validate-config --config sqlopt.yml

# 2. 执行完整 V8 流程
sqlopt-cli run --config sqlopt.yml

# 3. 查看状态
sqlopt-cli status --run-id <run-id>

# 4. 如中断，恢复运行
sqlopt-cli resume --run-id <run-id>

# 5. 应用补丁
sqlopt-cli apply --run-id <run-id>
```

### 3. Skill 与 CLI 的协作

```
┌─────────────────────┐          ┌─────────────────────┐
│   sqlopt-cli       │          │   OpenCode Skill   │
├─────────────────────┤          ├─────────────────────┤
│                     │          │                     │
│  • 扫描 MyBatis   │          │  • 调用 LLM        │
│  • 生成分支       │─────────▶│  • 生成建议         │
│  • 静态规则检测   │  prompt   │  • 决策判断         │
│  • 构建 LLM prompt│          │  • 用户交互         │
│  • 执行 SQL       │          │                     │
│  • 生成补丁       │          │                     │
│                     │          │                     │
└─────────────────────┘          └─────────────────────┘
```

**职责分离**：
- **CLI**：工程化能力（扫描、执行、构建 prompt）
- **Skill**：AI 能力（调用 LLM、生成建议）

## 快速开始

### 1) 安装

```bash
python3 install/install_skill.py
python3 install/install_skill.py --verify
```

### 2) 创建配置文件

在项目根目录创建 `sqlopt.yml`：

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:password@localhost:5432/dbname

llm:
  enabled: true
  provider: opencode_run
```

### 3) 开始使用

```bash
# 验证配置
sqlopt-cli validate-config --config sqlopt.yml

# 执行优化
sqlopt-cli run --config sqlopt.yml
```

## 常见问题

### 恢复中断的运行

```bash
sqlopt-cli resume --run-id <run-id>
```

### 查看运行状态

```bash
sqlopt-cli status --run-id <run-id>
```

### 局部调试

```bash
# 只诊断特定 SQL
sqlopt-cli run --config sqlopt.yml --sql-key <sqlKey>
```

## 数据存储结构

```
runs/<run_id>/
├── sqlmap_catalog/           # SQL 目录
│   ├── index.json          # 索引文件
│   └── <sql_key>.json     # 单个 SQL 详情
├── branches/               # 分支数据
├── risks/                  # 风险数据
├── baseline/               # 基线数据
├── proposals/              # 优化建议
├── acceptance/             # 验证结果
├── patches/               # 补丁文件
└── supervisor/            # 运行状态
```

## 关键边界

- PostgreSQL 方言（如 `ILIKE`）在 MySQL 平台不会自动兼容
- 此类语法问题会在报告中以 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR` 暴露
- 省略 run-id 时自动选择最新运行

## 文档入口

- [V8 架构总览](docs/V8/V8_SUMMARY.md) — V8 版本架构总览与实现状态
- [V8 阶段详解](docs/V8/V8_STAGES_OVERVIEW.md) — 7 阶段功能全景图
- [快速入门](docs/QUICKSTART.md)
- [安装指南](docs/INSTALL.md)
- [文档导航](docs/INDEX.md)
- [故障排查](docs/TROUBLESHOOTING.md)

## 开发与验收

```bash
python3 -m pytest -q
python3 scripts/ci/release_acceptance.py
```
