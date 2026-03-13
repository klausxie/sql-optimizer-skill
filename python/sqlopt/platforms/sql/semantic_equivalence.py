from __future__ import annotations

import re
from typing import Any

from .canonicalization_support import (
    SELECT_DIRECT_RE,
    cleanup_redundant_select_aliases,
    cleanup_single_table_alias_references,
    split_select_list,
    strip_redundant_projection_alias,
    strip_sql_comments,
)
from .aggregation_analysis import analyze_aggregation_query
from .cte_analysis import analyze_simple_inline_cte
from .dynamic_template_support import parse_select_wrapper_template, render_flattened_select_template

_WS_RE = re.compile(r"\s+")
_COUNT_SUBQUERY_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+from\s*\(\s*(?P<inner>.+)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_SELECT_FROM_RE = re.compile(r"^\s*select\s+.+?\s+(?P<from_suffix>from\b.+)$", flags=re.IGNORECASE | re.DOTALL)
_COUNT_DIRECT_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+(?P<from_suffix>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_UPDATE_RE = re.compile(
    r"^\s*update\s+(?P<table>[a-z_][a-z0-9_\.]*)\s+set\s+(?P<set_clause>.+?)(?:\s+where\s+(?P<where_clause>.+))?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_COUNT_WRAPPER_BLOCKERS = (
    r"\bdistinct\b",
    r"\bgroup\s+by\b",
    r"\bhaving\b",
    r"\bunion\b",
    r"\bover\s*\(",
    r"\blimit\b",
    r"\boffset\b",
    r"\bfetch\b",
)


def _normalize_sql(text: str) -> str:
    return _WS_RE.sub(" ", strip_sql_comments(str(text or "")).strip()).lower()


def _extract_select_list(sql: str) -> str | None:
    match = re.search(r"^\s*select\s+(.*?)\s+from\s", sql, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _normalize_sql(match.group(1))


def _projection_signature(select_list: str | None) -> tuple[str, ...] | None:
    if select_list is None:
        return None
    cleaned_select_list, _ = cleanup_redundant_select_aliases(select_list)
    parts = split_select_list(cleaned_select_list)
    return tuple(_normalize_sql(strip_redundant_projection_alias(part)) for part in parts)


def _extract_select_from_suffix(sql: str) -> str | None:
    match = _SELECT_FROM_RE.search(str(sql or "").strip())
    if not match:
        return None
    return _normalize_sql(match.group("from_suffix"))


def _inline_simple_count_wrapper(sql: str) -> str | None:
    normalized = str(sql or "").strip()
    match = _COUNT_SUBQUERY_RE.match(normalized)
    if not match:
        return None
    inner_sql = str(match.group("inner") or "").strip()
    if not inner_sql:
        return None
    inner_normalized = _normalize_sql(inner_sql)
    if any(re.search(pattern, inner_normalized, flags=re.IGNORECASE) for pattern in _COUNT_WRAPPER_BLOCKERS):
        return None
    from_suffix = _extract_select_from_suffix(inner_sql)
    count_match = _COUNT_DIRECT_RE.match(normalized)
    count_expr = _normalize_sql((count_match.group("count_expr") if count_match else "") or "")
    if not from_suffix or count_expr not in {"1", "*"}:
        return None
    return f"select count(*) {from_suffix}"


def _inline_simple_select_wrapper(sql: str) -> str | None:
    outer_select, inner_select, flattened_from = parse_select_wrapper_template(sql)
    if outer_select is None or inner_select is None or flattened_from is None:
        return None
    if _normalize_sql(outer_select) != _normalize_sql(inner_select):
        return None
    return render_flattened_select_template(inner_select, flattened_from)


def _normalize_groupby_from_alias_cleanup(sql: str) -> str | None:
    direct_match = SELECT_DIRECT_RE.match(str(sql or "").strip())
    if direct_match is None:
        return None
    select_text = str(direct_match.group("select") or "").strip()
    from_suffix = str(direct_match.group("from") or "").strip()
    if not re.search(r"\bgroup\s+by\b", from_suffix, flags=re.IGNORECASE):
        return None
    cleaned_select, cleaned_from, changed = cleanup_single_table_alias_references(select_text, from_suffix)
    if not changed:
        return None
    cleaned_select, _ = cleanup_redundant_select_aliases(cleaned_select)
    return f"SELECT {cleaned_select} {cleaned_from}"


def _semantic_subject_sql(sql: str) -> str:
    normalized = strip_sql_comments(str(sql or "")).strip()
    collapsed_count = _inline_simple_count_wrapper(normalized)
    if collapsed_count:
        return collapsed_count
    groupby_alias_cleanup = _normalize_groupby_from_alias_cleanup(normalized)
    if groupby_alias_cleanup:
        return groupby_alias_cleanup
    collapsed_wrapper = _inline_simple_select_wrapper(normalized)
    if collapsed_wrapper:
        return collapsed_wrapper
    cte_analysis = analyze_simple_inline_cte(normalized)
    if cte_analysis.collapsible and cte_analysis.inlined_sql:
        return cte_analysis.inlined_sql
    return normalized


def _normalize_projection_alias(expr: str) -> str:
    value = str(expr or "").strip().lower()
    # Remove trailing alias styles: "count(*) as c" / "count(*) c"
    value = re.sub(r"\s+as\s+[a-z_][a-z0-9_]*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+[a-z_][a-z0-9_]*$", "", value, flags=re.IGNORECASE)
    return _normalize_sql(value)


def _is_count_star_one_equivalent(before: str | None, after: str | None) -> bool:
    if before is None or after is None:
        return False
    normalized_before = _normalize_projection_alias(before)
    normalized_after = _normalize_projection_alias(after)
    pair = {normalized_before, normalized_after}
    return pair == {"count(1)", "count(*)"}


def _is_projection_alias_only_equivalent(before: str | None, after: str | None) -> bool:
    before_signature = _projection_signature(before)
    after_signature = _projection_signature(after)
    return before_signature is not None and before_signature == after_signature


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


def _extract_update_parts(sql: str) -> tuple[str | None, str | None, str | None]:
    match = _UPDATE_RE.match(str(sql or "").strip())
    if not match:
        return None, None, None
    table = _normalize_sql(match.group("table") or "")
    set_clause = _normalize_sql(match.group("set_clause") or "")
    where_clause = _normalize_sql(match.group("where_clause") or "") or None
    return table or None, set_clause or None, where_clause


def _is_update_statement(sql: str) -> bool:
    return _UPDATE_RE.match(str(sql or "").strip()) is not None


def _build_dml_checks(original_sql: str, rewritten_sql: str) -> dict[str, Any] | None:
    before_table, before_set, before_where = _extract_update_parts(original_sql)
    after_table, after_set, after_where = _extract_update_parts(rewritten_sql)
    if before_table is None or after_table is None:
        return None

    if before_table == after_table:
        projection_check = _build_check(
            status="PASS",
            reason_code="SEMANTIC_DML_TARGET_STABLE",
            detail="update target table unchanged",
            before=before_table,
            after=after_table,
        )
    else:
        projection_check = _build_check(
            status="FAIL",
            reason_code="SEMANTIC_DML_TARGET_CHANGED",
            detail="update target table changed",
            before=before_table,
            after=after_table,
        )

    if before_set is None or after_set is None:
        set_check = _build_check(
            status="UNCERTAIN",
            reason_code="SEMANTIC_DML_SET_PARSE_INCOMPLETE",
            detail="failed to parse update set clause from one or both sqls",
            before=before_set,
            after=after_set,
        )
    elif before_set == after_set:
        set_check = _build_check(
            status="PASS",
            reason_code="SEMANTIC_DML_SET_STABLE",
            detail="update set clause unchanged",
            before=before_set,
            after=after_set,
        )
    else:
        set_check = _build_check(
            status="UNCERTAIN",
            reason_code="SEMANTIC_DML_SET_CHANGED",
            detail="update set clause changed and requires manual review",
            before=before_set,
            after=after_set,
        )

    predicate_check = _compare_text_clause(
        before=before_where,
        after=after_where,
        same_reason_code="SEMANTIC_PREDICATE_STABLE",
        change_reason_code="SEMANTIC_PREDICATE_CHANGED",
        missing_reason_code="SEMANTIC_PREDICATE_ADDED_OR_REMOVED",
        missing_detail="where clause added or removed",
    )
    return {
        "predicate": predicate_check,
        "projection": projection_check,
        "ordering": _build_check(status="PASS", reason_code="SEMANTIC_ORDERING_STABLE", detail="clause absent in both sqls"),
        "pagination": _build_check(status="PASS", reason_code="SEMANTIC_PAGINATION_STABLE", detail="clause absent in both sqls"),
        "dmlSet": set_check,
    }


def _is_safe_aggregation_wrapper_equivalent(original_sql: str, rewritten_sql: str) -> str | None:
    analysis = analyze_aggregation_query(original_sql, rewritten_sql)
    family = str((analysis.capability_profile or {}).get("safeBaselineFamily") or "").strip().upper()
    if family == "REDUNDANT_GROUP_BY_WRAPPER":
        return "SEMANTIC_SAFE_BASELINE_REDUNDANT_GROUP_BY_WRAPPER"
    if family == "REDUNDANT_HAVING_WRAPPER":
        return "SEMANTIC_SAFE_BASELINE_REDUNDANT_HAVING_WRAPPER"
    if family == "GROUP_BY_FROM_ALIAS_CLEANUP":
        return "SEMANTIC_SAFE_BASELINE_GROUP_BY_FROM_ALIAS_CLEANUP"
    if family == "GROUP_BY_HAVING_FROM_ALIAS_CLEANUP":
        return "SEMANTIC_SAFE_BASELINE_GROUP_BY_HAVING_FROM_ALIAS_CLEANUP"
    return None


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
    original_subject_sql = _semantic_subject_sql(original_sql)
    rewritten_subject_sql = _semantic_subject_sql(rewritten_sql)
    row_count = dict(equivalence.get("rowCount") or {})
    row_count_status = str(row_count.get("status") or "").upper()
    fingerprint_status = _infer_fingerprint_status(equivalence)
    key_set_status = str(((equivalence.get("keySetHash") or {}).get("status") or "")).strip().upper()
    row_sample_status = str(((equivalence.get("rowSampleHash") or {}).get("status") or "")).strip().upper()
    fingerprint_strength = _extract_fingerprint_strength(equivalence, fingerprint_status)
    checked = equivalence.get("checked")
    is_dml_comparison = _is_update_statement(original_subject_sql) and _is_update_statement(rewritten_subject_sql)

    projection_before = _extract_select_list(original_subject_sql)
    projection_after = _extract_select_list(rewritten_subject_sql)
    count_projection_equivalent = _is_count_star_one_equivalent(projection_before, projection_after)
    alias_only_projection_equivalent = _is_projection_alias_only_equivalent(projection_before, projection_after)
    if is_dml_comparison:
        checks = _build_dml_checks(original_subject_sql, rewritten_subject_sql) or {}
        projection_check = dict(checks.get("projection") or {})
    else:
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
        elif alias_only_projection_equivalent:
            projection_check = _build_check(
                status="PASS",
                reason_code="SEMANTIC_PROJECTION_ALIAS_ONLY_EQUIVALENT",
                detail="projection change only removes redundant aliases",
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
            before=_extract_where_clause(original_subject_sql),
            after=_extract_where_clause(rewritten_subject_sql),
            same_reason_code="SEMANTIC_PREDICATE_STABLE",
            change_reason_code="SEMANTIC_PREDICATE_CHANGED",
            missing_reason_code="SEMANTIC_PREDICATE_ADDED_OR_REMOVED",
            missing_detail="where clause added or removed",
        )
        ordering_check = _compare_text_clause(
            before=_extract_order_by_clause(original_subject_sql),
            after=_extract_order_by_clause(rewritten_subject_sql),
            same_reason_code="SEMANTIC_ORDERING_STABLE",
            change_reason_code="SEMANTIC_ORDERING_CHANGED",
            missing_reason_code="SEMANTIC_ORDERING_ADDED_OR_REMOVED",
            missing_detail="order by clause added or removed",
            missing_status="UNCERTAIN",
            changed_status="UNCERTAIN",
        )
        pagination_check = _compare_text_clause(
            before=_extract_pagination_clause(original_subject_sql),
            after=_extract_pagination_clause(rewritten_subject_sql),
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

    equivalence_override_applied = False
    equivalence_override_rule: str | None = None
    dml_noop_override_applied = False
    only_projection_uncertain = (
        str(projection_check.get("status") or "").upper() == "UNCERTAIN"
        and all(
            str((check or {}).get("status") or "").upper() == "PASS"
            for name, check in checks.items()
            if name != "projection"
        )
    )
    if (
        status == "UNCERTAIN"
        and count_projection_equivalent
        and only_projection_uncertain
        and row_count_status == "MATCH"
        and fingerprint_strength == "EXACT"
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = "SEMANTIC_KNOWN_EQUIVALENCE_COUNT_STAR_ONE"
        status = "PASS"
        checks["projection"] = _build_check(
            status="PASS",
            reason_code="SEMANTIC_PROJECTION_COUNT_EQUIVALENT",
            detail="count(1) and count(*) are treated as equivalent with exact DB fingerprint evidence",
            before=projection_before,
            after=projection_after,
        )
        reasons = [code for code in reasons if code != "SEMANTIC_PROJECTION_CHANGED"]
        reasons.append(equivalence_override_rule)

    if (
        status == "UNCERTAIN"
        and is_dml_comparison
        and _normalize_sql(original_subject_sql) == _normalize_sql(rewritten_subject_sql)
        and all(str((check or {}).get("status") or "").upper() == "PASS" for check in checks.values())
        and row_count_status in {"", "SKIPPED", "ERROR"}
        and not hard_conflicts
    ):
        dml_noop_override_applied = True
        status = "PASS"
        reasons = [code for code in reasons if code not in {"SEMANTIC_ROW_COUNT_ERROR", "SEMANTIC_ROW_COUNT_UNVERIFIED"}]
        reasons.append("SEMANTIC_DML_NOOP_STABLE")

    safe_aggregation_wrapper_rule = _is_safe_aggregation_wrapper_equivalent(
        strip_sql_comments(original_sql),
        strip_sql_comments(rewritten_sql),
    )
    if (
        status == "UNCERTAIN"
        and safe_aggregation_wrapper_rule
        and all(str((check or {}).get("status") or "").upper() == "PASS" for check in checks.values())
        and row_count_status in {"", "SKIPPED", "ERROR"}
        and not hard_conflicts
    ):
        equivalence_override_applied = True
        equivalence_override_rule = safe_aggregation_wrapper_rule
        status = "PASS"
        reasons = [code for code in reasons if code not in {"SEMANTIC_ROW_COUNT_ERROR", "SEMANTIC_ROW_COUNT_UNVERIFIED"}]
        reasons.append(safe_aggregation_wrapper_rule)

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
    if dml_noop_override_applied and _confidence_rank("MEDIUM") > _confidence_rank(confidence):
        confidence = "MEDIUM"
        confidence_upgrade_applied = True
        confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_DML_NOOP_STABLE")
        confidence_upgrade_sources.append("STRUCTURE")
    if safe_aggregation_wrapper_rule and status == "PASS" and _confidence_rank("MEDIUM") > _confidence_rank(confidence):
        confidence = "MEDIUM"
        confidence_upgrade_applied = True
        confidence_upgrade_reasons.append("SEMANTIC_CONFIDENCE_UPGRADE_AGGREGATION_SAFE_BASELINE")
        confidence_upgrade_sources.append("STRUCTURE")

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
        "equivalenceOverrideApplied": equivalence_override_applied,
        "equivalenceOverrideRule": equivalence_override_rule,
        "evidenceLevel": evidence_level,
        "checks": checks,
        "reasons": dedup_reasons,
        "hardConflicts": dedup_hard_conflicts,
        "coverage": coverage,
        "evidence": evidence,
    }
