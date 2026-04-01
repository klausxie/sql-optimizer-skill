# SQL Optimizer

面向 MyBatis SQL 的分析与优化工具链，支持从扫描到补丁应用的可恢复工作流。

## 核心能力

- 端到端流程：`run -> status/resume -> report -> apply`
- 可恢复执行：支持中断后继续，支持 `report-rebuild`
- 产物可追溯：`runs/<run-id>/` 下保留状态、报告与中间产物
- proof-driven patching：`validate` 持久化 `patchTarget`，`patch_generate` 只消费该 contract
- 自动补丁门槛：仅对 frozen safe-baseline families 输出 `AUTO_PATCH`，且必须同时通过 replay、syntax、`git apply --check`
- 支持数据库：`postgresql`、`mysql`（5.6+，不含 MariaDB）

## 快速开始

### 1) 环境准备

```bash
# 设置 PYTHONPATH
export PYTHONPATH=$(pwd)/python

# 或在每次命令前添加
PYTHONPATH=python python3 scripts/sqlopt_cli.py --help
```

### 2) 最短运行链路

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml
PYTHONPATH=python python3 scripts/sqlopt_cli.py status
PYTHONPATH=python python3 scripts/sqlopt_cli.py resume
PYTHONPATH=python python3 scripts/sqlopt_cli.py apply
```

如果 `status.next_action=report-rebuild`：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage report --run-id <run-id>
```

## 常用命令

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py status --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --help
PYTHONPATH=python python3 scripts/sqlopt_cli.py validate-config --config sqlopt.yml
```

局部调试优先：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml \
  --mapper-path src/main/resources/com/example/mapper/user/advanced_user_mapper.xml \
  --sql-key demo.user.advanced.listUsersFilteredAliased#v17
```

当前推荐：日常开发优先局部 run，full run 只用于阶段验收。

## 关键边界

- PostgreSQL 方言（如 `ILIKE`）在 MySQL 平台不会自动兼容
- 此类语法问题会在 report 中以 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR` 暴露
- `status/resume/apply` 省略 `--run-id` 时自动选择最新 run（可用 `--project` 限定目录）

## 文档入口

- [快速入门](docs/QUICKSTART.md)
- [安装指南](docs/INSTALL.md)
- [配置参考](docs/CONFIG.md)
- [文档导航](docs/INDEX.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [当前规格](docs/current-spec.md)

## 开发与验收

```bash
python3 -m pytest -q
python3 scripts/ci/release_acceptance.py
```
