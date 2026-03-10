from __future__ import annotations

import re
from typing import Any

_WS_RE = re.compile(r"\s+")


def _normalize_sql(text: str) -> str:
    return _WS_RE.sub(" ", str(text or "").strip()).lower()


def _extract_select_list(sql: str) -> str | None:
    match = re.search(r"^\s*select\s+(.*?)\s+from\s", sql, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _normalize_sql(match.group(1))


def _extract_where_clause(sql: str) -> str | None:
    match = re.search(
        r"\bwhere\b(.*?)(\border\s+by\b|\blimit\b|\boffset\b|\bfetch\b|$)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    where_text = _normalize_sql(match.group(1))
    return where_text or None


def _extract_order_by_clause(sql: str) -> str | None:
    match = re.search(
        r"\border\s+by\b(.*?)(\blimit\b|\boffset\b|\bfetch\b|$)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    order_text = _normalize_sql(match.group(1))
    return order_text or None


def _extract_pagination_clause(sql: str) -> str | None:
    clauses: list[str] = []
    limit_match = re.search(r"\blimit\b\s+([0-9?#{}:_\-]+)", sql, flags=re.IGNORECASE)
    if limit_match:
        clauses.append(f"limit {limit_match.group(1).lower()}")
    offset_match = re.search(r"\boffset\b\s+([0-9?#{}:_\-]+)", sql, flags=re.IGNORECASE)
    if offset_match:
        clauses.append(f"offset {offset_match.group(1).lower()}")
    fetch_match = re.search(
        r"\bfetch\s+first\s+([0-9?#{}:_\-]+)\s+rows?\s+only\b",
        sql,
        flags=re.IGNORECASE,
    )
    if fetch_match:
        clauses.append(f"fetch first {fetch_match.group(1).lower()} rows only")
    if not clauses:
        return None
    return " ".join(clauses)


def _build_check(
    *,
    status: str,
    reason_code: str | None = None,
    detail: str | None = None,
    before: str | None = None,
    after: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
    }
    if reason_code:
        payload["reasonCode"] = reason_code
    if detail:
        payload["detail"] = detail
    if before is not None or after is not None:
        payload["evidence"] = {"before": before, "after": after}
    return payload


def _infer_fingerprint_status(equivalence: dict[str, Any]) -> str:
    key_status = str(((equivalence.get("keySetHash") or {}).get("status") or "")).strip().upper()
    sample_status = str(((equivalence.get("rowSampleHash") or {}).get("status") or "")).strip().upper()
    if key_status == "MISMATCH":
        return "MISMATCH"
    if key_status == "MATCH":
        return "MATCH"
    if sample_status == "MISMATCH":
        return "MISMATCH_SAMPLE"
    if sample_status == "MATCH":
        return "SAMPLE_MATCH"
    if "ERROR" in {key_status, sample_status}:
        return "ERROR"
    if key_status:
        return key_status
    if sample_status:
        return sample_status
    return "SKIPPED"


def _confidence_rank(confidence: str) -> int:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return order.get(str(confidence or "").upper(), 0)


def _confidence_from_status_and_evidence_level(*, status: str, evidence_level: str) -> str:
    if status == "PASS":
        if evidence_level == "DB_COUNT":
            return "MEDIUM"
        return "LOW"
    if status == "FAIL":
        return "HIGH" if evidence_level == "DB_COUNT" else "MEDIUM"
    return "MEDIUM" if evidence_level == "DB_COUNT" else "LOW"


def _extract_fingerprint_strength(equivalence: dict[str, Any], fingerprint_status: str) -> str:
    strengths: list[str] = []
    for row in equivalence.get("evidenceRefObjects") or []:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip().upper()
        if source != "DB_FINGERPRINT":
            continue
        strength = str(row.get("match_strength") or "").strip().upper()
        if strength:
            strengths.append(strength)
    if "EXACT" in strengths:
        return "EXACT"
    if "PARTIAL" in strengths:
        return "PARTIAL"
    if fingerprint_status == "MATCH":
        return "EXACT"
    if fingerprint_status == "SAMPLE_MATCH":
        return "PARTIAL"
    return "NONE"


def _compare_text_clause(
    *,
    before: str | None,
    after: str | None,
    same_reason_code: str,
    change_reason_code: str,
    missing_reason_code: str,
    missing_detail: str,
    missing_status: str = "FAIL",
    changed_status: str = "UNCERTAIN",
) -> dict[str, Any]:
    if before is None and after is None:
        return _build_check(status="PASS", reason_code=same_reason_code, detail="clause absent in both sqls")
    if before is None or after is None:
        return _build_check(
            status=missing_status,
            reason_code=missing_reason_code,
            detail=missing_detail,
            before=before,
            after=after,
        )
    if before == after:
        return _build_check(status="PASS", reason_code=same_reason_code, detail="clause text matches", before=before, after=after)
    return _build_check(
        status=changed_status,
        reason_code=change_reason_code,
        detail="clause changed and requires manual review",
        before=before,
        after=after,
    )


def build_semantic_equivalence(
    *,
    original_sql: str,
    rewritten_sql: str,
    equivalence: dict[str, Any],
) -> dict[str, Any]:
    row_count = dict(equivalence.get("rowCount") or {})
    row_count_status = str(row_count.get("status") or "").upper()
    fingerprint_status = _infer_fingerprint_status(equivalence)
    key_set_status = str(((equivalence.get("keySetHash") or {}).get("status") or "")).strip().upper()
    row_sample_status = str(((equivalence.get("rowSampleHash") or {}).get("status") or "")).strip().upper()
    fingerprint_strength = _extract_fingerprint_strength(equivalence, fingerprint_status)
    checked = equivalence.get("checked")

    projection_before = _extract_select_list(original_sql)
    projection_after = _extract_select_list(rewritten_sql)
    if projection_before is None or projection_after is None:
        projection_check = _build_check(
            status="UNCERTAIN",
            reason_code="SEMANTIC_PROJECTION_PARSE_INCOMPLETE",
            detail="failed to parse select list from one or both sqls",
            before=projection_before,
            after=projection_after,
        )
    elif projection_before == projection_after:
        projection_check = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PROJECTION_STABLE",
            detail="projection list unchanged",
            before=projection_before,
            after=projection_after,
        )
    else:
        projection_check = _build_check(
            status="UNCERTAIN",
            reason_code="SEMANTIC_PROJECTION_CHANGED",
            detail="projection list changed and may affect result shape",
            before=projection_before,
            after=projection_after,
        )

    predicate_check = _compare_text_clause(
        before=_extract_where_clause(original_sql),
        after=_extract_where_clause(rewritten_sql),
        same_reason_code="SEMANTIC_PREDICATE_STABLE",
        change_reason_code="SEMANTIC_PREDICATE_CHANGED",
        missing_reason_code="SEMANTIC_PREDICATE_ADDED_OR_REMOVED",
        missing_detail="where clause added or removed",
    )
    ordering_check = _compare_text_clause(
        before=_extract_order_by_clause(original_sql),
        after=_extract_order_by_clause(rewritten_sql),
        same_reason_code="SEMANTIC_ORDERING_STABLE",
        change_reason_code="SEMANTIC_ORDERING_CHANGED",
        missing_reason_code="SEMANTIC_ORDERING_ADDED_OR_REMOVED",
        missing_detail="order by clause added or removed",
        missing_status="UNCERTAIN",
        changed_status="UNCERTAIN",
    )
    pagination_check = _compare_text_clause(
        before=_extract_pagination_clause(original_sql),
        after=_extract_pagination_clause(rewritten_sql),
        same_reason_code="SEMANTIC_PAGINATION_STABLE",
        change_reason_code="SEMANTIC_PAGINATION_CHANGED",
        missing_reason_code="SEMANTIC_PAGINATION_ADDED_OR_REMOVED",
        missing_detail="pagination clause added or removed",
    )

    checks = {
        "predicate": predicate_check,
        "projection": projection_check,
        "ordering": ordering_check,
        "pagination": pagination_check,
    }

    check_statuses = [str((check or {}).get("status") or "UNCERTAIN").upper() for check in checks.values()]
    reasons = [str((check or {}).get("reasonCode") or "").strip() for check in checks.values()]
    reasons = [code for code in reasons if code]
    hard_conflicts = [
        str((check or {}).get("reasonCode") or "").strip()
        for check in checks.values()
        if str((check or {}).get("status") or "").upper() == "FAIL" and str((check or {}).get("reasonCode") or "").strip()
    ]

    if row_count_status == "MISMATCH":
        status = "FAIL"
        reasons.append("SEMANTIC_ROW_COUNT_MISMATCH")
        hard_conflicts.append("SEMANTIC_ROW_COUNT_MISMATCH")
    elif row_count_status in {"ERROR"}:
        status = "UNCERTAIN"
        reasons.append("SEMANTIC_ROW_COUNT_ERROR")
    elif checked is False or row_count_status in {"", "SKIPPED"}:
        status = "UNCERTAIN"
        reasons.append("SEMANTIC_ROW_COUNT_UNVERIFIED")
    elif "FAIL" in check_statuses:
        status = "FAIL"
    elif "UNCERTAIN" in check_statuses:
        status = "UNCERTAIN"
    else:
        status = "PASS"

    if status == "PASS" and row_count_status != "MATCH":
        status = "UNCERTAIN"
        reasons.append("SEMANTIC_ROW_COUNT_NOT_MATCH_CONFIRMED")

    if fingerprint_status == "MISMATCH":
        status = "FAIL"
        reasons.append("SEMANTIC_FINGERPRINT_MISMATCH")
        hard_conflicts.append("SEMANTIC_FINGERPRINT_MISMATCH")
    elif fingerprint_status == "MISMATCH_SAMPLE":
        if status == "PASS":
            status = "UNCERTAIN"
        reasons.append("SEMANTIC_FINGERPRINT_SAMPLE_MISMATCH")
    elif fingerprint_status == "ERROR":
        if status == "PASS":
            status = "UNCERTAIN"
        reasons.append("SEMANTIC_FINGERPRINT_ERROR")

    if fingerprint_status in {"MATCH", "MISMATCH", "SAMPLE_MATCH", "MISMATCH_SAMPLE"}:
        evidence_level = "DB_FINGERPRINT"
    elif row_count_status in {"MATCH", "MISMATCH"}:
        evidence_level = "DB_COUNT"
    else:
        evidence_level = "STRUCTURE"
    base_evidence_level = "DB_COUNT" if row_count_status in {"MATCH", "MISMATCH"} else "STRUCTURE"
    confidence = _confidence_from_status_and_evidence_level(status=status, evidence_level=base_evidence_level)
    confidence_before_upgrade = confidence
    confidence_upgrade_applied = False
    confidence_upgrade_reasons: list[str] = []
    confidence_upgrade_sources: list[str] = []
    if not hard_conflicts:
        if fingerprint_strength == "EXACT":
            target = "HIGH" if status == "PASS" else "MEDIUM"
            if _confidence_rank(target) > _confidence_rank(confidence):
                confidence = target
                confidence_upgrade_applied = True
                confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_DB_FINGERPRINT_EXACT")
                confidence_upgrade_sources.append("DB_FINGERPRINT")
        elif fingerprint_strength == "PARTIAL":
            target = "MEDIUM"
            if _confidence_rank(target) > _confidence_rank(confidence):
                confidence = target
                confidence_upgrade_applied = True
                confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_DB_FINGERPRINT_PARTIAL")
                confidence_upgrade_sources.append("DB_FINGERPRINT")

    evidence = {
        "checked": checked,
        "rowCountStatus": row_count_status or None,
        "fingerprintStatus": fingerprint_status,
        "fingerprintStrength": fingerprint_strength,
        "method": equivalence.get("method"),
        "evidenceRefs": [str(ref) for ref in (equivalence.get("evidenceRefs") or []) if str(ref).strip()],
        "evidenceRefObjects": [row for row in (equivalence.get("evidenceRefObjects") or []) if isinstance(row, dict)],
        "dbFingerprint": {
            "keySetStatus": key_set_status or "SKIPPED",
            "rowSampleStatus": row_sample_status or "SKIPPED",
            "strength": fingerprint_strength,
        },
    }
    coverage = {
        "structure": {
            "executedChecks": sorted(checks.keys()),
            "failedChecks": sorted(
                name for name, check in checks.items() if str((check or {}).get("status") or "").upper() == "FAIL"
            ),
            "uncertainChecks": sorted(
                name for name, check in checks.items() if str((check or {}).get("status") or "").upper() == "UNCERTAIN"
            ),
        },
        "data": {
            "rowCount": row_count_status or "SKIPPED",
            "fingerprint": fingerprint_status,
        },
    }

    dedup_reasons: list[str] = []
    for code in reasons:
        if code not in dedup_reasons:
            dedup_reasons.append(code)
    dedup_hard_conflicts: list[str] = []
    for code in hard_conflicts:
        if code and code not in dedup_hard_conflicts:
            dedup_hard_conflicts.append(code)

    return {
        "status": status,
        "confidence": confidence,
        "confidenceBeforeUpgrade": confidence_before_upgrade,
        "confidenceUpgradeApplied": confidence_upgrade_applied,
        "confidenceUpgradeReasons": confidence_upgrade_reasons,
        "confidenceUpgradeEvidenceSources": confidence_upgrade_sources,
        "evidenceLevel": evidence_level,
        "checks": checks,
        "reasons": dedup_reasons,
        "hardConflicts": dedup_hard_conflicts,
        "coverage": coverage,
        "evidence": evidence,
    }
