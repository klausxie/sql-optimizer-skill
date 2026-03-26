from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..patch_families.models import PatchFamilyVerificationPolicy
from ..patch_families.registry import lookup_patch_family_spec
from ..run_paths import canonical_paths
from ..verification.models import VerificationCheck, VerificationRecord
from ..verification.writer import append_verification_record

DEFAULT_VERIFICATION_POLICY = PatchFamilyVerificationPolicy(
    require_replay_match=True,
    require_xml_parse=True,
    require_render_ok=True,
    require_sql_parse=True,
    require_apply_check=True,
)


def _resolve_verification_policy(
    *,
    applicable: Any,
    patch_target: dict[str, Any],
) -> tuple[PatchFamilyVerificationPolicy, bool]:
    family = str((patch_target or {}).get("family") or "").strip()
    spec = lookup_patch_family_spec(family) if family else None
    return (
        spec.verification if spec is not None else DEFAULT_VERIFICATION_POLICY,
        applicable is True and bool(patch_target) and spec is None,
    )


def _verification_reason_message(check: VerificationCheck) -> str:
    messages = {
        "PATCH_FAMILY_SPEC_MISSING": "applicable patch family is not registered in the verification policy registry",
        "PATCH_TARGET_CONTRACT_MISSING": "applicable patch is missing persisted patchTarget contract",
        "PATCH_DECISION_EVIDENCE_INCOMPLETE": "applicable patch is missing required verification evidence",
        "PATCH_TARGET_DRIFT": "patch replay did not match the persisted patch target",
        "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED": "template patch path was considered without replay verification",
        "PATCH_SYNTAX_INVALID": "patch syntax checks did not pass",
    }
    return messages.get(
        str(check.reason_code or "").strip().upper(),
        "patch verification policy requirements were not satisfied",
    )


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
    verification_policy, family_spec_missing = _resolve_verification_policy(
        applicable=applicable,
        patch_target=patch_target,
    )
    replay_required = bool(verification_policy.require_replay_match and patch_target)
    replay_evidence_required = applicable is True and replay_required
    template_replay_required = applicable is True and bool(template_ops) and replay_required
    xml_required = verification_policy.require_xml_parse
    xml_evidence_required = applicable is True and xml_required
    render_required = verification_policy.require_render_ok
    render_evidence_required = applicable is True and render_required
    sql_required = verification_policy.require_sql_parse
    sql_evidence_required = applicable is True and sql_required
    syntax_aggregate_required = applicable is True and any((xml_required, render_required, sql_required))
    apply_required = verification_policy.require_apply_check
    apply_evidence_required = applicable is True and apply_required
    patch_target_ok = bool(patch_target) or not requires_patch_target
    if replay_matches_target is None:
        replay_check_ok = not replay_evidence_required
    elif replay_required:
        replay_check_ok = bool(replay_matches_target)
    else:
        replay_check_ok = True
    replay_check_reason = None
    if not replay_check_ok:
        replay_check_reason = replay_reason_code or (
            "PATCH_DECISION_EVIDENCE_INCOMPLETE" if replay_matches_target is None else "PATCH_TARGET_DRIFT"
        )
    if xml_parse_ok is None:
        xml_check_ok = not xml_evidence_required
    else:
        xml_check_ok = bool(xml_parse_ok) if xml_required else True
    if render_ok is None:
        render_check_ok = not render_evidence_required
    else:
        render_check_ok = bool(render_ok) if render_required else True
    if sql_parse_ok is None:
        sql_check_ok = not sql_evidence_required
    else:
        sql_check_ok = bool(sql_parse_ok) if sql_required else True
    if syntax_ok is None:
        syntax_aggregate_ok = True
    else:
        syntax_aggregate_ok = bool(syntax_ok) if syntax_aggregate_required else True
    syntax_aggregate_reason = None if syntax_aggregate_ok else "PATCH_SYNTAX_INVALID"
    xml_reason = None if xml_check_ok else ("PATCH_DECISION_EVIDENCE_INCOMPLETE" if xml_parse_ok is None else "PATCH_SYNTAX_INVALID")
    render_reason = (
        None if render_check_ok else ("PATCH_DECISION_EVIDENCE_INCOMPLETE" if render_ok is None else "PATCH_SYNTAX_INVALID")
    )
    sql_reason = None if sql_check_ok else ("PATCH_DECISION_EVIDENCE_INCOMPLETE" if sql_parse_ok is None else "PATCH_SYNTAX_INVALID")
    family_spec_ok = not family_spec_missing
    if applicable is None:
        apply_check_ok = not apply_evidence_required
    elif applicable is True:
        apply_check_ok = True
    else:
        apply_check_ok = not apply_required
    apply_check_reason = None
    if not apply_check_ok:
        apply_check_reason = (
            "PATCH_DECISION_EVIDENCE_INCOMPLETE"
            if applicable is None
            else (selection_code or "PATCH_NOT_APPLICABLE")
        )
    checks = [
        VerificationCheck(
            "patch_target_present",
            patch_target_ok,
            "error" if requires_patch_target else "info",
            None if patch_target_ok else "PATCH_TARGET_CONTRACT_MISSING",
        ),
        VerificationCheck(
            "patch_family_spec_registered",
            family_spec_ok,
            "error" if bool(patch_target) and applicable is True else "info",
            None if family_spec_ok else "PATCH_FAMILY_SPEC_MISSING",
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
            "error" if template_replay_required else "info",
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
            "error" if replay_required else "info",
            replay_check_reason,
        ),
        VerificationCheck(
            "syntax_ok",
            syntax_aggregate_ok,
            "error" if syntax_aggregate_required else "info",
            syntax_aggregate_reason,
        ),
        VerificationCheck(
            "xml_parse_ok",
            xml_check_ok,
            "error" if xml_required else "info",
            xml_reason,
        ),
        VerificationCheck(
            "render_ok",
            render_check_ok,
            "error" if render_required else "info",
            render_reason,
        ),
        VerificationCheck(
            "sql_parse_ok",
            sql_check_ok,
            "error" if sql_required else "info",
            sql_reason,
        ),
        VerificationCheck(
            "apply_check_ok",
            apply_check_ok,
            "error" if apply_required else "info",
            apply_check_reason,
        ),
    ]
    required_failures = [check for check in checks if check.severity == "error" and check.ok is False]
    required_missing = [
        check for check in checks if check.severity == "error" and check.reason_code == "PATCH_DECISION_EVIDENCE_INCOMPLETE"
    ]
    proof_complete = not required_failures and not required_missing
    first_required_issue = required_missing[0] if required_missing else (required_failures[0] if required_failures else None)
    required_failures_by_name = {check.name: check for check in required_failures}
    replay_failure = required_failures_by_name.get("replay_matches_target")
    syntax_failure = next(
        (
            required_failures_by_name[name]
            for name in ("syntax_ok", "xml_parse_ok", "render_ok", "sql_parse_ok")
            if name in required_failures_by_name and required_failures_by_name[name].reason_code == "PATCH_SYNTAX_INVALID"
        ),
        None,
    )
    if applicable is True and not patch_target:
        verification_status = "UNVERIFIED"
        verification_reason_code = "PATCH_TARGET_CONTRACT_MISSING"
        verification_reason_message = "applicable patch is missing persisted patchTarget contract"
    elif applicable is True and family_spec_missing:
        verification_status = "UNVERIFIED"
        verification_reason_code = "PATCH_FAMILY_SPEC_MISSING"
        verification_reason_message = "applicable patch family is not registered in the verification policy registry"
    elif replay_failure is not None and replay_failure.reason_code not in {None, "PATCH_DECISION_EVIDENCE_INCOMPLETE"}:
        verification_status = "UNVERIFIED"
        verification_reason_code = str(replay_failure.reason_code or "PATCH_TARGET_DRIFT")
        verification_reason_message = _verification_reason_message(replay_failure)
    elif syntax_failure is not None:
        verification_status = "UNVERIFIED"
        verification_reason_code = str(syntax_failure.reason_code or "PATCH_SYNTAX_INVALID")
        verification_reason_message = _verification_reason_message(syntax_failure)
    elif selection_code == "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS":
        verification_status = "VERIFIED"
        verification_reason_code = "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS"
        verification_reason_message = "patch generation was intentionally blocked by semantic equivalence gate"
    elif selection_code == "PATCH_SEMANTIC_CONFIDENCE_LOW":
        verification_status = "VERIFIED"
        verification_reason_code = "PATCH_SEMANTIC_CONFIDENCE_LOW"
        verification_reason_message = "patch generation was intentionally blocked due to low semantic confidence"
    elif applicable is False and apply_required and not apply_check_ok:
        verification_status = "UNVERIFIED"
        verification_reason_code = str(apply_check_reason or selection_code or "PATCH_NOT_APPLICABLE")
        verification_reason_message = "patch failed a required apply-check verification"
    elif applicable is False:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code or "PATCH_NOT_APPLICABLE"
        verification_reason_message = "patch was rejected with an explicit apply-check failure"
    elif applicable is True and not proof_complete and first_required_issue is not None:
        verification_status = "UNVERIFIED"
        verification_reason_code = str(first_required_issue.reason_code or "PATCH_DECISION_EVIDENCE_INCOMPLETE")
        verification_reason_message = _verification_reason_message(first_required_issue)
    elif applicable is True:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code or "PATCH_APPLICABLE_VERIFIED"
        verification_reason_message = "patch was selected and passed git apply --check"
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
