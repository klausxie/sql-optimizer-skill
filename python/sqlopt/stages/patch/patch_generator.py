"""V8 XML patch generator for MyBatis SQL optimization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...io_utils import append_jsonl, ensure_dir
from ...manifest import log_event
from ...run_paths import canonical_paths
from ...utils import sql_key_path_component


@dataclass
class PatchResult:
    sql_key: str
    patch_file: str | None
    applicable: bool


class PatchGenerator:
    def generate_patch(self, sql_unit: dict[str, Any], acceptance: dict[str, Any]) -> str:
        namespace = str(sql_unit.get("namespace") or "unknown")
        statement_id = str(sql_unit.get("statementId") or "unknown")
        result_type = str(sql_unit.get("resultType") or "map")
        rewritten_sql = str(acceptance.get("rewrittenSql") or sql_unit.get("sql") or "")
        return (
            f"<!-- SQL Optimizer patch for {namespace}.{statement_id} -->\n"
            f"<select id=\"{statement_id}\" resultType=\"{result_type}\">\n"
            f"  {rewritten_sql}\n"
            f"</select>\n"
        )


def execute_one(
    sql_unit: dict,
    acceptance: dict,
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict:
    config = config or {}
    paths = canonical_paths(run_dir)
    paths.ensure_layout()
    sql_key = str(sql_unit.get("sqlKey") or acceptance.get("sqlKey") or "unknown")
    statement_key = sql_key
    rewritten_sql = acceptance.get("rewrittenSql")

    patch_files: list[str] = []
    applicable = bool(rewritten_sql and sql_unit.get("xmlPath"))
    apply_check_error: str | None = None
    diff_summary = {"filesChanged": 0, "hunks": 0, "summary": "no patch generated"}

    if applicable:
        generator = PatchGenerator()
        patch_text = generator.generate_patch(sql_unit, acceptance)
        ensure_dir(paths.patch_files_dir)
        patch_file = paths.patch_files_dir / f"{sql_key_path_component(sql_key)}.patch"
        patch_file.write_text(patch_text, encoding="utf-8")
        patch_files = [str(patch_file)]
        diff_summary = {
            "filesChanged": 1,
            "hunks": 1,
            "summary": f"rewrite mapper statement for {statement_key}",
        }

    patch_result = {
        "sqlKey": sql_key,
        "statementKey": statement_key,
        "patchFiles": patch_files,
        "diffSummary": diff_summary,
        "applyMode": str(((config.get("apply", {}) or {}).get("mode") or "manual")).lower(),
        "rollback": "restore original mapper backup",
        "selectedCandidateId": acceptance.get("selectedCandidateId"),
        "candidatesEvaluated": len(acceptance.get("candidateEvaluations") or []) or 1,
        "applicable": applicable,
        "applyCheckError": apply_check_error,
        "selectionReason": acceptance.get("selectionReason") or acceptance.get("selectionRationale"),
    }

    validator.validate("patch_result", patch_result)
    append_jsonl(paths.patches_path, patch_result)
    log_event(paths.manifest_path, "patch", "done", {"statement_key": sql_key})
    return patch_result
