# SQL Optimizer Skill Upgrade

## 1. Upgrade in place

```bash
cd /path/to/new/sql-optimizer-skill-bundle-v<new_version>
python3 install/install_skill.py --project /path/to/your/project
```

Windows PowerShell:

```powershell
cd C:\path\to\new\sql-optimizer-skill-bundle-v<new_version>
python install/install_skill.py --project C:\path\to\your\project
```

Installer behavior:

1. Existing skill is backed up to:
   - `<home>/.opencode/skills/sql-optimizer.bak.<timestamp>`
2. New version is installed to:
   - `<home>/.opencode/skills/sql-optimizer`

## 2. Rollback

```bash
rm -rf $HOME/.opencode/skills/sql-optimizer
mv $HOME/.opencode/skills/sql-optimizer.bak.<timestamp> $HOME/.opencode/skills/sql-optimizer
```

Windows PowerShell:

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.opencode\skills\sql-optimizer"
Move-Item "$env:USERPROFILE\.opencode\skills\sql-optimizer.bak.<timestamp>" "$env:USERPROFILE\.opencode\skills\sql-optimizer"
```

Then re-run:

```bash
python3 install/doctor.py --project /path/to/your/project
```

## 3. Notes

1. `sqlopt.yml` and `runs/` data are not removed during upgrade.
2. Old run data compatibility is not guaranteed across major behavior changes.
3. If you use `llm.provider=direct_openai_compatible`, re-check `api_base/api_key/api_model` after upgrade.
