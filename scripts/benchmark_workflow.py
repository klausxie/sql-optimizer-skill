#!/usr/bin/env python3
"""
Benchmark script for V9 workflow performance measurement.

Measures:
- Total execution time
- Per-stage execution time
- Peak memory usage

Usage:
    python3 scripts/benchmark_workflow.py [--runs N] [--output FILE]
"""

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))


from sqlopt.v9_pipeline import STAGE_ORDER


def create_mock_config() -> dict:
    """Create a minimal mock configuration for benchmarking."""
    return {
        "config_version": "v1",
        "project": {
            "root_path": str(ROOT / "tests" / "fixtures"),
        },
        "scan": {
            "mapper_globs": [
                "**/*.xml",
            ],
        },
        "db": {
            "platform": "postgresql",
            "dsn": "postgresql://mock:mock@localhost:5432/mock",
        },
        "llm": {
            "enabled": False,
        },
    }


def create_mock_sql_units(count: int = 10) -> list[dict]:
    """Create mock SQL units for benchmarking."""
    units = []
    for i in range(count):
        units.append(
            {
                "sqlKey": f"sql_{i}",
                "templateSql": f"SELECT * FROM table_{i} WHERE id = {{id}} AND name LIKE '%{{name}}%'",
                "sql": f"SELECT * FROM table_{i} WHERE id = 1 AND name LIKE '%test%'",
                "branchCount": 2,
                "branches": [
                    {
                        "branch_id": f"branch_{i}_0",
                        "active_conditions": ["id IS NOT NULL"],
                        "sql": f"SELECT * FROM table_{i} WHERE id IS NOT NULL",
                        "condition_count": 1,
                        "risk_flags": [],
                    },
                    {
                        "branch_id": f"branch_{i}_1",
                        "active_conditions": ["id IS NOT NULL", "name IS NOT NULL"],
                        "sql": f"SELECT * FROM table_{i} WHERE id IS NOT NULL AND name IS NOT NULL",
                        "condition_count": 2,
                        "risk_flags": ["suffix_wildcard_only"],
                    },
                ],
            }
        )
    return units


def run_stage_init(run_dir: Path, config: dict) -> dict:
    """Mock init stage - in real impl this would scan XML files."""
    time.sleep(0.01)  # Simulate work
    sql_units = create_mock_sql_units(count=10)
    output_path = run_dir / "init" / "sql_units.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(sql_units, f)
    return {
        "success": True,
        "output_file": str(output_path),
        "sql_units_count": len(sql_units),
    }


def run_stage_parse(run_dir: Path, config: dict) -> dict:
    """Mock parse stage - in real impl this would expand branches and risks."""
    time.sleep(0.035)  # Simulate branch expansion + risk analysis
    init_path = run_dir / "init" / "sql_units.json"
    if not init_path.exists():
        return {"success": False, "error": "Init results not found"}
    with open(init_path) as f:
        sql_units = json.load(f)
    units_output_path = run_dir / "parse" / "sql_units_with_branches.json"
    units_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(units_output_path, "w") as f:
        json.dump(sql_units, f)
    risks = []
    for unit in sql_units:
        for branch in unit.get("branches", []):
            for flag in branch.get("risk_flags", []):
                risks.append(
                    {
                        "sqlKey": unit.get("sqlKey"),
                        "branch_id": branch.get("branch_id"),
                        "risk_flag": flag,
                    }
                )
    risks_output_path = run_dir / "parse" / "risks.json"
    with open(risks_output_path, "w") as f:
        json.dump(risks, f)
    return {
        "success": True,
        "sql_units_file": str(units_output_path),
        "risks_file": str(risks_output_path),
        "total_branches": sum(u.get("branchCount", 0) for u in sql_units),
        "risks_count": len(risks),
    }


def run_stage_recognition(run_dir: Path, config: dict) -> dict:
    """Mock recognition stage - in real impl this would call database EXPLAIN."""
    time.sleep(0.03)  # Simulate work (database call)
    parse_path = run_dir / "parse" / "sql_units_with_branches.json"
    if not parse_path.exists():
        return {"success": False, "error": "Parse results not found"}
    with open(parse_path) as f:
        sql_units = json.load(f)
    baselines = []
    for unit in sql_units:
        for branch in unit.get("branches", [])[:1]:  # Only first branch
            baselines.append(
                {
                    "sqlKey": unit.get("sqlKey"),
                    "branch_id": branch.get("branch_id"),
                    "sql": branch.get("sql", ""),
                    "plan": {
                        "operation": "Seq Scan",
                        "estimated_cost": 100.0,
                    },
                }
            )
    output_path = run_dir / "recognition" / "baselines.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(baselines, f)
    return {
        "success": True,
        "output_file": str(output_path),
        "baselines_count": len(baselines),
    }


def run_stage_optimize(run_dir: Path, config: dict) -> dict:
    """Mock optimize stage - in real impl this would propose and validate rewrites."""
    time.sleep(0.09)  # Simulate rule engine + validation work
    baseline_path = run_dir / "recognition" / "baselines.json"
    if not baseline_path.exists():
        return {"success": False, "error": "Recognition results not found"}
    with open(baseline_path) as f:
        baselines = json.load(f)
    proposals = []
    for baseline in baselines:
        proposals.append(
            {
                "sqlKey": baseline.get("sqlKey"),
                "originalSql": baseline.get("sql", ""),
                "ruleName": "index_usage",
                "optimizedSql": baseline.get("sql", "").replace(
                    "SELECT *", "SELECT id, name"
                ),
                "validated": True,
                "validationStatus": "PASS",
            }
        )
    output_path = run_dir / "optimize" / "proposals.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(proposals, f)
    return {
        "success": True,
        "output_file": str(output_path),
        "proposals_count": len(proposals),
    }


def run_stage_patch(run_dir: Path, config: dict) -> dict:
    """Mock patch stage - in real impl this would generate XML patches."""
    time.sleep(0.01)  # Simulate work
    optimize_path = run_dir / "optimize" / "proposals.json"
    if not optimize_path.exists():
        return {"success": False, "error": "Optimize results not found"}
    with open(optimize_path) as f:
        proposals = json.load(f)
    patches = []
    for proposal in proposals:
        if proposal.get("validated", False):
            patches.append(
                {
                    "sqlKey": proposal.get("sqlKey"),
                    "ruleName": proposal.get("ruleName"),
                    "status": "ready",
                    "applied": False,
                }
            )
    output_path = run_dir / "patch" / "patches.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(patches, f)
    return {
        "success": True,
        "output_file": str(output_path),
        "patches_count": len(patches),
    }


STAGE_FUNCTIONS = {
    "init": run_stage_init,
    "parse": run_stage_parse,
    "recognition": run_stage_recognition,
    "optimize": run_stage_optimize,
    "patch": run_stage_patch,
}


def run_workflow_benchmark(
    run_dir: Path,
    config: dict,
) -> dict[str, Any]:
    """Run one benchmark iteration and return timing data."""
    stage_times = {}
    tracemalloc.start()

    for stage_name in STAGE_ORDER:
        stage_fn = STAGE_FUNCTIONS.get(stage_name)
        if stage_fn is None:
            continue

        start_time = time.perf_counter()
        stage_fn(run_dir, config)
        end_time = time.perf_counter()

        stage_times[stage_name] = end_time - start_time

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    total_time = sum(stage_times.values())

    return {
        "total_time": total_time,
        "stages": stage_times,
        "memory_peak_bytes": peak,
        "memory_peak_mb": peak / (1024 * 1024),
    }


def average_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Average benchmark results over multiple runs."""
    if not results:
        return {}

    num_runs = len(results)
    avg_stage_times = {}

    for stage in STAGE_ORDER:
        stage_times = [r["stages"].get(stage, 0) for r in results]
        avg_stage_times[stage] = sum(stage_times) / num_runs

    total_times = [r["total_time"] for r in results]
    avg_total_time = sum(total_times) / num_runs

    memory_peaks = [r["memory_peak_bytes"] for r in results]
    avg_memory_peak = sum(memory_peaks) / num_runs

    return {
        "runs": num_runs,
        "total_time": avg_total_time,
        "stages": avg_stage_times,
        "memory_peak_bytes": avg_memory_peak,
        "memory_peak_mb": avg_memory_peak / (1024 * 1024),
        "raw_results": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark V9 workflow performance",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of benchmark runs to average (default: 1)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path for JSON results (default: stdout)",
    )
    args = parser.parse_args()

    config = create_mock_config()
    results = []

    for i in range(args.runs):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            result = run_workflow_benchmark(run_dir, config)
            results.append(result)

    if args.runs > 1:
        output = average_results(results)
    else:
        output = results[0] if results else {}

    output_json = json.dumps(output, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_json)
        print(f"Results written to {args.output}")
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
