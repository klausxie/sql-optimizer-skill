from __future__ import annotations

from typing import Any


def normalize_sqlunit(unit: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(unit)
    sql_key = str(normalized.get("sqlKey") or "").strip()
    statement_id = str(
        normalized.get("statementId")
        or (sql_key.rsplit(".", 1)[-1] if sql_key else "unknown")
    )
    normalized.setdefault("xmlPath", str(normalized.get("mapperPath") or ""))
    normalized.setdefault("namespace", str(normalized.get("namespace") or ""))
    normalized.setdefault("statementId", statement_id)
    normalized.setdefault(
        "statementType",
        "SELECT"
        if str(normalized.get("sql") or "").strip().lower().startswith("select")
        else "UNKNOWN",
    )
    normalized.setdefault("variantId", "v1")
    normalized.setdefault("parameterMappings", [])
    normalized.setdefault("paramExample", {})
    normalized.setdefault("locators", {})
    normalized.setdefault("riskFlags", [])
    if normalized.get("templateSql") is None and normalized.get("sql") is not None:
        normalized["templateSql"] = normalized["sql"]
    return normalized


def merge_validation_into_proposal(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    validation_result: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(proposal)
    original_sql = str(sql_unit.get("sql") or "")
    rewritten_sql = str(validation_result.get("rewrittenSql") or original_sql)
    merged["validated"] = str(validation_result.get("status") or "").upper() == "PASS"
    merged["validationStatus"] = validation_result.get("status")
    merged["originalSql"] = original_sql
    merged["optimizedSql"] = rewritten_sql
    merged["rewrittenSql"] = rewritten_sql
    for key in (
        "selectedCandidateId",
        "candidateEvaluations",
        "selectionReason",
        "selectionRationale",
        "deliveryReadiness",
        "decisionLayers",
        "semanticEquivalence",
        "patchability",
        "selectedPatchStrategy",
        "rewriteMaterialization",
        "templateRewriteOps",
        "rewriteFacts",
        "patchStrategyCandidates",
        "canonicalizationAssessment",
        "candidateSelectionTrace",
        "dynamicTemplate",
        "warnings",
        "riskFlags",
    ):
        if key in validation_result:
            merged[key] = validation_result[key]
    merged["validationResult"] = {
        "status": validation_result.get("status"),
        "warnings": validation_result.get("warnings") or [],
        "riskFlags": validation_result.get("riskFlags") or [],
        "securityChecks": validation_result.get("securityChecks") or {},
        "equivalence": validation_result.get("equivalence") or {},
        "perfComparison": validation_result.get("perfComparison") or {},
    }
    return merged
