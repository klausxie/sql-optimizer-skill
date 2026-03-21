from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...run_paths import canonical_paths


def run_recognition(
    run_dir: Path,
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    from ...stages.baseline import collect_baseline

    paths = canonical_paths(run_dir)
    parse_path = paths.parse_sql_units_with_branches_path
    if not parse_path.exists():
        return {"success": False, "error": "Parse results not found"}

    with open(parse_path) as f:
        sql_units = json.load(f)
    for unit in sql_units:
        validator.validate_stage_input("recognition", unit)

    raw_baselines = collect_baseline(config, sql_units)
    baselines = []
    for baseline in raw_baselines:
        explain_plan = dict(baseline.get("explainPlan") or {})
        normalized = {
            "sql_key": baseline.get("sqlKey", "unknown"),
            "execution_time_ms": baseline.get("executionTimeMs", 0.0),
            "rows_scanned": baseline.get("rowsExamined", 0),
            "execution_plan": {
                "node_type": explain_plan.get("scan_type", "UNKNOWN"),
                "index_used": baseline.get("indexUsed"),
                "cost": explain_plan.get("estimated_cost"),
            },
            "result_hash": hashlib.md5(
                json.dumps(baseline, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:12],
            "rows_returned": baseline.get("rowsReturned", 0),
            "database_platform": baseline.get("databasePlatform"),
            "sample_params": baseline.get("sampleParams"),
            "actual_execution_time_ms": baseline.get("actualExecutionTimeMs"),
            "buffer_hit_count": baseline.get("bufferHitCount"),
            "buffer_read_count": baseline.get("bufferReadCount"),
            "explain_plan": explain_plan,
        }
        validator.validate_stage_output("recognition", normalized)
        baselines.append(normalized)

    output_path = paths.recognition_results_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(baselines, f, indent=2, ensure_ascii=False)

    return {
        "success": True,
        "output_file": str(output_path),
        "baselines_count": len(baselines),
    }
