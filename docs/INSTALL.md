# SQL Optimizer Skill Installation

## 1. Prerequisites

1. Python (>= 3.10)
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
python3 install/install_skill.py --project /path/to/your/project
```

Windows PowerShell:

```powershell
cd C:\path\to\sql-optimizer-skill-bundle-v<version>
python install/install_skill.py --project C:\path\to\your\project
```

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
$HOME/.opencode/skills/sql-optimizer/bin/sqlopt-cli --help
```

Windows PowerShell:

```powershell
$env:USERPROFILE\.opencode\skills\sql-optimizer\bin\sqlopt-cli.cmd --help
```

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

Before switching to real DB / external LLM, verify one offline-safe run first.

Recommended config overrides for the project under test:

```yaml
validate:
  db_reachable: false
  allow_db_unreachable_fallback: true
  plan_compare_enabled: false

llm:
  enabled: true
  provider: opencode_builtin

apply:
  mode: PATCH_ONLY
```

Then run from the project root:

```bash
$HOME/.opencode/skills/sql-optimizer/bin/sqlopt-cli --quiet run --config sqlopt.yml --to-stage patch_generate
$HOME/.opencode/skills/sql-optimizer/bin/sqlopt-cli status --run-id <run_id>
$HOME/.opencode/skills/sql-optimizer/bin/sqlopt-cli resume --run-id <run_id>
```

Repeat `resume` until `complete=true`, then verify:

1. `runs/<run_id>/supervisor/state.json`
2. `runs/<run_id>/report.json`
3. `runs/<run_id>/report.summary.md`

All three should agree that `report` is `DONE`.

Preferred release gate from this repository:

```bash
python3 scripts/ci/release_acceptance.py
```

This runs both:

1. install-to-opencode path (skill install, command docs, installed runtime)
2. repository-local degraded path (DB unreachable but fallback allowed)

You can still run them individually:

```bash
python3 scripts/ci/opencode_smoke_acceptance.py
python3 scripts/ci/degraded_runtime_acceptance.py
```
