from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, read_jsonl
from ..manifest import log_event
from ..platforms.sql.validator_sql import validate_proposal
from ..run_paths import canonical_paths
from ..utils import statement_key
from ..verification.models import VerificationCheck, VerificationRecord
from ..verification.writer import append_verification_record

def execute_one(sql_unit: dict, proposal: dict, run_dir: Path, validator: ContractValidator, db_reachable: bool, config: dict) -> dict:
    paths = canonical_paths(run_dir)
    evidence_dir = paths.sql_evidence_dir(sql_unit["sqlKey"])
    fragments_path = paths.scan_fragments_path
    fragment_rows = read_jsonl(fragments_path) if fragments_path.exists() else []
    fragment_catalog = {str(row.get("fragmentKey") or ""): row for row in fragment_rows if str(row.get("fragmentKey") or "").strip()}
    result = validate_proposal(
        sql_unit,
        proposal,
        db_reachable=db_reachable,
        config=config,
        evidence_dir=evidence_dir,
        fragment_catalog=fragment_catalog,
    )
    payload = result.to_contract()
    validator.validate("acceptance_result", payload)
    acceptance_path = paths.acceptance_path
    append_jsonl(acceptance_path, payload)
    sql_key = str(payload.get("sqlKey") or sql_unit["sqlKey"])
    perf = dict(payload.get("perfComparison") or {})
    equivalence = dict(payload.get("equivalence") or {})
    semantic_equivalence = dict(payload.get("semanticEquivalence") or {})
    semantic_gate_status = str(semantic_equivalence.get("status") or "PASS").upper()
    semantic_gate_confidence = str(semantic_equivalence.get("confidence") or "HIGH").upper()
    reason_codes = [str(code) for code in (perf.get("reasonCodes") or []) if str(code).strip()]
    template_ops = [row for row in (payload.get("templateRewriteOps") or []) if isinstance(row, dict)]
    rewrite_materialization = dict(payload.get("rewriteMaterialization") or {})
    replay_verified = rewrite_materialization.get("replayVerified")
    selected_source = str(payload.get("selectedCandidateSource") or "").strip()
    selected_id = str(payload.get("selectedCandidateId") or "").strip()
    decision_layers = dict(payload.get("decisionLayers") or {})
    pass_has_selection = payload.get("status") != "PASS" or (bool(selected_source) and bool(selected_id))
    checks = [
        VerificationCheck(
            "equivalence_checked",
            bool(equivalence.get("checked")),
            "warn",
            None if equivalence.get("checked") else "VALIDATE_EQUIVALENCE_NOT_CHECKED",
        ),
        VerificationCheck(
            "semantic_gate_passed",
            semantic_gate_status == "PASS",
            "warn" if payload.get("status") == "PASS" else "info",
            None if semantic_gate_status == "PASS" else "VALIDATE_SEMANTIC_GATE_NOT_PASS",
        ),
        VerificationCheck(
            "semantic_confidence_sufficient",
            semantic_gate_confidence in {"MEDIUM", "HIGH"},
            "warn" if payload.get("status") == "PASS" else "info",
            None if semantic_gate_confidence in {"MEDIUM", "HIGH"} else "VALIDATE_SEMANTIC_CONFIDENCE_LOW",
        ),
        VerificationCheck(
            "perf_checked_or_explained",
            bool(perf.get("checked")) or bool(reason_codes),
            "warn",
            None if bool(perf.get("checked")) or bool(reason_codes) else "VALIDATE_PERF_NOT_CHECKED",
        ),
        VerificationCheck(
            "pass_selection_complete",
            pass_has_selection,
            "error" if payload.get("status") == "PASS" else "info",
            None if pass_has_selection else "VALIDATE_PASS_SELECTION_INCOMPLETE",
        ),
        VerificationCheck(
            "template_replay_verified",
            (not template_ops) or replay_verified is True,
            "error" if template_ops else "info",
            None if (not template_ops) or replay_verified is True else "VALIDATE_TEMPLATE_REPLAY_MISSING",
        ),
        VerificationCheck(
            "security_checks_present",
            bool(payload.get("securityChecks")),
            "warn",
            None if payload.get("securityChecks") else "VALIDATE_SECURITY_EVIDENCE_MISSING",
        ),
    ]
    if template_ops and replay_verified is not True:
        verification_status = "UNVERIFIED"
        verification_reason_code = "VALIDATE_TEMPLATE_REPLAY_MISSING"
        verification_reason_message = "template rewrite ops were emitted without replayVerified=true"
    elif not pass_has_selection:
        verification_status = "UNVERIFIED"
        verification_reason_code = "VALIDATE_PASS_SELECTION_INCOMPLETE"
        verification_reason_message = "PASS result is missing selected candidate source or id"
    elif (not db_reachable) and ("VALIDATE_DB_UNREACHABLE" in reason_codes):
        verification_status = "PARTIAL"
        verification_reason_code = "VALIDATE_DB_UNREACHABLE"
        verification_reason_message = "validate relied on a degraded DB-unreachable fallback path"
    elif semantic_gate_status != "PASS":
        verification_status = "PARTIAL"
        verification_reason_code = "VALIDATE_SEMANTIC_GATE_NOT_PASS"
        verification_reason_message = "semantic gate is not PASS and requires manual confirmation before delivery"
    elif semantic_gate_confidence not in {"MEDIUM", "HIGH"}:
        verification_status = "PARTIAL"
        verification_reason_code = "VALIDATE_SEMANTIC_CONFIDENCE_LOW"
        verification_reason_message = "semantic gate confidence is LOW and requires stronger evidence before delivery"
    elif not equivalence.get("checked") or (not perf.get("checked") and not reason_codes):
        verification_status = "PARTIAL"
        verification_reason_code = "VALIDATE_CHECKS_PARTIAL"
        verification_reason_message = "one or more validate checks were skipped or incompletely recorded"
    else:
        verification_status = "VERIFIED"
        verification_reason_code = "VALIDATE_EVIDENCE_VERIFIED"
        verification_reason_message = "validate result includes its acceptance and safety evidence"
    evidence_refs = [str(acceptance_path)]
    if evidence_dir.exists():
        evidence_refs.append(str(evidence_dir))
    append_verification_record(
        run_dir,
        validator,
        VerificationRecord(
            run_id=run_dir.name,
            sql_key=sql_key,
            statement_key=statement_key(sql_key),
            phase="validate",
            status=verification_status,
            reason_code=verification_reason_code,
            reason_message=verification_reason_message,
            evidence_refs=evidence_refs,
            inputs={
                "acceptance_status": payload.get("status"),
                "db_reachable": db_reachable,
                "selected_candidate_source": selected_source or None,
                "selected_candidate_id": selected_id or None,
                "selection_strategy": ((payload.get("selectionRationale") or {}).get("strategy")),
                "delivery_readiness_tier": ((payload.get("deliveryReadiness") or {}).get("tier")),
                "evidence_degraded": ((decision_layers.get("evidence") or {}).get("degraded")),
                "acceptance_profile": ((decision_layers.get("acceptance") or {}).get("validationProfile")),
                "template_op_count": len(template_ops),
                "perf_reason_codes": reason_codes,
                "semantic_gate_status": semantic_gate_status,
                "semantic_gate_confidence": semantic_gate_confidence,
            },
            checks=checks,
            verdict={
                "status": payload.get("status"),
                "semantic_risk": payload.get("semanticRisk"),
                "semantic_gate_status": semantic_gate_status,
                "semantic_gate_confidence": semantic_gate_confidence,
                "replay_verified": replay_verified,
                "selection_strategy": ((payload.get("selectionRationale") or {}).get("strategy")),
                "delivery_tier": ((decision_layers.get("delivery") or {}).get("tier")),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    log_event(
        paths.manifest_path,
        "validate",
        "done",
        {"statement_key": sql_unit["sqlKey"], "status": result.status},
    )
    return payload
