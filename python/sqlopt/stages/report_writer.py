from __future__ import annotations

from pathlib import Path

from ..contracts import ContractValidator
from ..io_utils import write_json, write_jsonl
from ..run_paths import canonical_paths
from .report_models import ReportArtifacts


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
    report_payload = artifacts.report.to_contract()
    validator.validate("run_report", report_payload)
    write_json(paths.report_json_path, report_payload)
    for row in artifacts.diagnostics_sql_artifacts:
        validator.validate("sql_artifact_index_row", row)
    _write_sql_layout(run_dir, artifacts.diagnostics_sql_artifacts)
    return report_payload
