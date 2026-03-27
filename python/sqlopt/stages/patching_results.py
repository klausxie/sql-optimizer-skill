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
    delivery_outcome: dict | None = None,
    repair_hints: list[dict] | None = None,
    patchability: dict | None = None,
    selection_evidence: dict | None = None,
    fallback_reason_codes: list[str] | None = None,
    patch_target: dict | None = None,
    replay_evidence: dict | None = None,
    syntax_evidence: dict | None = None,
    artifact_kind: str | None = None,
    delivery_stage: str | None = None,
    failure_class: str | None = None,
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
    patch_family = str((patch_target or {}).get("family") or "").strip()
    if patch_family:
        patch["patchFamily"] = patch_family
    if applicable is not None:
        patch["applicable"] = applicable
        patch["applyCheckError"] = apply_check_error
    if delivery_outcome is not None:
        patch["deliveryOutcome"] = delivery_outcome
    if repair_hints is not None:
        patch["repairHints"] = repair_hints
    if patchability is not None:
        patch["patchability"] = patchability
    if selection_evidence is not None:
        patch["selectionEvidence"] = selection_evidence
    if fallback_reason_codes is not None:
        patch["fallbackReasonCodes"] = list(fallback_reason_codes)
    if replay_evidence is not None:
        patch["replayEvidence"] = dict(replay_evidence)
    if syntax_evidence is not None:
        patch["syntaxEvidence"] = dict(syntax_evidence)
    if artifact_kind is not None:
        patch["artifactKind"] = artifact_kind
    if delivery_stage is not None:
        patch["deliveryStage"] = delivery_stage
    if failure_class is not None:
        patch["failureClass"] = failure_class
    return patch


def selected_patch_result(
    *,
    sql_key: str,
    statement_key: str,
    patch_file: Path,
    changed_lines: int,
    candidates_evaluated: int,
    selected_candidate_id: str | None,
    delivery_outcome: dict | None = None,
    repair_hints: list[dict] | None = None,
    patchability: dict | None = None,
    selection_evidence: dict | None = None,
    fallback_reason_codes: list[str] | None = None,
    patch_target: dict | None = None,
    replay_evidence: dict | None = None,
    syntax_evidence: dict | None = None,
    artifact_kind: str | None = None,
    delivery_stage: str | None = None,
    failure_class: str | None = None,
) -> dict:
    patch = {
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
    patch_family = str((patch_target or {}).get("family") or "").strip()
    if patch_family:
        patch["patchFamily"] = patch_family
    if delivery_outcome is not None:
        patch["deliveryOutcome"] = delivery_outcome
    if repair_hints is not None:
        patch["repairHints"] = repair_hints
    if patchability is not None:
        patch["patchability"] = patchability
    if selection_evidence is not None:
        patch["selectionEvidence"] = selection_evidence
    if fallback_reason_codes is not None:
        patch["fallbackReasonCodes"] = list(fallback_reason_codes)
    if replay_evidence is not None:
        patch["replayEvidence"] = dict(replay_evidence)
    if syntax_evidence is not None:
        patch["syntaxEvidence"] = dict(syntax_evidence)
    if artifact_kind is not None:
        patch["artifactKind"] = artifact_kind
    if delivery_stage is not None:
        patch["deliveryStage"] = delivery_stage
    if failure_class is not None:
        patch["failureClass"] = failure_class
    return patch
