from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...platforms.sql.optimizer_sql import generate_proposal
from ...platforms.sql.validator_sql import validate_proposal
from ...run_paths import canonical_paths
from .common import merge_validation_into_proposal


def run_optimize(
    run_dir: Path,
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    paths = canonical_paths(run_dir)
    baselines_path = paths.recognition_results_path
    if not baselines_path.exists():
        return {"success": False, "error": "Recognition results not found"}

    with open(baselines_path) as f:
        baselines = json.load(f)
    for baseline in baselines:
        validator.validate_stage_input("optimize", baseline)

    sql_units_path = paths.parse_sql_units_with_branches_path
    if not sql_units_path.exists():
        return {"success": False, "error": "Parse results not found"}

    with open(sql_units_path) as f:
        sql_units_data = json.load(f)

    sql_units_map = {unit.get("sqlKey", ""): unit for unit in sql_units_data}
    db_reachable = bool(((config.get("db", {}) or {}).get("dsn")))

    # Load cached schema_metadata from init stage (reuse to avoid redundant DB queries)
    schema_metadata = None
    schema_meta_path = paths.init_schema_metadata_path
    if schema_meta_path.exists():
        try:
            with open(schema_meta_path) as f:
                schema_metadata = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    proposals = []
    for baseline in baselines:
        sql_key = baseline.get("sql_key") or baseline.get("sqlKey", "")
        sql_unit = sql_units_map.get(sql_key)

        if not sql_unit:
            continue

        try:
            proposal = generate_proposal(sql_unit, config, schema_metadata)
            acceptance_result = validate_proposal(
                sql_unit,
                proposal,
                db_reachable,
                config=config,
                evidence_dir=canonical_paths(run_dir).sql_evidence_dir(sql_key),
                fragment_catalog={},
            )
            validation_result = (
                acceptance_result.to_contract()
                if hasattr(acceptance_result, "to_contract")
                else dict(acceptance_result)
            )
            enriched_proposal = merge_validation_into_proposal(
                sql_unit,
                proposal,
                validation_result,
            )
            validator.validate_stage_output("optimize", enriched_proposal)
            proposals.append(enriched_proposal)
        except Exception as exc:
            fallback = {
                "sqlKey": sql_key,
                "issues": [{"code": "OPTIMIZE_GENERATION_FAILED", "detail": str(exc)}],
                "dbEvidenceSummary": {},
                "planSummary": {},
                "suggestions": [],
                "verdict": "NO_ACTION",
                "confidence": "low",
                "estimatedBenefit": "unknown",
                "validated": False,
                "validationStatus": "ERROR",
                "originalSql": str(sql_unit.get("sql") or ""),
                "optimizedSql": str(sql_unit.get("sql") or ""),
                "rewrittenSql": str(sql_unit.get("sql") or ""),
                "validationResult": {
                    "status": "ERROR",
                    "warnings": [],
                    "riskFlags": [],
                    "securityChecks": {},
                    "equivalence": {},
                    "perfComparison": {"error": str(exc)},
                },
            }
            validator.validate_stage_output("optimize", fallback)
            proposals.append(fallback)

    output_path = paths.v9_proposals_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(proposals, f, indent=2, ensure_ascii=False)

    actionable_count = sum(
        1 for p in proposals if str(p.get("verdict") or "").upper() == "ACTIONABLE"
    )

    return {
        "success": True,
        "output_file": str(output_path),
        "proposals_count": len(proposals),
        "actionable_count": actionable_count,
    }
