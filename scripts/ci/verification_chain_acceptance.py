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


def _config_text() -> str:
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

    with tempfile.TemporaryDirectory(prefix="sqlopt_verification_accept_") as td:
        temp_root = Path(td)
        project_dir = temp_root / "project"
        shutil.copytree(fixture, project_dir)
        user_config_path = project_dir / "sqlopt.local.yml"
        user_config_path.write_text(_config_text(), encoding="utf-8")
        config_path = _write_resolved_config(project_dir)

        proc = _run(
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
        payload = _require_ok(proc, step="sqlopt_cli run")
        if not bool(payload.get("complete", False)):
            raise SystemExit("verification chain acceptance failed: run did not complete")

        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise SystemExit("verification chain acceptance failed: missing run_id")

        run_dir = project_dir / "runs" / run_id
        report_path = run_dir / "report.json"
        acceptance_path = run_dir / "artifacts" / "acceptance.jsonl"
        patches_path = run_dir / "artifacts" / "patches.jsonl"
        scan_path = run_dir / "artifacts" / "scan.jsonl"
        proposals_path = run_dir / "artifacts" / "proposals.jsonl"
        if not report_path.exists():
            raise SystemExit("verification chain acceptance failed: report.json missing")

        verification_rows: list[dict[str, Any]] = []
        for path in (scan_path, proposals_path, acceptance_path, patches_path):
            for row in [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]:
                verification = row.get("verification")
                if isinstance(verification, dict):
                    verification_rows.append(dict(verification))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        acceptance_rows = [
            json.loads(line)
            for line in acceptance_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        patch_rows = [
            json.loads(line)
            for line in patches_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        phases = {str(row.get("phase")) for row in verification_rows}
        required_phases = {"scan", "optimize", "validate", "patch_generate"}
        if not required_phases.issubset(phases):
            raise SystemExit(f"verification chain acceptance failed: missing phases {sorted(required_phases - phases)}")

        validation_sql = {
            str(row.get("sql_key"))
            for row in verification_rows
            if str(row.get("phase")) == "validate" and str(row.get("sql_key") or "").strip()
        }
        patch_sql = {
            str(row.get("sql_key"))
            for row in verification_rows
            if str(row.get("phase")) == "patch_generate" and str(row.get("sql_key") or "").strip()
        }
        accepted_sql = {str(row.get("sqlKey")) for row in acceptance_rows if str(row.get("status")) == "PASS"}
        patch_result_sql = {str(row.get("sqlKey")) for row in patch_rows if str(row.get("sqlKey") or "").strip()}

        if not accepted_sql.issubset(validation_sql):
            raise SystemExit("verification chain acceptance failed: PASS acceptance rows missing validate verification records")
        if not patch_result_sql.issubset(patch_sql):
            raise SystemExit("verification chain acceptance failed: patch results missing patch_generate verification records")
        if report.get("phase_status", {}).get("report") != "DONE":
            raise SystemExit("verification chain acceptance failed: report phase is not DONE in report.json")

        print(
            json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "verification_rows": len(verification_rows),
                    "validate_verified_sql": len(validation_sql),
                    "patch_verified_sql": len(patch_sql),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
