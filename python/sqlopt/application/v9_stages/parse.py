from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...progress import get_progress_reporter
from ...run_paths import canonical_paths
from ...stages.branching import FragmentRegistry, build_fragment_registry
from ...adapters.branch_generator import BranchGenerator
from .common import analyze_risks, normalize_sqlunit
from .overview import ParseOverviewGenerator


def _build_fragment_registry(
    config: dict[str, Any], sql_units: list[dict[str, Any]]
) -> FragmentRegistry:
    """Build FragmentRegistry from all XML files referenced by SQL units."""
    xml_paths = set()
    for unit in sql_units:
        xml_path = unit.get("xmlPath")
        if xml_path:
            xml_paths.add(Path(xml_path))

    if not xml_paths:
        return FragmentRegistry()

    return build_fragment_registry(sorted(xml_paths))


def _create_branches_v9(
    brancher: BranchGenerator, sql_unit: dict[str, Any]
) -> list[dict[str, Any]]:
    """Adapter: V9 BranchGenerator already returns the expected format."""
    return brancher.generate(sql_unit)


def run_parse(
    run_dir: Path,
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    paths = canonical_paths(run_dir)
    init_path = paths.init_sql_units_path
    if not init_path.exists():
        return {"success": False, "error": "Init results not found"}

    with open(init_path) as f:
        sql_units = [normalize_sqlunit(unit) for unit in json.load(f)]

    fragment_registry = _build_fragment_registry(config, sql_units)

    branch_cfg = config.get("branching", {})
    brancher = BranchGenerator(
        config={
            "branch": {
                "strategy": branch_cfg.get("strategy", "all_combinations"),
                "max_branches": branch_cfg.get("max_branches", 100),
            }
        },
        fragment_registry=fragment_registry,
    )

    for unit in sql_units:
        validator.validate_stage_input("parse", unit)
        branches = _create_branches_v9(brancher, unit)
        unit["branches"] = branches
        unit["branchCount"] = len(branches)
        unit["problemBranchCount"] = 0
        risk_flags = list(dict.fromkeys(str(x) for x in (unit.get("riskFlags") or [])))
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

    reporter = get_progress_reporter()
    overview_gen = ParseOverviewGenerator("parse", run_dir / "parse")
    overview_path = overview_gen.write(
        {"sql_units_with_branches": sql_units, "risks": all_risks}, "parse.overview.md"
    )
    reporter.report_info(f"parse output: overview -> {overview_path}")

    return {
        "success": True,
        "sql_units_file": str(units_output_path),
        "risks_file": str(risks_output_path),
        "sql_units_count": len(sql_units),
        "risks_count": len(all_risks),
    }
