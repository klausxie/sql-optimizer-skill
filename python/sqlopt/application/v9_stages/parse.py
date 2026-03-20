from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...run_paths import canonical_paths
from .common import normalize_sqlunit


def run_parse(
    run_dir: Path,
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    from ...stages.branching.brancher import Brancher
    from ...stages.pruning import analyze_risks

    paths = canonical_paths(run_dir)
    init_path = paths.init_sql_units_path
    if not init_path.exists():
        return {"success": False, "error": "Init results not found"}

    with open(init_path) as f:
        sql_units = [normalize_sqlunit(unit) for unit in json.load(f)]

    branch_cfg = config.get("branching", {})
    brancher = Brancher(
        strategy=branch_cfg.get("strategy", "all_combinations"),
        max_branches=branch_cfg.get("max_branches", 100),
    )

    for unit in sql_units:
        validator.validate_stage_input("parse", unit)
        sql_text = unit.get("templateSql", unit.get("sql", ""))
        branches = brancher.generate(sql_text)
        unit["branches"] = [
            {
                "id": index,
                "conditions": b.active_conditions,
                "sql": b.sql,
                "type": "conditional" if b.condition_count else "static",
            }
            for index, b in enumerate(branches, start=1)
        ]
        unit["branchCount"] = len(branches)
        unit["problemBranchCount"] = sum(1 for b in branches if b.risk_flags)
        risk_flags = list(dict.fromkeys(str(x) for x in (unit.get("riskFlags") or [])))
        for branch in branches:
            for flag in branch.risk_flags:
                text = str(flag).strip()
                if text and text not in risk_flags:
                    risk_flags.append(text)
        unit["riskFlags"] = risk_flags
        validator.validate_stage_output("parse", unit)

    all_risks = analyze_risks(sql_units)
    for risk_report in all_risks:
        validator.validate_stage_output("parse", risk_report)

    units_output_path = paths.parse_sql_units_with_branches_path
    units_output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(units_output_path, "w") as f:
        json.dump(sql_units, f, indent=2, ensure_ascii=False)

    risks_output_path = paths.parse_risks_path
    with open(risks_output_path, "w") as f:
        json.dump(all_risks, f, indent=2, ensure_ascii=False)

    return {
        "success": True,
        "sql_units_file": str(units_output_path),
        "risks_file": str(risks_output_path),
        "sql_units_count": len(sql_units),
        "risks_count": len(all_risks),
    }
