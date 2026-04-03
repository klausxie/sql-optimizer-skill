#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_project(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "projects" / "sample_project"


def _scanner_jar(repo_root: Path) -> Path:
    return repo_root / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar"


def _config_text(repo_root: Path) -> str:
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


def _parse_last_dict(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            value = ast.literal_eval(line)
        except Exception:
            try:
                value = json.loads(line)
            except Exception:
                continue
        if isinstance(value, dict):
            return value
    return {}


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def _require_ok(proc: subprocess.CompletedProcess[str], *, step: str) -> None:
    if proc.returncode == 0:
        return
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    raise SystemExit(f"{step} failed with exit code {proc.returncode}")


def _run_until_complete(repo_root: Path, config_path: Path) -> str:
    run_id = ""
    for _ in range(6):
        if run_id:
            cmd = [
                sys.executable,
                str(repo_root / "scripts" / "sqlopt_cli.py"),
                "resume",
                "--run-id",
                run_id,
                "--max-steps",
                "200",
                "--max-seconds",
                "95",
            ]
        else:
            cmd = [
                sys.executable,
                str(repo_root / "scripts" / "sqlopt_cli.py"),
                "run",
                "--config",
                str(config_path),
                "--to-stage",
                "patch_generate",
                "--max-steps",
                "200",
                "--max-seconds",
                "95",
            ]
        proc = _run(cmd, cwd=repo_root)
        _require_ok(proc, step="sqlopt_cli")
        payload = _parse_last_dict(proc.stdout)
        run_id = str(payload.get("run_id") or run_id).strip()
        if run_id and bool(payload.get("complete")):
            return run_id
    raise SystemExit("degraded acceptance failed: run did not complete within retry budget")


def main() -> None:
    repo_root = _repo_root()
    fixture = _fixture_project(repo_root)
    if not fixture.exists():
        raise SystemExit(f"missing fixture project: {fixture}")

    with tempfile.TemporaryDirectory(prefix="sqlopt_degraded_accept_") as td:
        temp_root = Path(td)
        project_dir = temp_root / "project"
        shutil.copytree(fixture, project_dir)
        config_path = project_dir / "sqlopt.local.yml"
        config_path.write_text(_config_text(repo_root), encoding="utf-8")

        run_id = _run_until_complete(repo_root, config_path)
        run_dir = project_dir / "runs" / run_id

        state = json.loads((run_dir / "control" / "state.json").read_text(encoding="utf-8"))
        report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
        preflight = json.loads((run_dir / "control" / "preflight.json").read_text(encoding="utf-8"))

        db_check = next((row for row in preflight.get("checks", []) if row.get("name") == "db"), {})
        if db_check.get("reason") != "validate.db_reachable=false":
            raise SystemExit("degraded acceptance failed: expected preflight DB check to be skipped")
        if state["phase_status"]["validate"] != "DONE":
            raise SystemExit("degraded acceptance failed: validate phase did not complete")
        if state["phase_status"]["report"] != "DONE":
            raise SystemExit("degraded acceptance failed: report phase not done in state")
        if report["phase_status"]["report"] != "DONE":
            raise SystemExit("degraded acceptance failed: report.json does not show report DONE")
        if str(state.get("status")) != "COMPLETED":
            raise SystemExit("degraded acceptance failed: state status not completed")

        print(
            json.dumps(
                {
                    "ok": True,
                    "project_dir": str(project_dir),
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "db_check": db_check,
                    "phase_status": state["phase_status"],
                    "run_status": state.get("status"),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
