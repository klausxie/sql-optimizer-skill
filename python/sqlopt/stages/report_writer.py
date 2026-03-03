from __future__ import annotations

from pathlib import Path

from ..contracts import ContractValidator
from ..io_utils import write_json, write_jsonl
from .report_builder import ReportArtifacts
from .report_render import render_report_md, render_summary_md


def write_report_artifacts(
    run_id: str,
    mode: str,
    run_dir: Path,
    validator: ContractValidator,
    artifacts: ReportArtifacts,
) -> dict:
    validator.validate("ops_topology", artifacts.topology)
    write_json(run_dir / "ops" / "topology.json", artifacts.topology)

    write_jsonl(run_dir / "ops" / "failures.jsonl", artifacts.failures)

    validator.validate("run_report", artifacts.report)
    write_json(run_dir / "report.json", artifacts.report)
    (run_dir / "report.summary.md").write_text(
        render_summary_md(
            run_id,
            artifacts.report["summary"]["verdict"],
            artifacts.report["summary"]["release_readiness"],
            artifacts.report["stats"],
            artifacts.phase_status,
        ),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text(
        render_report_md(
            run_id,
            artifacts.report["summary"]["verdict"],
            artifacts.report["summary"]["release_readiness"],
            artifacts.report["stats"],
            artifacts.phase_status,
            artifacts.attempts_by_phase,
            artifacts.next_actions,
            artifacts.top_blockers,
            artifacts.sql_rows,
            artifacts.proposal_rows,
        ),
        encoding="utf-8",
    )

    validator.validate("ops_health", artifacts.health)
    write_json(run_dir / "ops" / "health.json", artifacts.health)
    return artifacts.report
