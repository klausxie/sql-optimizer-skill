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
    template_ops = [
        row
        for row in (acceptance.get("templateRewriteOps") or [])
        if isinstance(row, dict)
    ]
    replay_verified = (acceptance.get("rewriteMaterialization") or {}).get(
        "replayVerified"
    )
    applicable = patch.get("applicable")
    selection_code = str(selection_reason.get("code") or "").strip()
    pass_has_clear_winner = status != "PASS" or (
        len(pass_rows) == 1 and str(pass_rows[0].get("sqlKey") or "") == sql_key
    )
    checks = [
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
            None
            if semantic_gate_status == "PASS"
            else "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
        ),
        VerificationCheck(
            "semantic_confidence_sufficient",
            semantic_gate_confidence in {"MEDIUM", "HIGH"},
            "warn" if status == "PASS" else "info",
            None
            if semantic_gate_confidence in {"MEDIUM", "HIGH"}
            else "PATCH_SEMANTIC_CONFIDENCE_LOW",
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
            None
            if (not template_ops) or replay_verified is True
            else "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED",
        ),
        VerificationCheck(
            "patch_applicability_recorded",
            (applicable is True) or (applicable is False) or bool(selection_code),
            "warn",
            None
            if (applicable is True) or (applicable is False) or bool(selection_code)
            else "PATCH_APPLICABILITY_UNKNOWN",
        ),
    ]
    if template_ops and replay_verified is not True:
        verification_status = "UNVERIFIED"
        verification_reason_code = "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED"
        verification_reason_message = (
            "template patch path was considered without replay verification"
        )
    elif selection_code == "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS":
        verification_status = "VERIFIED"
        verification_reason_code = "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS"
        verification_reason_message = (
            "patch generation was intentionally blocked by semantic equivalence gate"
        )
    elif selection_code == "PATCH_SEMANTIC_CONFIDENCE_LOW":
        verification_status = "VERIFIED"
        verification_reason_code = "PATCH_SEMANTIC_CONFIDENCE_LOW"
        verification_reason_message = (
            "patch generation was intentionally blocked due to low semantic confidence"
        )
    elif applicable is True:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code or "PATCH_APPLICABLE_VERIFIED"
        verification_reason_message = "patch was selected and passed git apply --check"
    elif applicable is False:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code or "PATCH_NOT_APPLICABLE"
        verification_reason_message = (
            "patch was rejected with an explicit apply-check failure"
        )
    elif selection_code:
        verification_status = "VERIFIED"
        verification_reason_code = selection_code
        verification_reason_message = str(
            selection_reason.get("message") or "patch was skipped for an explicit rule"
        )
    else:
        verification_status = "PARTIAL"
        verification_reason_code = "PATCH_DECISION_EVIDENCE_INCOMPLETE"
        verification_reason_message = (
            "patch result exists but its selection evidence is incomplete"
        )

    append_verification_record(
        run_dir,
        validator,
        VerificationRecord(
            run_id=run_dir.name,
            sql_key=sql_key,
            statement_key=statement_key,
            phase="apply",
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
                "replay_verified": replay_verified,
                "semantic_gate_status": semantic_gate_status,
                "semantic_gate_confidence": semantic_gate_confidence,
            },
            checks=checks,
            verdict={
                "selection_code": selection_code or None,
                "applicable": applicable,
                "patch_file_count": len(patch.get("patchFiles") or []),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
