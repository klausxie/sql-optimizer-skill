from __future__ import annotations

from pathlib import Path

from ..contracts import ContractValidator
from ..io_utils import write_json, write_jsonl
from .report_models import ReportArtifacts
from .report_render import render_report_md, render_summary_md


def write_report_artifacts(
    run_id: str,
    mode: str,
    run_dir: Path,
    validator: ContractValidator,
    artifacts: ReportArtifacts,
) -> dict:
    topology_payload = artifacts.topology.to_contract()
    validator.validate("ops_topology", topology_payload)
    write_json(run_dir / "ops" / "topology.json", topology_payload)

    write_jsonl(run_dir / "ops" / "failures.jsonl", artifacts.failures_to_contract())

    report_payload = artifacts.report.to_contract()
    validator.validate("run_report", report_payload)
    write_json(run_dir / "report.json", report_payload)
    (run_dir / "report.summary.md").write_text(
        render_summary_md(
            run_id,
            artifacts.report.summary.verdict,
            artifacts.report.summary.release_readiness,
            artifacts.report.stats,
            artifacts.state.phase_status,
        ),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text(
        render_report_md(
            run_id,
            artifacts.report.summary.verdict,
            artifacts.report.summary.release_readiness,
            artifacts.report.stats,
            artifacts.state.phase_status,
            artifacts.state.attempts_by_phase,
            artifacts.next_actions,
            artifacts.top_blockers,
            artifacts.sql_rows,
            artifacts.proposal_rows,
        ),
        encoding="utf-8",
    )

    health_payload = artifacts.health.to_contract()
    validator.validate("ops_health", health_payload)
    write_json(run_dir / "ops" / "health.json", health_payload)
    return report_payload
