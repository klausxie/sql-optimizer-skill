from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...run_paths import canonical_paths


def run_patch(
    run_dir: Path,
    *,
    validator: ContractValidator,
) -> dict[str, Any]:
    paths = canonical_paths(run_dir)
    optimize_path = paths.v9_proposals_path
    if not optimize_path.exists():
        return {"success": False, "error": "Optimize results not found"}

    with open(optimize_path) as f:
        proposals = json.load(f)

    patches = []
    for proposal in proposals:
        validator.validate_stage_input("patch", proposal)
        if not proposal.get("validated", False):
            continue

        sql_key = proposal.get("sqlKey", "unknown")
        original_sql = proposal.get("originalSql", "")
        optimized_sql = proposal.get("optimizedSql", original_sql)
        rule_name = proposal.get("ruleName", "unknown")

        patch_result = {
            "sqlKey": sql_key,
            "statementKey": sql_key,
            "patchFiles": [],
            "diffSummary": {
                "filesChanged": 1 if optimized_sql != original_sql else 0,
                "hunks": 1 if optimized_sql != original_sql else 0,
                "summary": f"rewrite by {rule_name}"
                if optimized_sql != original_sql
                else "no change",
            },
            "applyMode": "manual",
            "rollback": "restore original mapper backup",
            "applicable": optimized_sql != original_sql,
            "originalSql": original_sql,
            "optimizedSql": optimized_sql,
            "ruleName": rule_name,
        }

        if patch_result["applicable"]:
            patch_content = (
                f"-- SQL Optimizer patch: {sql_key}\n-- Rule: {rule_name}\n{optimized_sql}"
            )
            patch_dir = paths.v9_patch_files_dir
            patch_dir.mkdir(parents=True, exist_ok=True)
            patch_file = patch_dir / f"{sql_key.replace('/', '_')}.sql"
            patch_file.write_text(patch_content, encoding="utf-8")
            patch_result["patchFiles"] = [str(patch_file)]

        patches.append(patch_result)
        validator.validate_stage_output("patch", patch_result)

    output_path = paths.v9_patch_results_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(patches, f, indent=2, ensure_ascii=False)

    return {
        "success": True,
        "output_file": str(output_path),
        "patches_count": len(patches),
        "applicable_count": sum(1 for p in patches if p.get("applicable")),
    }
