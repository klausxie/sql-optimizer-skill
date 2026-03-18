"""
V8 Workflow Engine - 7 Stage Pipeline

Independent implementation with zero coupling to legacy workflow.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import json


@dataclass
class StageContext:
    run_id: str
    config: dict
    run_dir: Path
    cache_dir: Path
    metadata: dict


@dataclass
class StageResult:
    success: bool
    output_files: list[Path]
    artifacts: dict
    errors: list[str]
    warnings: list[str]


STAGE_ORDER = [
    "discovery",
    "branching",
    "pruning",
    "baseline",
    "optimize",
    "validate",
    "patch",
]


class V8WorkflowEngine:
    def __init__(self, config: dict):
        self.config = config
        self.stages = {}
        self._register_stages()

    def _register_stages(self):
        from ..stages.discovery import Scanner
        from ..stages.branching import BranchGenerator
        from ..stages.pruning import RiskDetector

        self.stages["discovery"] = self._run_discovery
        self.stages["branching"] = self._run_branching
        self.stages["pruning"] = self._run_pruning
        self.stages["baseline"] = self._run_baseline
        self.stages["optimize"] = self._run_optimize
        self.stages["validate"] = self._run_validate
        self.stages["patch"] = self._run_patch

    def run(
        self,
        run_dir: Path,
        to_stage: str = "patch",
    ) -> dict[str, Any]:
        results = {}

        for stage_name in STAGE_ORDER:
            if stage_name not in self.stages:
                continue

            stage_fn = self.stages[stage_name]
            try:
                result = stage_fn(run_dir)
                results[stage_name] = result

                if not result.get("success", False):
                    break

            except Exception as e:
                results[stage_name] = {
                    "success": False,
                    "error": str(e),
                }
                break

            if stage_name == to_stage:
                break

        return results

    def _run_discovery(self, run_dir: Path) -> dict:
        from ..stages.discovery import Scanner

        scanner = Scanner(self.config)
        root_path = self.config.get("project", {}).get("root_path", ".")

        result = scanner.scan(root_path)

        output_path = run_dir / "discovery" / "sql_units.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(result.sql_units, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "sql_units_count": result.total_count,
            "errors": result.errors,
            "warnings": result.warnings,
        }

    def _run_branching(self, run_dir: Path) -> dict:
        from ..stages.branching.brancher import Brancher

        discovery_path = run_dir / "discovery" / "sql_units.json"
        if not discovery_path.exists():
            return {"success": False, "error": "Discovery results not found"}

        with open(discovery_path) as f:
            sql_units = json.load(f)

        branch_cfg = self.config.get("branching", {})
        brancher = Brancher(
            strategy=branch_cfg.get("strategy", "all_combinations"),
            max_branches=branch_cfg.get("max_branches", 100),
        )

        total_branches = 0
        for unit in sql_units:
            sql_text = unit.get("templateSql", unit.get("sql", ""))
            branches = brancher.generate(sql_text)
            unit["branches"] = [
                {
                    "branch_id": b.branch_id,
                    "active_conditions": b.active_conditions,
                    "sql": b.sql,
                    "condition_count": b.condition_count,
                    "risk_flags": b.risk_flags,
                }
                for b in branches
            ]
            unit["branchCount"] = len(branches)
            total_branches += len(branches)

        output_path = run_dir / "branching" / "sql_units_with_branches.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(sql_units, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "total_branches": total_branches,
        }

    def _run_pruning(self, run_dir: Path) -> dict:
        from ..stages.pruning import RiskDetector, analyze_risks

        branching_path = run_dir / "branching" / "sql_units_with_branches.json"
        if not branching_path.exists():
            return {"success": False, "error": "Branching results not found"}

        with open(branching_path) as f:
            sql_units = json.load(f)

        all_risks = analyze_risks(sql_units)

        output_path = run_dir / "pruning" / "risks.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(all_risks, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "risks_count": len(all_risks),
        }

    def _run_baseline(self, run_dir: Path) -> dict:
        from ..stages.baseline_stage import collect_baseline

        branching_path = run_dir / "branching" / "sql_units_with_branches.json"
        if not branching_path.exists():
            return {"success": False, "error": "Branching results not found"}

        with open(branching_path) as f:
            sql_units = json.load(f)

        baselines = collect_baseline(self.config, sql_units)

        output_path = run_dir / "baseline" / "baselines.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(baselines, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "baselines_count": len(baselines),
        }

    def _run_optimize(self, run_dir: Path) -> dict:
        from ..stages.optimize_stage.rule_engine import apply_rules

        baseline_path = run_dir / "baseline" / "baselines.json"
        if not baseline_path.exists():
            return {"success": False, "error": "Baseline results not found"}

        with open(baseline_path) as f:
            baselines = json.load(f)

        proposals = []
        for baseline in baselines:
            sql = baseline.get("sql", "")
            rule_results = apply_rules(sql)
            if rule_results:
                proposals.append(
                    {
                        "sqlKey": baseline.get("sqlKey"),
                        "originalSql": sql,
                        "optimizations": [
                            {
                                "ruleName": r.rule_name,
                                "optimizedSql": r.optimized_sql,
                                "improvement": r.improvement,
                            }
                            for r in rule_results
                        ],
                    }
                )

        output_path = run_dir / "optimize" / "proposals.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(proposals, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "proposals_count": len(proposals),
        }

    def _run_validate(self, run_dir: Path) -> dict:
        from ..stages.validate_stage.semantic_checker import SemanticChecker

        optimize_path = run_dir / "optimize" / "proposals.json"
        if not optimize_path.exists():
            return {"success": False, "error": "Optimize results not found"}

        with open(optimize_path) as f:
            proposals = json.load(f)

        checker = SemanticChecker()
        validations = []
        for proposal in proposals:
            for opt in proposal.get("optimizations", []):
                original = opt.get("originalSql", "")
                optimized = opt.get("optimizedSql", "")
                if original and optimized:
                    result = checker._perform_validation(original, optimized)
                    validations.append(
                        {
                            "sqlKey": proposal.get("sqlKey"),
                            "ruleName": opt.get("ruleName"),
                            "isEquivalent": result.is_equivalent,
                            "confidence": result.confidence,
                            "reason": result.reason,
                        }
                    )

        output_path = run_dir / "validate" / "validations.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(validations, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "validations_count": len(validations),
        }

    def _run_patch(self, run_dir: Path) -> dict:
        from ..stages.patch_stage.patch_generator import PatchGenerator

        validate_path = run_dir / "validate" / "validations.json"
        if not validate_path.exists():
            return {"success": False, "error": "Validate results not found"}

        with open(validate_path) as f:
            validations = json.load(f)

        generator = PatchGenerator()
        patches = []
        for validation in validations:
            if validation.get("isEquivalent", False):
                patches.append(
                    {
                        "sqlKey": validation.get("sqlKey"),
                        "ruleName": validation.get("ruleName"),
                        "status": "ready",
                        "applied": False,
                    }
                )

        output_path = run_dir / "patch" / "patches.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(patches, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "patches_count": len(patches),
        }


def run_v8_workflow(config: dict, run_dir: Path, to_stage: str = "patch") -> dict:
    engine = V8WorkflowEngine(config)
    return engine.run(run_dir, to_stage)
