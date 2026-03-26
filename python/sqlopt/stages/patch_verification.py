from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..run_paths import canonical_paths
from ..verification.models import VerificationCheck, VerificationRecord
from ..verification.writer import append_verification_record


def append_patch_verification(
    *,
    run_dir: Path,
    validator: ContractValidator,
    patch: dict[str, Any],
    acceptance: dict[str, Any],
    status: str,
    semantic_gate_status: str,
    semantic_gate_confidence: str,
    sql_key: str,
    statement_key: str,
    same_statement: list[dict[str, Any]],
    pass_rows: list[dict[str, Any]],
) -> None:
    paths = canonical_paths(run_dir)
    selection_reason = dict(patch.get("selectionReason") or {})
    patch_target = dict(patch.get("patchTarget") or acceptance.get("patchTarget") or {})
    template_ops = [
        row
        for row in ((patch_target.get("templateRewriteOps") if patch_target else acceptance.get("templateRewriteOps")) or [])
        if isinstance(row, dict)
    ]
    rewrite_materialization = dict(
        (patch_target.get("rewriteMaterialization") if patch_target else acceptance.get("rewriteMaterialization")) or {}
    )
    replay_verified = rewrite_materialization.get("replayVerified")
    replay_result = dict(patch.get("replayEvidence") or {})
    syntax_result = dict(patch.get("syntaxEvidence") or {})
    replay_matches_target = replay_result.get("matchesTarget")
    replay_reason_code = str(replay_result.get("driftReason") or "").strip() or None
    xml_parse_ok = syntax_result.get("xmlParseOk")
    render_ok = syntax_result.get("renderOk", syntax_result.get("renderedSqlPresent"))
    sql_parse_ok = syntax_result.get("sqlParseOk", syntax_result.get("ok"))
    syntax_ok = syntax_result.get("ok")
    applicable = patch.get("applicable")
    selection_code = str(selection_reason.get("code") or "").strip()
    pass_has_clear_winner = status != "PASS" or (len(pass_rows) == 1 and str(pass_rows[0].get("sqlKey") or "") == sql_key)
    requires_patch_target = applicable is True
    replay_evidence_required = applicable is True and bool(patch_target)
    syntax_evidence_required = applicable is True and bool(patch_target)
    patch_target_ok = bool(patch_target) or not requires_patch_target
    replay_check_ok = (
        bool(replay_matches_target)
        if replay_evidence_required
        else (True if replay_matches_target is None else bool(replay_matches_target))
    )
    replay_check_reason = None
    if not replay_check_ok:
        replay_check_reason = replay_reason_code or (
            "PATCH_DECISION_EVIDENCE_INCOMPLETE" if replay_matches_target is None else "PATCH_TARGET_DRIFT"
        )
    xml_check_ok = True if xml_parse_ok is None and not syntax_evidence_required else bool(xml_parse_ok)
    render_check_ok = True if render_ok is None and not syntax_evidence_required else bool(render_ok)
    sql_check_ok = True if sql_parse_ok is None and not syntax_evidence_required else bool(sql_parse_ok)
    syntax_missing_reason = "PATCH_DECISION_EVIDENCE_INCOMPLETE" if syntax_evidence_required else None
    checks = [
        VerificationCheck(
            "patch_target_present",
            patch_target_ok,
            "error" if requires_patch_target else "info",
            None if patch_target_ok else "PATCH_TARGET_CONTRACT_MISSING",
        ),
        VerificationCheck(
            "acceptance_pass_required",
            status == "PASS",
            "warn",
            None if status == "PASS" else "PATCH_ACCEPTANCE_NOT_PASS",
        ),
        VerificationCheck(
            "semantic_gate_pass_required",
            semantic_gate_status == "PASS",
            "warn" if status == "PASS" else "info",
            None if semantic_gate_status == "PASS" else "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
        ),
        VerificationCheck(
            "semantic_confidence_sufficient",
            semantic_gate_confidence in {"MEDIUM", "HIGH"},
            "warn" if status == "PASS" else "info",
            None if semantic_gate_confidence in {"MEDIUM", "HIGH"} else "PATCH_SEMANTIC_CONFIDENCE_LOW",
        ),
        VerificationCheck(
            "clear_winner_present",
            pass_has_clear_winner,
            "warn" if status == "PASS" else "info",
            None if pass_has_clear_winner else "PATCH_CONFLICT_NO_CLEAR_WINNER",
        ),
        VerificationCheck(
            "template_replay_verified",
            (not template_ops) or replay_verified is True,
            "error" if template_ops else "info",
            None if (not template_ops) or replay_verified is True else "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED",
        ),
        VerificationCheck(
            "patch_applicability_recorded",
            (applicable is True) or (applicable is False) or bool(selection_code),
            "warn",
            None if (applicable is True) or (applicable is False) or bool(selection_code) else "PATCH_APPLICABILITY_UNKNOWN",
        ),
        VerificationCheck(
            "replay_matches_target",
            replay_check_ok,
            "error" if replay_evidence_required or replay_matches_target is not None else "info",
            replay_check_reason,
        ),
        VerificationCheck(
            "xml_parse_ok",
            xml_check_ok,
            "error" if syntax_evidence_required or xml_parse_ok is not None else "info",
            None if xml_check_ok else (syntax_missing_reason if xml_parse_ok is None else "PATCH_SYNTAX_INVALID"),
        ),
        VerificationCheck(
            "render_ok",
            render_check_ok,
            "error" if syntax_evidence_required or render_ok is not None else "info",
            None if render_check_ok else (syntax_missing_reason if render_ok is None else "PATCH_SYNTAX_INVALID"),
        ),
        VerificationCheck(
            "sql_parse_ok",
            sql_check_ok,
            "error" if syntax_evidence_required or sql_parse_ok is not None else "info",
            None if sql_check_ok else (syntax_missing_reason if sql_parse_ok is None else "PATCH_SYNTAX_INVALID"),
        ),
        VerificationCheck(
            "apply_check_ok",
            applicable is True if applicable is not None else True,
            "error" if applicable is not None else "info",
            None if applicable in {None, True} else (selection_code or "PATCH_NOT_APPLICABLE"),
        ),
    ]
    if template_ops and replay_verified is not True:
        verification_status = "UNVERIFIED"
        verification_reason_code = "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED"
        verification_reason_message = "template patch path was considered without replay verification"
    elif replay_matches_target is False:
        verification_status = "UNVERIFIED"
        verification_reason_code = replay_reason_code or "PATCH_TARGET_DRIFT"
        verification_reason_message = "patch replay did not match the persisted patch target"
    elif syntax_ok is False:
        verification_status = "UNVERIFIED"
        verification_reason_code = str(syntax_result.get("reasonCode") or "PATCH_SYNTAX_INVALID")
        verification_reason_message = "patch syntax checks did not pass"
    elif selection_code == "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS":
        verification_status = "VERIFIED"
        verification_reason_code = "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS"
        verification_reason_message = "patch generation was intentionally blocked by semantic equivalence gate"
    elif selection_code == "PATCH_SEMANTIC_CONFIDENCE_LOW":
        verification_status = "VERIFIED"
        verification_reason_code = "PATCH_SEMANTIC_CONFIDENCE_LOW"
        verification_reason_message = "patch generation was intentionally blocked due to low semantic confidence"
    elif applicable is True and not patch_target:
        verification_status = "UNVERIFIED"
        verification_reason_code = "PATCH_TARGET_CONTRACT_MISSING"
        verification_reason_message = "applicable patch is missing persisted patchTarget contract"
    elif applicable is True and replay_matches_target is None:
        verification_status = "UNVERIFIED"
        verification_reason_code = "PATCH_DECISION_EVIDENCE_INCOMPLETE"
        verification_reason_message = "applicable patch is missing replay verification evidence"
    elif applicable is True and syntax_ok is None:
        verification_status = "UNVERIFIED"
        verification_reason_code = "PATCH_DECISION_EVIDENCE_INCOMPLETE"
        verification_reason_message = "applicable patch is missing syntax verification evidence"
    elif applicable is True:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code or "PATCH_APPLICABLE_VERIFIED"
        verification_reason_message = "patch was selected and passed git apply --check"
    elif applicable is False:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code or "PATCH_NOT_APPLICABLE"
        verification_reason_message = "patch was rejected with an explicit apply-check failure"
    elif selection_code:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code
        verification_reason_message = str(selection_reason.get("message") or "patch was skipped for an explicit rule")
    else:
        verification_status = "PARTIAL"
        verification_reason_code = "PATCH_DECISION_EVIDENCE_INCOMPLETE"
        verification_reason_message = "patch result exists but its selection evidence is incomplete"

    append_verification_record(
        run_dir,
        validator,
        VerificationRecord(
            run_id=run_dir.name,
            sql_key=sql_key,
            statement_key=statement_key,
            phase="patch_generate",
            status=verification_status,
            reason_code=verification_reason_code,
            reason_message=verification_reason_message,
            evidence_refs=[
                str(paths.acceptance_path),
                str(paths.patches_path),
                *[str(x) for x in (patch.get("patchFiles") or [])],
            ],
            inputs={
                "acceptance_status": status,
                "same_statement_count": len(same_statement),
                "pass_variant_count": len(pass_rows),
                "template_op_count": len(template_ops),
                "patch_target_present": bool(patch_target),
                "replay_verified": replay_verified,
                "replay_matches_target": replay_matches_target,
                "xml_parse_ok": xml_parse_ok,
                "render_ok": render_ok,
                "sql_parse_ok": sql_parse_ok,
                "semantic_gate_status": semantic_gate_status,
                "semantic_gate_confidence": semantic_gate_confidence,
            },
            checks=checks,
            verdict={
                "selection_code": selection_code or None,
                "applicable": applicable,
                "patch_file_count": len(patch.get("patchFiles") or []),
                "replay_matches_target": replay_matches_target,
                "syntax_ok": syntax_ok,
                "xml_parse_ok": xml_parse_ok,
                "render_ok": render_ok,
                "sql_parse_ok": sql_parse_ok,
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
