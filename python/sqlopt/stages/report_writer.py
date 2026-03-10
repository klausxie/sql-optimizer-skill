from __future__ import annotations

from pathlib import Path

from ..contracts import ContractValidator
from ..io_utils import write_json, write_jsonl
from ..run_paths import canonical_paths
from ..verification.writer import write_verification_summary
from .report_models import ReportArtifacts
from .report_render import render_report_md, render_summary_md


def _write_sql_layout(run_dir: Path, rows: list[dict]) -> None:
    write_jsonl(run_dir / "sql" / "catalog.jsonl", rows)
    for row in rows:
        index_rel = str(row.get("sql_index") or "").strip()
        if not index_rel:
            continue
        write_json(run_dir / index_rel, row)


def write_report_artifacts(
    run_id: str,
    mode: str,
    run_dir: Path,
    validator: ContractValidator,
    artifacts: ReportArtifacts,
) -> dict:
    paths = canonical_paths(run_dir)
    topology_payload = artifacts.topology.to_contract()
    validator.validate("ops_topology", topology_payload)
    write_json(paths.topology_path, topology_payload)

    write_jsonl(paths.failures_path, artifacts.failures_to_contract())

    report_payload = artifacts.report.to_contract()
    validator.validate("run_report", report_payload)
    summary_md = render_summary_md(
        run_id,
        artifacts.report.summary.verdict,
        artifacts.report.summary.release_readiness,
        artifacts.report.stats,
        artifacts.state.phase_status,
    )
    report_md = render_report_md(
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
    )
    write_json(paths.report_json_path, report_payload)
    paths.report_md_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_md_path.write_text(report_md, encoding="utf-8")
    paths.report_summary_md_path.write_text(summary_md, encoding="utf-8")

    health_payload = artifacts.health.to_contract()
    validator.validate("ops_health", health_payload)
    write_json(paths.health_path, health_payload)
    validator.validate("run_index", artifacts.run_index)
    write_json(run_dir / "run.index.json", artifacts.run_index)
    for row in artifacts.diagnostics_sql_artifacts:
        validator.validate("sql_artifact_index_row", row)
    write_jsonl(run_dir / "diagnostics" / "sql_outcomes.jsonl", artifacts.diagnostics_sql_outcomes)
    write_jsonl(run_dir / "diagnostics" / "sql_artifacts.jsonl", artifacts.diagnostics_sql_artifacts)
    write_json(run_dir / "diagnostics" / "blockers.summary.json", artifacts.diagnostics_blockers_summary)
    _write_sql_layout(run_dir, artifacts.diagnostics_sql_artifacts)
    if artifacts.verification_summary:
        write_verification_summary(run_dir, validator, artifacts.verification_summary)
    return report_payload
