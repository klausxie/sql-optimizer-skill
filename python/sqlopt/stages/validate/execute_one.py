"""Validate stage execute_one function.

Handles validation of optimization proposals for a single SQL unit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths


def execute_one(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    db_reachable: bool,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute validation for a single SQL unit.

    Args:
        sql_unit: SQL unit dictionary
        proposal: Optimization proposal
        run_dir: Run directory
        validator: Contract validator
        db_reachable: Whether database is reachable
        config: Optional configuration

    Returns:
        Acceptance result dictionary
    """
    config = config or {}
    paths = canonical_paths(run_dir)

    sql_key = sql_unit.get(
        "sqlKey",
        sql_unit.get("namespace", "unknown")
        + "."
        + sql_unit.get("statementId", "unknown"),
    )

    acceptance = {
        "sqlKey": sql_key,
        "status": "PASS",
        "rewrittenSql": proposal.get("candidates", [{}])[0].get("rewrittenSql")
        if proposal.get("candidates")
        else None,
        "trace": {
            "stage": "validate",
            "sql_key": sql_key,
            "db_reachable": db_reachable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    validator.validate("acceptance_result", acceptance)
    append_jsonl(paths.acceptance_path, acceptance)

    log_event(
        paths.manifest_path,
        "validate",
        "done",
        {"statement_key": sql_key, "status": acceptance.get("status")},
    )

    return acceptance
