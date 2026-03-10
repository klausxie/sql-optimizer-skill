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


def _delivery_matches(report_delivery: str, verify_delivery: str) -> bool:
    allowed = {
        "READY": {"NEEDS_REVIEW", "READY_TO_APPLY"},
        "READY_TO_APPLY": {"READY_TO_APPLY"},
        "NEEDS_TEMPLATE_REWRITE": {"PATCHABLE_WITH_REWRITE"},
        "PATCHABLE_WITH_REWRITE": {"PATCHABLE_WITH_REWRITE"},
        "MANUAL_REVIEW": {"MANUAL_REVIEW"},
        "BLOCKED": {"BLOCKED"},
    }
    return verify_delivery in allowed.get(report_delivery, {verify_delivery})


def _actions_align(report_action: str, verify_action: str) -> bool:
    if report_action == verify_action:
        return True
    return (report_action, verify_action) == ("check-db", "restore-db-validation")


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
        report_path = run_dir / "overview" / "report.json"
        summary_md_path = run_dir / "overview" / "report.summary.md"
        if not report_path.exists():
            raise SystemExit("guidance consistency acceptance failed: overview/report.json missing")
        if not summary_md_path.exists():
            raise SystemExit("guidance consistency acceptance failed: report.summary.md missing")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        report_summary_md = summary_md_path.read_text(encoding="utf-8")
        top_actionable = list(((report.get("stats") or {}).get("top_actionable_sql") or []))
        if not top_actionable:
            raise SystemExit("guidance consistency acceptance failed: top_actionable_sql is empty")
        top_row = dict(top_actionable[0])
        sql_key = str(top_row.get("sql_key") or "").strip()
        if not sql_key:
            raise SystemExit("guidance consistency acceptance failed: top actionable sql is missing sql_key")

        report_next_actions = list(((report.get("summary") or {}).get("next_actions") or []))
        if not report_next_actions:
            raise SystemExit("guidance consistency acceptance failed: report summary is missing next_actions")
        report_action = dict(report_next_actions[0])

        verification_rows = [
            row
            for row in _read_jsonl(run_dir / "pipeline" / "verification" / "ledger.jsonl")
            if str(row.get("sql_key") or "") == sql_key
        ]
        acceptance_rows = [
            row
            for row in _read_jsonl(run_dir / "pipeline" / "validate" / "acceptance.results.jsonl")
            if str(row.get("sqlKey") or "") == sql_key
        ]
        patch_rows = [
            row
            for row in _read_jsonl(run_dir / "pipeline" / "patch_generate" / "patch.results.jsonl")
            if str(row.get("sqlKey") or "") == sql_key
        ]
        verify_payload = build_verify_payload(
            run_id,
            run_dir,
            sql_key,
            None,
            (run_dir / "pipeline" / "verification" / "ledger.jsonl").exists(),
            verification_rows,
            acceptance_rows,
            patch_rows,
        )
        if not verify_payload:
            raise SystemExit("guidance consistency acceptance failed: verify aggregation produced no structured payload")

        report_delivery = str(top_row.get("delivery_tier") or "")
        verify_delivery = str(verify_payload.get("delivery_assessment") or "")
        if not _delivery_matches(report_delivery, verify_delivery):
            raise SystemExit("guidance consistency acceptance failed: delivery assessment drifted between report and diagnostic summary")

        report_evidence_state = str(top_row.get("evidence_state") or "")
        verify_evidence_state = str(verify_payload.get("evidence_state") or "")
        if report_evidence_state != verify_evidence_state:
            raise SystemExit("guidance consistency acceptance failed: evidence_state drifted between report and diagnostic summary")

        report_action_id = str(report_action.get("action_id") or "")
        verify_action = str((verify_payload.get("recommended_next_step") or {}).get("action") or "")
        if not _actions_align(report_action_id, verify_action):
            raise SystemExit("guidance consistency acceptance failed: action drifted between report and diagnostic summary")

        report_reason = str(report_action.get("reason") or "")
        verify_reason = str((verify_payload.get("recommended_next_step") or {}).get("reason") or "")
        if report_reason != verify_reason:
            raise SystemExit("guidance consistency acceptance failed: reason drifted between report and diagnostic summary")

        verify_why_now = str(verify_payload.get("why_now") or "").strip()
        if not verify_why_now:
            raise SystemExit("guidance consistency acceptance failed: diagnostic why_now is missing")
        report_why_now = str(top_row.get("why_now") or "").strip()
        if not report_why_now:
            raise SystemExit("guidance consistency acceptance failed: report why_now is missing")
        if report_why_now not in report_summary_md:
            raise SystemExit("guidance consistency acceptance failed: report.summary.md is missing the top why_now guidance")

        print(
            json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "sql_key": sql_key,
                    "delivery_assessment": verify_delivery,
                    "evidence_state": verify_evidence_state,
                    "action_alignment": True,
                    "reason_alignment": True,
                    "why_now_present": True,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
