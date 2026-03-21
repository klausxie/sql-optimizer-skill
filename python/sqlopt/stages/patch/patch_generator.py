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
    def generate_patch(self, sql_unit: dict[str, Any], proposal: dict[str, Any]) -> str:
        namespace = str(sql_unit.get("namespace") or "unknown")
        statement_id = str(sql_unit.get("statementId") or "unknown")
        result_type = str(sql_unit.get("resultType") or "map")
        rewritten_sql = str(_proposal_rewritten_sql(sql_unit, proposal) or sql_unit.get("sql") or "")
        return (
            f"<!-- SQL Optimizer patch for {namespace}.{statement_id} -->\n"
            f"<select id=\"{statement_id}\" resultType=\"{result_type}\">\n"
            f"  {rewritten_sql}\n"
            f"</select>\n"
        )


def _proposal_rewritten_sql(sql_unit: dict[str, Any], proposal: dict[str, Any]) -> str:
    selected_candidate_id = str(proposal.get("selectedCandidateId") or "").strip()
    if selected_candidate_id:
        for row in list(proposal.get("suggestions") or []) + list(proposal.get("llmCandidates") or []):
            if isinstance(row, dict) and str(row.get("id") or "").strip() == selected_candidate_id:
                text = str(row.get("rewrittenSql") or "").strip()
                if text:
                    return text

    for key in ("optimizedSql", "rewrittenSql"):
        text = str(proposal.get(key) or "").strip()
        if text:
            return text

    for row in list(proposal.get("suggestions") or []) + list(proposal.get("llmCandidates") or []):
        if isinstance(row, dict):
            text = str(row.get("rewrittenSql") or "").strip()
            if text:
                return text

    return str(sql_unit.get("sql") or "").strip()


def execute_one(
    sql_unit: dict,
    proposal: dict,
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict:
    config = config or {}
    paths = canonical_paths(run_dir)
    paths.ensure_layout()
    sql_key = str(sql_unit.get("sqlKey") or proposal.get("sqlKey") or "unknown")
    statement_key = sql_key
    rewritten_sql = _proposal_rewritten_sql(sql_unit, proposal)

    patch_files: list[str] = []
    applicable = bool(proposal.get("validated")) and bool(rewritten_sql and sql_unit.get("xmlPath"))
    apply_check_error: str | None = None
    diff_summary = {"filesChanged": 0, "hunks": 0, "summary": "no patch generated"}

    if applicable:
        generator = PatchGenerator()
        patch_text = generator.generate_patch(sql_unit, proposal)
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
        "selectedCandidateId": proposal.get("selectedCandidateId"),
        "candidatesEvaluated": len(proposal.get("candidateEvaluations") or []) or 1,
        "applicable": applicable,
        "applyCheckError": apply_check_error,
        "selectionReason": proposal.get("selectionReason") or proposal.get("selectionRationale"),
        "patchability": proposal.get("patchability"),
        "strategyType": ((proposal.get("selectedPatchStrategy") or {}).get("strategyType") if isinstance(proposal.get("selectedPatchStrategy"), dict) else None),
        "gates": {
            "semanticEquivalenceStatus": ((proposal.get("semanticEquivalence") or {}).get("status") if isinstance(proposal.get("semanticEquivalence"), dict) else None),
            "semanticEquivalenceBlocking": not bool(proposal.get("validated")),
            "semanticConfidence": ((proposal.get("semanticEquivalence") or {}).get("confidence") if isinstance(proposal.get("semanticEquivalence"), dict) else None),
            "semanticEvidenceLevel": ((proposal.get("semanticEquivalence") or {}).get("evidenceLevel") if isinstance(proposal.get("semanticEquivalence"), dict) else None),
        },
    }

    validator.validate("patch_result", patch_result)
    append_jsonl(paths.patches_path, patch_result)
    log_event(paths.manifest_path, "patch", "done", {"statement_key": sql_key})
    return patch_result
