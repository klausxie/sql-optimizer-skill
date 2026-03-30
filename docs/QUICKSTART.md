# SQL Optimizer 快速入门（15 分钟）

目标：在项目里完成一轮可恢复的 SQL 优化运行，并拿到报告与补丁。

## 1. 前置条件

- Python 3.9+
- MyBatis XML mapper 文件
- 数据库（PostgreSQL 或 MySQL 5.6+）
  仅安装链路 smoke 时可先使用离线配置（`llm.provider=opencode_builtin`）

## 2. 克隆并设置环境

```bash
git clone <repository-url>
cd sql-optimizer-skill

# 设置 PYTHONPATH
export PYTHONPATH=$(pwd)/python

# 安装依赖
pip install -r install/requirements.txt

# 验证安装
PYTHONPATH=python python3 scripts/sqlopt_cli.py --help
```

## 3. 准备最小配置

在项目根目录创建或确认 `sqlopt.yml`：

```yaml
project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:pass@127.0.0.1:5432/db?sslmode=disable

llm:
  enabled: true
  provider: opencode_run
```

离线 smoke 推荐：

```yaml
llm:
  enabled: true
  provider: opencode_builtin
```

## 4. 跑通主流程

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml
PYTHONPATH=python python3 scripts/sqlopt_cli.py status
PYTHONPATH=python python3 scripts/sqlopt_cli.py resume
```

说明：
- `run` 默认持续推进到完成（除非失败/中断）。
- `status/resume/apply` 省略 `--run-id` 时会自动选择最新 run。

如果 `status.next_action=report-rebuild`：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage report --run-id <run-id>
```

## 5. 查看产物并应用补丁

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py status --run-id <run-id>
cat runs/<run-id>/overview/report.summary.md
cat runs/<run-id>/overview/report.md
PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id <run-id>
```

重点产物：
- `runs/<run-id>/pipeline/supervisor/state.json`
- `runs/<run-id>/overview/report.json`
- `runs/<run-id>/overview/report.summary.md`（摘要）
- `runs/<run-id>/overview/report.md`（详细版）
- `runs/<run-id>/pipeline/patch_generate/patch.results.jsonl`

## 6. 常见分支

- 只想先验证扫描：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage scan
```

- MySQL 方言边界（例如 `ILIKE`）不会自动兼容；语法问题会在 report 的 warnings 体现。

## 7. 下一步文档

- 安装细节：[`INSTALL.md`](INSTALL.md)
- 故障排查：[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
- 配置约定：[`CONFIG.md`](CONFIG.md)
- 命令与状态机：[`project/03-workflow-and-state-machine.md`](project/03-workflow-and-state-machine.md)