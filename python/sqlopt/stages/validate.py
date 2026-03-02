from __future__ import annotations

from pathlib import Path

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, read_jsonl
from ..manifest import log_event
from ..platforms.sql.validator_sql import validate_proposal


def execute_one(sql_unit: dict, proposal: dict, run_dir: Path, validator: ContractValidator, db_reachable: bool, config: dict) -> dict:
    evidence_dir = run_dir / "evidence" / sql_unit["sqlKey"].replace("/", "_")
    fragments_path = run_dir / "scan.fragments.jsonl"
    fragment_rows = read_jsonl(fragments_path) if fragments_path.exists() else []
    fragment_catalog = {str(row.get("fragmentKey") or ""): row for row in fragment_rows if str(row.get("fragmentKey") or "").strip()}
    result = validate_proposal(
        sql_unit,
        proposal,
        db_reachable=db_reachable,
        config=config,
        evidence_dir=evidence_dir,
        fragment_catalog=fragment_catalog,
    )
    validator.validate("acceptance_result", result)
    append_jsonl(run_dir / "acceptance" / "acceptance.results.jsonl", result)
    log_event(run_dir / "manifest.jsonl", "validate", "done", {"statement_key": sql_unit["sqlKey"], "status": result["status"]})
    return result
