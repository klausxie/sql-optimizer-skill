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
    return repo_root / "tests" / "fixtures" / "project"


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


def _legacy_patch_rows(run_dir: Path) -> list[dict[str, Any]]:
    candidates = [
        run_dir / "patch" / "legacy.patch.results.jsonl",
        run_dir / "pipeline" / "apply" / "patch.results.jsonl",
        run_dir / "pipeline" / "patch_generate" / "patch.results.jsonl",
    ]
    for path in candidates:
        if path.exists():
            return [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
    return []


def main() -> None:
    repo_root = _repo_root()
    fixture = _fixture_project(repo_root)
    if not fixture.exists():
        raise SystemExit(f"missing fixture project: {fixture}")

    with tempfile.TemporaryDirectory(prefix="sqlopt_verification_accept_") as td:
        temp_root = Path(td)
        project_dir = temp_root / "project"
        shutil.copytree(fixture, project_dir)
        config_path = project_dir / "sqlopt.local.yml"
        config_path.write_text(_config_text(), encoding="utf-8")

        proc = _run(
            [
                sys.executable,
                str(repo_root / "scripts" / "run_until_budget.py"),
                "--config",
                str(config_path),
                "--to-stage",
                "patch",
                "--max-steps",
                "200",
                "--max-seconds",
                "45",
            ],
            cwd=repo_root,
        )
        payload = _require_ok(proc, step="run_until_budget")
        if not bool(payload.get("complete", False)):
            raise SystemExit("verification chain acceptance failed: run did not complete")

        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise SystemExit("verification chain acceptance failed: missing run_id")

        run_dir = project_dir / "runs" / run_id
        ledger_path = run_dir / "supervisor" / "verification" / "ledger.jsonl"
        summary_path = run_dir / "supervisor" / "verification" / "summary.json"
        report_path = run_dir / "overview" / "report.json"
        if not ledger_path.exists():
            raise SystemExit("verification chain acceptance failed: verification ledger missing")
        if not summary_path.exists():
            raise SystemExit("verification chain acceptance failed: verification summary missing")
        if not report_path.exists():
            raise SystemExit("verification chain acceptance failed: overview/report.json missing")

        ledger_rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        acceptance_path = (
            run_dir / "optimize" / "validation" / "acceptance.results.jsonl"
        )
        if not acceptance_path.exists():
            acceptance_path = (
                run_dir / "pipeline" / "validate" / "acceptance.results.jsonl"
            )
        acceptance_rows = (
            [
                json.loads(line)
                for line in acceptance_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if acceptance_path.exists()
            else []
        )
        patch_rows = _legacy_patch_rows(run_dir)

        phases = {str(row.get("phase")) for row in ledger_rows}
        required_phases = {"optimize", "patch"}
        legacy_required = {"scan", "optimize", "validate"}
        patch_phase_candidates = {"apply", "patch_generate", "patch"}
        if not required_phases.issubset(phases) and not legacy_required.issubset(
            phases
        ):
            raise SystemExit(
                f"verification chain acceptance failed: missing phases {sorted(required_phases - phases)}"
            )
        if not (phases & patch_phase_candidates):
            raise SystemExit(
                "verification chain acceptance failed: missing patch/apply verification records"
            )

        validation_sql = {
            str(row.get("sql_key"))
            for row in ledger_rows
            if str(row.get("phase")) in {"validate", "optimize"}
            and str(row.get("sql_key") or "").strip()
        }
        patch_sql = {
            str(row.get("sql_key"))
            for row in ledger_rows
            if str(row.get("phase")) in patch_phase_candidates
            and str(row.get("sql_key") or "").strip()
        }
        accepted_sql = {str(row.get("sqlKey")) for row in acceptance_rows if str(row.get("status")) == "PASS"}
        patch_result_sql = {str(row.get("sqlKey")) for row in patch_rows if str(row.get("sqlKey") or "").strip()}

        if acceptance_rows and not accepted_sql.issubset(validation_sql):
            raise SystemExit(
                "verification chain acceptance failed: PASS acceptance rows missing validate/optimize verification records"
            )
        if not patch_result_sql.issubset(patch_sql):
            raise SystemExit("verification chain acceptance failed: patch results missing patch/apply verification records")

        report_verification = ((report.get("stats") or {}).get("verification") or {})
        stable_summary = {key: value for key, value in summary.items() if key != "generated_at"}
        projected_report_verification = {key: report_verification.get(key) for key in stable_summary}
        if projected_report_verification != stable_summary:
            raise SystemExit("verification chain acceptance failed: overview/report.json verification summary mismatch")

        print(
            json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "verification_rows": len(ledger_rows),
                    "verified_count": summary.get("verified_count"),
                    "partial_count": summary.get("partial_count"),
                    "unverified_count": summary.get("unverified_count"),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
