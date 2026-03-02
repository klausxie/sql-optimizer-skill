from __future__ import annotations

from pathlib import Path


def skip_patch_result(
    *,
    sql_key: str,
    statement_key: str,
    reason_code: str,
    reason_message: str,
    candidates_evaluated: int,
    selected_candidate_id: str | None = None,
    applicable: bool | None = None,
    apply_check_error: str | None = None,
) -> dict:
    patch = {
        "sqlKey": sql_key,
        "statementKey": statement_key,
        "patchFiles": [],
        "diffSummary": {"skipped": True},
        "applyMode": "PATCH_ONLY",
        "rollback": "not_applied",
        "selectionReason": {"code": reason_code, "message": reason_message},
        "rejectedCandidates": [{"reason_code": reason_code}],
        "candidatesEvaluated": candidates_evaluated,
    }
    if selected_candidate_id is not None:
        patch["selectedCandidateId"] = selected_candidate_id
    if applicable is not None:
        patch["applicable"] = applicable
        patch["applyCheckError"] = apply_check_error
    return patch


def selected_patch_result(
    *,
    sql_key: str,
    statement_key: str,
    patch_file: Path,
    changed_lines: int,
    candidates_evaluated: int,
    selected_candidate_id: str | None,
) -> dict:
    return {
        "sqlKey": sql_key,
        "statementKey": statement_key,
        "patchFiles": [str(patch_file)],
        "diffSummary": {"lines": changed_lines, "changed": bool(changed_lines)},
        "applyMode": "PATCH_ONLY",
        "rollback": "delete_patch_file",
        "selectedCandidateId": selected_candidate_id,
        "candidatesEvaluated": candidates_evaluated,
        "selectionReason": {"code": "PATCH_SELECTED_SINGLE_PASS", "message": "single pass variant"},
        "rejectedCandidates": [],
        "applicable": True,
        "applyCheckError": None,
    }
