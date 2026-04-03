#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _project_fixture(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "projects" / "sample_project"


def _scanner_jar(repo_root: Path) -> Path:
    return repo_root / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"


def _opencode_home() -> Path:
    return Path.home() / ".opencode"


def _installed_skill_dir() -> Path:
    return _opencode_home() / "skills" / "sql-optimizer"


def _installed_runtime_python() -> Path:
    if sys.platform.startswith("win"):
        return _installed_skill_dir() / "runtime" / ".venv" / "Scripts" / "python.exe"
    return _installed_skill_dir() / "runtime" / ".venv" / "bin" / "python"


def _installed_runtime_script(name: str) -> Path:
    return _installed_skill_dir() / "runtime" / "scripts" / name


def _local_config_text(repo_root: Path) -> str:
    return "\n".join(
        [
            "project:",
            "  root_path: .",
            "",
            "scan:",
            "  mapper_globs:",
            "    - src/main/resources/**/*.xml",
            "",
            "db:",
            "  platform: postgresql",
            "  dsn: postgresql://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable",
            "",
            "llm:",
            "  enabled: true",
            "  provider: opencode_builtin",
            "  timeout_ms: 80000",
            "",
        ]
    )


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def _parse_last_dict(text: str) -> dict[str, Any]:
    lines = [_strip_ansi(line).strip() for line in text.splitlines() if _strip_ansi(line).strip()]
    for line in reversed(lines):
        candidates = [line]
        start = line.find("{")
        end = line.rfind("}")
        if start != -1 and end != -1 and start < end:
            fragment = line[start : end + 1]
            if fragment != line:
                candidates.append(fragment)
        for candidate in candidates:
            try:
                value = ast.literal_eval(candidate)
            except Exception:
                try:
                    value = json.loads(candidate)
                except Exception:
                    continue
            if isinstance(value, dict):
                return value
    return {}


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)


def _require_ok(proc: subprocess.CompletedProcess[str], *, step: str) -> None:
    if proc.returncode == 0:
        return
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    raise SystemExit(f"{step} failed with exit code {proc.returncode}")


def _verify_outputs(run_dir: Path) -> dict[str, Any]:
    state = json.loads((run_dir / "control" / "state.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    catalog_path = run_dir / "sql" / "catalog.jsonl"

    state_report = state["phase_status"]["report"]
    report_status = report["phase_status"]["report"]
    catalog_exists = catalog_path.exists()
    if state_report != "DONE" or report_status != "DONE" or not catalog_exists:
        raise SystemExit(
            "smoke verification failed: expected report DONE in control/state.json and report.json, with sql/catalog.jsonl present"
        )

    return {
        "state_report": state_report,
        "report_phase_status": report_status,
        "sql_catalog_present": catalog_exists,
    }


def _latest_run_id(project_dir: Path) -> str:
    runs_dir = project_dir / "runs"
    if not runs_dir.exists():
        return ""
    candidates = [path for path in runs_dir.iterdir() if path.is_dir()]
    if not candidates:
        return ""
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    return latest.name


def main() -> None:
    repo_root = _repo_root()
    fixture = _project_fixture(repo_root)
    if not fixture.exists():
        raise SystemExit(f"missing fixture project: {fixture}")
    with tempfile.TemporaryDirectory(prefix="sqlopt_opencode_accept_") as td:
        temp_root = Path(td)
        project_dir = temp_root / "project"
        shutil.copytree(fixture, project_dir)
        (project_dir / "sqlopt.local.yml").write_text(_local_config_text(repo_root), encoding="utf-8")

        install_proc = _run([sys.executable, str(repo_root / "install" / "install_skill.py"), "--project", str(project_dir), "--force"])
        _require_ok(install_proc, step="install_skill")
        opencode_proc = _run(["opencode", "--version"])
        _require_ok(opencode_proc, step="opencode --version")

        commands_dir = _opencode_home() / "commands"
        command_docs = [
            commands_dir / "sql-optimizer-run.md",
            commands_dir / "sql-optimizer-status.md",
            commands_dir / "sql-optimizer-resume.md",
            commands_dir / "sql-optimizer-apply.md",
        ]
        if not all(path.exists() for path in command_docs):
            raise SystemExit("smoke verification failed: opencode command docs missing after install")

        runtime_python = _installed_runtime_python()
        cli_script = _installed_runtime_script("sqlopt_cli.py")
        if not runtime_python.exists() or not cli_script.exists():
            raise SystemExit("smoke verification failed: installed runtime cli missing")

        run_proc = _run(
            [
                str(runtime_python),
                str(cli_script),
                "run",
                "--config",
                "./sqlopt.local.yml",
                "--to-stage",
                "patch_generate",
                "--max-steps",
                "200",
                "--max-seconds",
                "95",
            ],
            cwd=project_dir,
        )
        _require_ok(run_proc, step="installed sqlopt_cli run")
        run_payload = _parse_last_dict(run_proc.stdout)
        run_id = str(run_payload.get("run_id") or "").strip() or _latest_run_id(project_dir)
        if not run_id:
            raise SystemExit("smoke verification failed: missing run_id from installed runtime output")

        status_proc = _run(
            [
                str(runtime_python),
                str(cli_script),
                "status",
                "--run-id",
                run_id,
                "--project",
                ".",
            ],
            cwd=project_dir,
        )
        _require_ok(status_proc, step="installed status")
        status_payload = _parse_last_dict(status_proc.stdout)
        if str(status_payload.get("run_status")) != "COMPLETED":
            raise SystemExit(f"smoke verification failed: status not completed (run_id={run_id})")

        run_dir = project_dir / "runs" / run_id
        verification = _verify_outputs(run_dir)
        print(
            json.dumps(
                {
                    "ok": True,
                    "project_dir": str(project_dir),
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "opencode_version": opencode_proc.stdout.strip(),
                    "status": status_payload,
                    "verification": verification,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
