# SQL Optimizer 快速入门

目标：在项目里跑通一轮完整流程，并拿到 `report.json` 与 patch 结果。

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
cat runs/<run-id>/report.json
cat runs/<run-id>/sql/catalog.jsonl
PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id <run-id>
```

重点产物：
- `runs/<run-id>/control/state.json`
- `runs/<run-id>/control/plan.json`
- `runs/<run-id>/control/manifest.jsonl`
- `runs/<run-id>/report.json`
- `runs/<run-id>/artifacts/patches.jsonl`
- `runs/<run-id>/sql/catalog.jsonl`

## 6. 常见分支

- 只想先验证扫描：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage scan
```

- 手动跑仓库内 sample project：

```bash
# 长期使用建议：统一走 sample_project 包装脚本
python3 scripts/run_sample_project.py
python3 scripts/run_sample_project.py \
  --scope mapper \
  --mapper-path src/main/resources/com/example/mapper/user/advanced_user_mapper.xml
python3 scripts/run_sample_project.py \
  --scope sql \
  --sql-key demo.user.advanced.listUsersFilteredAliased

# 查看最新 run
cat tests/fixtures/projects/sample_project/runs/index.json

# 查看某次 run 的核心产物
cat tests/fixtures/projects/sample_project/runs/<run-id>/report.json
cat tests/fixtures/projects/sample_project/runs/<run-id>/control/state.json
cat tests/fixtures/projects/sample_project/runs/<run-id>/sql/catalog.jsonl
```

说明：
- `run_sample_project.py` 底层直接调用 `sqlopt_cli.py run`
- `runs/` 会保留在 `tests/fixtures/projects/sample_project/` 下
- 如果只是想先看目录输出效果，可临时改用 `llm.provider=heuristic`
- 日常开发默认已切到 optimize replay；测试和录制方式见 [`LLM_REPLAY.md`](LLM_REPLAY.md)

- replay 方式跑 `sample_project` / `generalization`：

```bash
python3 scripts/run_sample_project.py --scope generalization-batch1 --to-stage optimize
python3 scripts/ci/generalization_refresh.py --max-seconds 240
```

- 需要刷新某条 SQL 的 cassette 时，再显式切到 `record`：

```bash
python3 scripts/run_sample_project.py \
  --scope sql \
  --sql-key demo.user.countUser \
  --to-stage optimize \
  --llm-mode record \
  --max-seconds 180
```

- MySQL 方言边界（例如 `ILIKE`）不会自动兼容；语法问题会在 report 的 warnings 体现。

## 7. 下一步

- 安装细节：[`INSTALL.md`](INSTALL.md)
- 配置约定：[`CONFIG.md`](CONFIG.md)
- LLM replay / cassette：[`LLM_REPLAY.md`](LLM_REPLAY.md)
- 故障排查：[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
- 当前规格：[`current-spec.md`](current-spec.md)
