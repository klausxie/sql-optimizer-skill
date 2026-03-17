# SQL Optimizer Skill

面向 MyBatis SQL 的分析与优化工具链，支持从扫描到补丁应用的可恢复工作流。

## 核心能力

- 端到端流程：`run -> status/resume -> report -> apply`
- 可恢复执行：支持中断后继续，支持 `report-rebuild`
- 产物可追溯：`runs/<run-id>/` 下保留状态、报告与中间产物
- 支持数据库：`postgresql`、`mysql`（5.6+，不含 MariaDB）

## 安装方式

### 方式一：全局安装（推荐）

安装到 OpenCode 全局技能目录：

```bash
python3 install/install_skill.py
python3 install/install_skill.py --verify
```

安装后技能位置：`~/.opencode/skills/sql-optimizer/`

> 安装时会自动覆盖旧版本，无需额外操作。

### 方式二：项目内安装

安装到指定项目的 `.sqlopt` 目录：

```bash
python3 install/install_skill.py --project /path/to/your/project
```

这会在项目根目录创建 `.sqlopt/` 目录存放技能文件。

> 安装时会自动覆盖旧版本，无需额外操作。

### 方式三：自定义目录

安装到任意指定目录：

```bash
python3 install/install_skill.py --project /custom/path/sqlopt-skill
```

### 覆盖安装说明

多次安装时会自动覆盖旧版本：

```bash
# 首次安装
python3 install/install_skill.py

# 再次安装（自动覆盖，无需额外参数）
python3 install/install_skill.py
```

如需手动删除后安装：

```bash
# 全局安装的卸载
rm -rf ~/.opencode/skills/sql-optimizer/

# 项目安装的卸载
rm -rf /path/to/your/project/.sqlopt

# 然后重新安装
python3 install/install_skill.py
```

## 在 OpenCode 中使用

### 1. 启动 OpenCode

在项目根目录启动 OpenCode：

```bash
opencode
```

### 2. 使用 Skill

当处理 MyBatis SQL 优化任务时，OpenCode 会自动加载 sql-optimizer skill。

#### 常用工作流

**完整优化流程**：

```bash
# 1. 验证配置
sqlopt-cli validate-config --config sqlopt.yml

# 2. 运行优化（Skill 会引导你完成各个阶段）
sqlopt-cli run --config sqlopt.yml

# 3. 查看状态
sqlopt-cli status

# 4. 如中断，恢复运行
sqlopt-cli resume --run-id <run_id>

# 5. 应用补丁
sqlopt-cli apply --run-id <run_id>
```

**诊断单个 SQL**：

```bash
sqlopt-cli run --config sqlopt.yml \
  --mapper-path src/main/resources/com/example/mapper/user_mapper.xml \
  --sql-key listUsers
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

### 3) 最短运行链路

```bash
sqlopt-cli validate-config --config sqlopt.yml
sqlopt-cli run --config sqlopt.yml
sqlopt-cli status
sqlopt-cli apply
```

建议先让 `validate-config` 检查 `db.dsn`、mapper 匹配结果和数据库连通性；如果这里已经失败，不要直接继续 full run。

如果 `status.next_action=report-rebuild`：

```bash
sqlopt-cli run --config sqlopt.yml --to-stage report --run-id <run-id>
```

## 常用命令

```bash
sqlopt-cli --help
sqlopt-cli run --help
sqlopt-cli validate-config --help
sqlopt-cli resume --help
sqlopt-cli status --help
sqlopt-cli apply --help
```

局部调试优先：

```bash
sqlopt-cli run --config sqlopt.yml \
  --mapper-path src/main/resources/com/example/mapper/user/advanced_user_mapper.xml \
  --sql-key listUsersFilteredAliased
```

`--sql-key` 支持完整 `sqlKey`、`namespace.statementId`、`statementId`、`statementId#vN`。如果只给 `statementId` 且命中多个 SQL，CLI 会列出候选 full key。

当前推荐：日常开发优先局部 run，full run 只用于阶段验收。

## 关键边界

- PostgreSQL 方言（如 `ILIKE`）在 MySQL 平台不会自动兼容
- 此类语法问题会在 report 中以 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR` 暴露
- `status/resume/apply` 省略 `--run-id` 时自动选择最新 run（可用 `--project` 限定目录）

## 文档入口

- [快速入门](docs/QUICKSTART.md)
- [安装指南](docs/INSTALL.md)
- [文档导航](docs/INDEX.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [系统规格](docs/project/02-system-spec.md)
- [工作流与状态机](docs/project/03-workflow-and-state-machine.md)
- [数据契约](docs/project/04-data-contracts.md)
- [SQL 补丁能力架构](docs/project/10-sql-patchability-architecture.md)

## 开发与验收

```bash
python3 -m pytest -q
python3 scripts/ci/release_acceptance.py
```

## 架构设计

- **功能全景图**：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 完整功能架构和执行流程

> 推荐先阅读功能全景图，了解整体设计后再深入其他文档。
