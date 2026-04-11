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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.config import load_config


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _project_fixture(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "projects" / "sample_project"


def _scanner_jar(repo_root: Path) -> Path:
    return repo_root / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"


def _opencode_home() -> Path:
    return Path.home() / ".opencode"


def _repo_cli_script(repo_root: Path) -> Path:
    return repo_root / "scripts" / "sqlopt_cli.py"


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
            "  dsn: postgresql://postgres:postgres@127.0.0.1:9/postgres?sslmode=disable",
            "",
            "llm:",
            "  enabled: true",
            "  provider: opencode_builtin",
            "  timeout_ms: 80000",
            "",
        ]
    )


def _write_resolved_config(repo_root: Path, project_dir: Path) -> Path:
    user_config_path = project_dir / "sqlopt.local.yml"
    resolved = load_config(user_config_path)
    validate_cfg = dict(resolved.get("validate") or {})
    validate_cfg["db_reachable"] = False
    resolved["validate"] = validate_cfg
    resolved_path = project_dir / "config.resolved.json"
    resolved_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


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
    proposals_path = run_dir / "artifacts" / "proposals.jsonl"
    report_path = run_dir / "report.json"

    state_optimize = state["phase_status"]["optimize"]
    report_optimize = None
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_optimize = report["phase_status"]["optimize"]
    proposals_present = proposals_path.exists()
    if state_optimize != "DONE" or (report_optimize is not None and report_optimize != "DONE") or not proposals_present:
        raise SystemExit(
            "smoke verification failed: expected optimize DONE in control/state.json, with artifacts/proposals.jsonl present"
        )

    return {
        "state_optimize": state_optimize,
        "report_phase_status": report_optimize,
        "proposals_present": proposals_present,
        "report_present": report_path.exists(),
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
        resolved_config_path = _write_resolved_config(repo_root, project_dir)

        cli_script = _repo_cli_script(repo_root)
        if not cli_script.exists():
            raise SystemExit(f"smoke verification failed: missing repo cli at {cli_script}")
        run_proc = _run(
            [
                sys.executable,
                str(cli_script),
                "run",
                "--config",
                str(resolved_config_path),
                "--to-stage",
                "optimize",
                "--max-steps",
                "400",
                "--max-seconds",
                "95",
            ],
            cwd=project_dir,
        )
        _require_ok(run_proc, step="repo sqlopt_cli run")
        run_payload = _parse_last_dict(run_proc.stdout)
        run_id = str(run_payload.get("run_id") or "").strip() or _latest_run_id(project_dir)
        if not run_id:
            raise SystemExit("smoke verification failed: missing run_id from repo runtime output")

        status_proc = _run(
            [
                sys.executable,
                str(cli_script),
                "status",
                "--run-id",
                run_id,
                "--project",
                ".",
            ],
            cwd=project_dir,
        )
        _require_ok(status_proc, step="repo status")
        status_payload = _parse_last_dict(status_proc.stdout)
        if str(status_payload.get("run_id") or "").strip() != run_id:
            raise SystemExit(f"smoke verification failed: status returned mismatched run_id (run_id={run_id})")

        run_dir = project_dir / "runs" / run_id
        verification = _verify_outputs(run_dir)
        print(
            json.dumps(
                {
                    "ok": True,
                    "project_dir": str(project_dir),
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "cli_script": str(cli_script),
                    "status": status_payload,
                    "verification": verification,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
