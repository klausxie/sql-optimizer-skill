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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.config import load_config


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_project(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "projects" / "sample_project"


def _config_text(repo_root: Path) -> str:
    return "\n".join(
        [
            "project:",
            "  root_path: .",
            "",
            "scan:",
            "  mapper_globs:",
            "    - src/main/resources/com/example/mapper/user/user_mapper.xml",
            "",
            "db:",
            "  platform: postgresql",
            "  dsn: postgresql://postgres:postgres@127.0.0.1:9/postgres?sslmode=disable",
            "",
            "llm:",
            "  enabled: false",
            "  provider: heuristic",
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


def _write_resolved_config(project_dir: Path) -> Path:
    user_config_path = project_dir / "sqlopt.local.yml"
    resolved = load_config(user_config_path)
    validate_cfg = dict(resolved.get("validate") or {})
    validate_cfg["db_reachable"] = False
    resolved["validate"] = validate_cfg
    resolved_path = project_dir / "config.resolved.json"
    resolved_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def _require_ok(proc: subprocess.CompletedProcess[str], *, step: str) -> dict[str, Any]:
    if proc.returncode != 0:
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"{step} failed with exit code {proc.returncode}")
    payload = _parse_last_dict(proc.stdout)
    if not payload:
        raise SystemExit(f"{step} produced no structured payload")
    return payload


def main() -> None:
    repo_root = _repo_root()
    fixture = _fixture_project(repo_root)
    if not fixture.exists():
        raise SystemExit(f"missing fixture project: {fixture}")

    with tempfile.TemporaryDirectory(prefix="sqlopt_report_rebuild_accept_") as td:
        temp_root = Path(td)
        project_dir = temp_root / "project"
        shutil.copytree(fixture, project_dir)
        user_config_path = project_dir / "sqlopt.local.yml"
        user_config_path.write_text(_config_text(repo_root), encoding="utf-8")
        config_path = _write_resolved_config(project_dir)

        run_proc = _run(
            [
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
                "45",
            ],
            cwd=project_dir,
        )
        run_payload = _require_ok(run_proc, step="sqlopt_cli run")
        if not bool(run_payload.get("complete", False)):
            raise SystemExit("report rebuild acceptance failed: run did not complete")

        run_id = str(run_payload.get("run_id") or "").strip()
        if not run_id:
            raise SystemExit("report rebuild acceptance failed: missing run_id")

        run_dir = project_dir / "runs" / run_id
        report_before = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
        manifest_path = run_dir / "control" / "manifest.jsonl"
        report_result_count_before = len(
            [
                line
                for line in manifest_path.read_text(encoding="utf-8").splitlines()
                if '"stage": "report"' in line and '"event": "done"' in line
            ]
        )

        rebuild_proc = _run(
            [
                sys.executable,
                str(repo_root / "scripts" / "sqlopt_cli.py"),
                "run",
                "--config",
                str(config_path),
                "--to-stage",
                "report",
                "--run-id",
                run_id,
            ],
            cwd=project_dir,
        )
        rebuild_payload = _require_ok(rebuild_proc, step="report_rebuild")
        if rebuild_payload.get("result", {}).get("phase") != "report":
            raise SystemExit("report rebuild acceptance failed: explicit report rebuild did not finalize report")

        report_after = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
        report_result_count_after = len(
            [
                line
                for line in manifest_path.read_text(encoding="utf-8").splitlines()
                if '"stage": "report"' in line and '"event": "done"' in line
            ]
        )
        state = json.loads((run_dir / "control" / "state.json").read_text(encoding="utf-8"))

        if report_result_count_before != report_result_count_after:
            raise SystemExit("report rebuild acceptance failed: duplicate report DONE result was appended")
        if state["phase_status"].get("report") != "DONE":
            raise SystemExit("report rebuild acceptance failed: report phase not DONE after rebuild")
        if bool(state.get("report_rebuild_required", False)):
            raise SystemExit("report rebuild acceptance failed: rebuild_required flag was not cleared")
        if str(state.get("status")) != "COMPLETED":
            raise SystemExit("report rebuild acceptance failed: run status not completed after rebuild")

        print(
            json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "report_result_count": report_result_count_after,
                    "run_status": state.get("status"),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
