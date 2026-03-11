# SQL Optimizer Skill

面向 MyBatis SQL 的分析与优化工具链，支持从扫描到补丁应用的可恢复工作流。

## 核心能力

- 端到端流程：`run -> status/resume -> report -> apply`
- 可恢复执行：支持中断后继续，支持 `report-rebuild`
- 产物可追溯：`runs/<run-id>/` 下保留状态、报告与中间产物
- 支持数据库：`postgresql`、`mysql`（5.6+，不含 MariaDB）

## 快速开始

### 1) 安装

```bash
python3 install/install_skill.py
python3 install/install_skill.py --verify
```

### 2) 最短运行链路

```bash
sqlopt-cli run --config sqlopt.yml
sqlopt-cli status
sqlopt-cli resume
sqlopt-cli apply
```

如果 `status.next_action=report-rebuild`：

```bash
sqlopt-cli run --config sqlopt.yml --to-stage report --run-id <run-id>
```

## 常用命令

```bash
sqlopt-cli --help
sqlopt-cli run --help
sqlopt-cli resume --help
sqlopt-cli status --help
sqlopt-cli apply --help
sqlopt-cli validate-config --config sqlopt.yml
```

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
