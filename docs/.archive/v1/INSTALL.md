# SQL Optimizer Skill Installation

## 1. Prerequisites

1. Python (>= 3.9)
2. If using `llm.provider=opencode_run`, ensure `opencode` command is available
3. Network access to your configured LLM endpoint and DB

## 2. Build bundle (publisher machine)

Linux/macOS:

```bash
python3 install/build_bundle.py
```

Windows PowerShell:

```powershell
python install/build_bundle.py
```

Artifact:

```text
dist/sql-optimizer-skill-bundle-v<version>.tar.gz
```

## 3. Install on teammate machine

Linux/macOS:

```bash
cd /path/to/sql-optimizer-skill-bundle-v<version>
python3 install/install_skill.py
python3 install/install_skill.py --verify
```

Windows PowerShell:

```powershell
cd C:\path\to\sql-optimizer-skill-bundle-v<version>
python install/install_skill.py
python install/install_skill.py --verify
```

By default installer auto-updates PATH. Use `--no-auto-path` to disable it.

What this does:

1. Installs skill to `<home>/.opencode/skills/sql-optimizer`
2. Creates runtime `.venv` and installs dependencies
3. Installs opencode command docs under `<home>/.opencode/commands/`
4. Creates `<project>/sqlopt.yml` if missing

## 4. Run doctor

Linux/macOS:

```bash
python3 install/doctor.py --project /path/to/your/project
```

Windows PowerShell:

```powershell
python install/doctor.py --project C:\path\to\your\project
```

Note for Windows:

1. Runtime uses soft-timeout fallback (no `SIGALRM` dependency).
2. If a step appears slow, check `opencode`/DB connectivity first.

## 5. Verify command path

Linux/macOS:

```bash
sqlopt-cli --help
```

Windows PowerShell:

```powershell
sqlopt-cli --help
```

If PATH is still missing (auto-update failed or was disabled), installer prints exact PATH parameter and fix commands. Typical Windows fix:

```powershell
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
[Environment]::SetEnvironmentVariable('Path', "$env:USERPROFILE\.opencode\skills\sql-optimizer\bin;$userPath", 'User')
```

Then reopen PowerShell.

## 6. Optional: Direct LLM API mode

If you want to bypass `opencode run`, set in `sqlopt.yml`:

```yaml
llm:
  enabled: true
  provider: direct_openai_compatible
  timeout_ms: 15000
  api_base: https://api.openai.com/v1
  api_key: <your_api_key>
  api_model: gpt-4o-mini
  api_timeout_ms: 30000
  # optional:
  # api_headers:
  #   x-env: prod
```

## 7. Verify local tests

From the repository root, run:

```bash
python3 -m pytest -q
```

## 8. Recommended Post-Install Smoke Run

在切换到真实 DB / 外部 LLM 前，先跑一轮离线 smoke：

```yaml
llm:
  enabled: true
  provider: opencode_builtin
```

```bash
sqlopt-cli --quiet run --config sqlopt.yml --to-stage patch
sqlopt-cli status
sqlopt-cli resume
```

若 `status.next_action=report-rebuild`，说明报告阶段可独立重建，通常无需手动触发。

发布前推荐统一验收入口：

```bash
python3 scripts/ci/release_acceptance.py
```

更详细的运行流程与故障排查请看：
- `docs/QUICKSTART.md`
- `docs/TROUBLESHOOTING.md`
