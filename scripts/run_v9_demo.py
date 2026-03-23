#!/usr/bin/env python3
"""
V9 Full Pipeline Run Script - Demo with Mock/Fallback
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from sqlopt.contracts import ContractValidator
from sqlopt.application.v9_stages import run_stage

MAPPER_PATH = (
    ROOT / "tests" / "real" / "mybatis-test" / "src" / "main" / "resources" / "mapper"
)

CONFIG = {
    "config_version": "v1",
    "project": {
        "root_path": str(ROOT / "tests" / "real" / "mybatis-test"),
    },
    "scan": {
        "mapper_globs": ["src/main/resources/mapper/**/*.xml"],
        "statement_types": ["SELECT", "INSERT", "UPDATE", "DELETE"],
    },
    "db": {
        "platform": "h2",
        "dsn": "h2:mem:testdb",
    },
    "llm": {
        "enabled": False,
        "provider": "heuristic",
    },
    "branching": {
        "strategy": "all_combinations",
        "max_branches": 100,
    },
    "optimize": {
        "provider": "heuristic",
    },
    "validate": {
        "allow_db_unreachable_fallback": True,
    },
    "report": {
        "enabled": True,
    },
}


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_stage_result(stage: str, result: dict) -> None:
    status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
    print(f"\n{status}: Stage '{stage}'")

    if "sql_units_count" in result:
        print(f"  - SQL Units: {result['sql_units_count']}")
    if "branches_count" in result:
        print(f"  - Branches: {result['branches_count']}")
    if "baselines_count" in result:
        print(f"  - Baselines: {result['baselines_count']}")
    if "proposals_count" in result:
        print(f"  - Proposals: {result['proposals_count']}")
    if "patches_count" in result:
        print(f"  - Patches: {result['patches_count']}")

    if not result.get("success"):
        print(f"  - Error: {result.get('error', 'Unknown error')}")


def load_json_file(file_path: Path) -> dict | list:
    if not file_path.exists():
        return {} if "patch" in str(file_path) else []
    with open(file_path) as f:
        return json.load(f)


def list_output_files(run_dir: Path) -> None:
    print("\n📁 Output Files:")
    for stage in ["init", "parse", "recognition", "optimize", "patch"]:
        stage_dir = run_dir / stage
        if stage_dir.exists():
            for f in stage_dir.iterdir():
                size = f.stat().st_size
                print(f"  {f.relative_to(run_dir)} ({size} bytes)")


def run_full_pipeline(run_id: str) -> dict:
    run_dir = ROOT / "tests" / "real" / "mybatis-test" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Run Directory: {run_dir}")

    validator = ContractValidator(ROOT)

    stages = ["init", "parse", "recognition", "optimize", "patch"]
    results = {}

    for stage in stages:
        print_header(f"Stage: {stage.upper()}")

        start_time = time.time()

        try:
            result = run_stage(
                stage,
                run_dir,
                config=CONFIG,
                validator=validator,
            )
            elapsed = time.time() - start_time

            result["elapsed_seconds"] = elapsed
            results[stage] = result

            print_stage_result(stage, result)
            print(f"  - Time: {elapsed:.2f}s")

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ EXCEPTION in stage '{stage}': {e}")
            results[stage] = {
                "success": False,
                "error": str(e),
                "elapsed_seconds": elapsed,
            }

    print_header("PIPELINE SUMMARY")

    total_time = sum(r.get("elapsed_seconds", 0) for r in results.values())
    success_count = sum(1 for r in results.values() if r.get("success"))
    print(f"Total Stages: {len(stages)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(stages) - success_count}")
    print(f"Total Time: {total_time:.2f}s")

    list_output_files(run_dir)

    summary = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "config": {
            "db_platform": CONFIG["db"]["platform"],
            "llm_enabled": CONFIG["llm"]["enabled"],
            "optimizer_provider": CONFIG["optimize"]["provider"],
        },
        "stages": {
            stage: {"success": r.get("success"), "elapsed": r.get("elapsed_seconds")}
            for stage, r in results.items()
        },
        "results": results,
    }

    summary_path = run_dir / "pipeline_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n📄 Summary saved to: {summary_path}")

    return results


if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"demo_{timestamp}"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║         V9 SQL OPTIMIZER - FULL PIPELINE DEMO              ║
║                                                              ║
║  Mode: Mock/H2 Fallback (No Real Database)                  ║
║  Run ID: {run_id:<46}║
╚══════════════════════════════════════════════════════════════╝
    """)

    results = run_full_pipeline(run_id)

    if any(not r.get("success") for r in results.values()):
        sys.exit(1)
