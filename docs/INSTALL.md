# SQL Optimizer 安装指南

## 1. Prerequisites

1. Python 3.9+
2. 如果使用 `llm.provider=opencode_run`，本机需要可执行的 `opencode`
3. 能访问你的数据库和 LLM 服务

## 2. Install

```bash
git clone <repository-url>
cd sql-optimizer-skill
export PYTHONPATH=$(pwd)/python
pip install -r install/requirements.txt
```

## 3. Configuration

最小配置示例：

```yaml
config_version: v1

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

## 4. Java Scanner

默认场景优先走当前主链路，不要求手动配置 Java scanner JAR。

只有在 legacy Java scanner 路径下，才需要额外提供 `scan.java_scanner.jar_path`。

## 5. Verify

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py --help
PYTHONPATH=python python3 install/doctor.py --project /path/to/your/project
python3 -m pytest -q
```

## 6. Smoke Run

切到真实 DB / 外部 LLM 之前，建议先跑离线 smoke：

```yaml
llm:
  enabled: true
  provider: opencode_builtin
```

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage patch_generate
PYTHONPATH=python python3 scripts/sqlopt_cli.py status
PYTHONPATH=python python3 scripts/sqlopt_cli.py resume
```

如果 `status.next_action=report-rebuild`：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage report --run-id <run-id>
```

下一步看：
- [QUICKSTART.md](QUICKSTART.md)
- [CONFIG.md](CONFIG.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
