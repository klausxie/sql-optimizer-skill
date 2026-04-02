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


sys.path.insert(0, str(_repo_root() / "python"))

from sqlopt.application.diagnostics_summary import build_verify_payload  # noqa: E402
from sqlopt.stages.report_builder import build_report_artifacts  # noqa: E402
from sqlopt.stages.report_loader import load_report_inputs  # noqa: E402


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


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _report_build_config() -> dict[str, Any]:
    return {
        "policy": {},
        "runtime": {
            "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
            "stage_retry_max": {"scan": 1, "report": 2},
            "stage_retry_backoff_ms": 50,
        },
        "llm": {"enabled": False},
    }


def _require_payload(proc: subprocess.CompletedProcess[str], *, step: str) -> dict[str, Any]:
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

    with tempfile.TemporaryDirectory(prefix="sqlopt_guidance_accept_") as td:
        temp_root = Path(td)
        project_dir = temp_root / "project"
        shutil.copytree(fixture, project_dir)
        config_path = project_dir / "sqlopt.local.yml"
        config_path.write_text(_config_text(), encoding="utf-8")

        run_proc = _run(
            [
                sys.executable,
                str(repo_root / "scripts" / "run_until_budget.py"),
                "--config",
                str(config_path),
                "--to-stage",
                "patch_generate",
                "--max-steps",
                "200",
                "--max-seconds",
                "45",
            ],
            cwd=repo_root,
        )
        run_payload = _require_payload(run_proc, step="run_until_budget")
        if not bool(run_payload.get("complete", False)):
            raise SystemExit("guidance consistency acceptance failed: run did not complete")

        run_id = str(run_payload.get("run_id") or "").strip()
        if not run_id:
            raise SystemExit("guidance consistency acceptance failed: missing run_id")

        run_dir = project_dir / "runs" / run_id
        report_path = run_dir / "report.json"
        catalog_path = run_dir / "sql" / "catalog.jsonl"
        if not report_path.exists():
            raise SystemExit("guidance consistency acceptance failed: report.json missing")
        if not catalog_path.exists():
            raise SystemExit("guidance consistency acceptance failed: sql/catalog.jsonl missing")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        inputs = load_report_inputs(run_dir)
        artifacts = build_report_artifacts(run_id, "analyze", _report_build_config(), run_dir, inputs)
        catalog_rows = _read_jsonl(catalog_path)
        if not catalog_rows:
            raise SystemExit("guidance consistency acceptance failed: sql/catalog.jsonl is empty")
        top_row = dict(catalog_rows[0])
        sql_key = str(top_row.get("sql_key") or "").strip()
        if not sql_key:
            raise SystemExit("guidance consistency acceptance failed: catalog row is missing sql_key")

        verification_rows = [row for row in inputs.verification_rows if str(row.get("sql_key") or "") == sql_key]
        acceptance_rows = [
            row
            for row in _read_jsonl(run_dir / "artifacts" / "acceptance.jsonl")
            if str(row.get("sqlKey") or "") == sql_key
        ]
        patch_rows = [
            row
            for row in _read_jsonl(run_dir / "artifacts" / "patches.jsonl")
            if str(row.get("sqlKey") or "") == sql_key
        ]
        verify_payload = build_verify_payload(
            run_id,
            run_dir,
            sql_key,
            None,
            bool(inputs.verification_rows),
            verification_rows,
            acceptance_rows,
            patch_rows,
        )
        if not verify_payload:
            raise SystemExit("guidance consistency acceptance failed: verify aggregation produced no structured payload")
        verify_why_now = str(verify_payload.get("why_now") or "").strip()
        if not verify_why_now:
            raise SystemExit("guidance consistency acceptance failed: diagnostic why_now is missing")
        if report.get("next_action") != artifacts.report.to_contract().get("next_action"):
            raise SystemExit("guidance consistency acceptance failed: persisted report next_action drifted from rebuilt report contract")
        if report.get("next_action") == "apply" and str((verify_payload.get("recommended_next_step") or {}).get("action") or "") != "apply":
            raise SystemExit("guidance consistency acceptance failed: apply-ready run drifted from diagnostic summary")

        print(
            json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "sql_key": sql_key,
                    "delivery_assessment": verify_payload.get("delivery_assessment"),
                    "evidence_state": verify_payload.get("evidence_state"),
                    "why_now_present": True,
                    "catalog_present": True,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
