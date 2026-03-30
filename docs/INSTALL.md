# SQL Optimizer Installation

## 1. Prerequisites

1. Python (>= 3.9)
2. If using `llm.provider=opencode_run`, ensure `opencode` command is available
3. Network access to your configured LLM endpoint and DB

## 2. Clone and Setup

```bash
git clone <repository-url>
cd sql-optimizer-skill

# Set PYTHONPATH
export PYTHONPATH=$(pwd)/python

# Or add to your shell profile for persistence
echo 'export PYTHONPATH="<absolute-path>/python"' >> ~/.bashrc
```

## 3. Install Dependencies

```bash
pip install -r install/requirements.txt
```

## 4. Verify Installation

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py --help
```

## 5. Run Doctor

```bash
PYTHONPATH=python python3 install/doctor.py --project /path/to/your/project
```

## 6. Verify Local Tests

From the repository root, run:

```bash
python3 -m pytest -q
```

## 7. Recommended Post-Install Smoke Run

在切换到真实 DB / 外部 LLM 前，先跑一轮离线 smoke：

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

若 `status.next_action=report-rebuild`，执行：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config sqlopt.yml --to-stage report --run-id <run-id>
```

发布前推荐统一验收入口：

```bash
python3 scripts/ci/release_acceptance.py
```

更详细的运行流程与故障排查请看：
- `docs/QUICKSTART.md`
- `docs/TROUBLESHOOTING.md`