from __future__ import annotations

from pathlib import Path
from typing import Any

from ..failure_classification import classify_reason_code
from ..io_utils import read_json
from .report_models import FailureRecord, ManifestEvent


def count_llm_timeouts(run_dir: Path, proposals: list[dict[str, Any]]) -> int:
    count = 0
    for proposal in proposals:
        for ref in proposal.get("llmTraceRefs") or []:
            trace_path = run_dir / ref
            if not trace_path.exists():
                continue
            row = read_json(trace_path)
            if row.get("degrade_reason") == "RUN_TIME_BUDGET_EXHAUSTED":
                count += 1
            if row.get("response", {}).get("error_type") == "TimeoutError":
                count += 1
    return count


def build_failures(
    acceptance: list[dict[str, Any]],
    manifest_rows: list[ManifestEvent],
) -> list[FailureRecord]:
    failures: list[FailureRecord] = []
    for row in acceptance:
        if row.get("status") == "PASS":
            gate = row.get("semanticEquivalence")
            if isinstance(gate, dict):
                gate_status = str(gate.get("status") or "").strip().upper()
                gate_confidence = str(gate.get("confidence") or "").strip().upper()
                if gate_status in {"FAIL", "UNCERTAIN"}:
                    reason_code = "VALIDATE_SEMANTIC_GATE_NOT_PASS"
                    failures.append(
                        FailureRecord(
                            sql_key=row.get("sqlKey"),
                            reason_code=reason_code,
                            status=gate_status,
                            classification=classify_reason_code(reason_code, phase="validate"),
                            phase="validate",
                        )
                    )
                elif gate_confidence == "LOW":
                    reason_code = "VALIDATE_SEMANTIC_CONFIDENCE_LOW"
                    failures.append(
                        FailureRecord(
                            sql_key=row.get("sqlKey"),
                            reason_code=reason_code,
                            status=gate_status or "PASS",
                            classification=classify_reason_code(reason_code, phase="validate"),
                            phase="validate",
                        )
                    )
            continue
        code = None
        feedback = row.get("feedback")
        if isinstance(feedback, dict):
            code = feedback.get("reason_code")
        reason_code = str(code or "VALIDATE_PARAM_INSUFFICIENT")
        failures.append(
            FailureRecord(
                sql_key=row.get("sqlKey"),
                reason_code=reason_code,
                status=str(row.get("status") or "UNKNOWN"),
                classification=classify_reason_code(reason_code, phase="validate"),
                phase="validate",
            )
        )
    for row in manifest_rows:
        if row.event != "failed":
            continue
        payload = row.payload
        reason_code = str(payload.get("reason_code") or "RUNTIME_RETRY_EXHAUSTED")
        stage = row.stage
        failures.append(
            FailureRecord(
                sql_key=payload.get("statement_key"),
                reason_code=reason_code,
                classification=classify_reason_code(reason_code, phase=stage),
                status="FAILED",
                phase=stage,
            )
        )
    return failures


def summarize_failures(failures: list[FailureRecord]) -> tuple[dict[str, int], dict[str, dict[str, int]], dict[str, int]]:
    reason_counts: dict[str, int] = {}
    phase_reason_counts: dict[str, dict[str, int]] = {}
    class_counts = {"fatal": 0, "retryable": 0, "degradable": 0}
    for row in failures:
        code = row.reason_code or "UNKNOWN"
        reason_counts[code] = reason_counts.get(code, 0) + 1
        phase = str(row.phase or "unknown")
        phase_bucket = phase_reason_counts.setdefault(phase, {})
        phase_bucket[code] = phase_bucket.get(code, 0) + 1
        cls = row.classification or "fatal"
        class_counts[cls] = class_counts.get(cls, 0) + 1
    return reason_counts, phase_reason_counts, class_counts


def summarize_semantic_gates(acceptance_rows: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    counts = {
        "pass": 0,
        "fail": 0,
        "uncertain": 0,
    }
    reason_counts: dict[str, int] = {}

    for row in acceptance_rows:
        gate = row.get("semanticEquivalence")
        if not isinstance(gate, dict):
            counts["pass"] += 1
            continue

        status = str(gate.get("status") or "").strip().upper()
        if status == "FAIL":
            counts["fail"] += 1
        elif status == "UNCERTAIN":
            counts["uncertain"] += 1
        else:
            counts["pass"] += 1

        for reason_code in gate.get("reasons") or []:
            code = str(reason_code or "").strip()
            if not code:
                continue
            reason_counts[code] = reason_counts.get(code, 0) + 1

    return counts, reason_counts


def summarize_semantic_gate_quality(acceptance_rows: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    confidence_distribution: dict[str, int] = {}
    evidence_level_distribution: dict[str, int] = {}
    hard_conflict_counts: dict[str, int] = {}

    for row in acceptance_rows:
        gate = row.get("semanticEquivalence")
        if not isinstance(gate, dict):
            confidence_distribution["UNKNOWN"] = confidence_distribution.get("UNKNOWN", 0) + 1
            evidence_level_distribution["UNKNOWN"] = evidence_level_distribution.get("UNKNOWN", 0) + 1
            continue

        confidence = str(gate.get("confidence") or "UNKNOWN").strip().upper()
        evidence_level = str(gate.get("evidenceLevel") or "UNKNOWN").strip().upper()
        confidence_distribution[confidence] = confidence_distribution.get(confidence, 0) + 1
        evidence_level_distribution[evidence_level] = evidence_level_distribution.get(evidence_level, 0) + 1

        for code in gate.get("hardConflicts") or []:
            reason_code = str(code or "").strip()
            if not reason_code:
                continue
            hard_conflict_counts[reason_code] = hard_conflict_counts.get(reason_code, 0) + 1

    return confidence_distribution, evidence_level_distribution, hard_conflict_counts


def summarize_semantic_confidence_upgrades(acceptance_rows: list[dict[str, Any]]) -> tuple[int, dict[str, int]]:
    upgraded_count = 0
    source_counts: dict[str, int] = {}
    for row in acceptance_rows:
        gate = row.get("semanticEquivalence")
        if not isinstance(gate, dict):
            continue
        if not bool(gate.get("confidenceUpgradeApplied")):
            continue
        upgraded_count += 1
        raw_sources = gate.get("confidenceUpgradeEvidenceSources") or []
        sources = [
            str(src or "").strip().upper()
            for src in raw_sources
            if str(src or "").strip()
        ]
        if not sources:
            # Backward-compatible inference when source list is not present.
            for reason in gate.get("confidenceUpgradeReasons") or []:
                text = str(reason or "").strip().upper()
                if "DB_FINGERPRINT" in text:
                    sources.append("DB_FINGERPRINT")
                    break
        if not sources:
            sources.append("UNKNOWN")
        seen: set[str] = set()
        for source in sources:
            if source in seen:
                continue
            seen.add(source)
            source_counts[source] = source_counts.get(source, 0) + 1
    return upgraded_count, source_counts


def build_verification_gate(
    acceptance_rows: list[dict[str, Any]],
    patch_rows: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
) -> tuple[list[str], str, dict[str, Any]]:
    unverified_validate_sql = {
        str(row.get("sql_key") or "")
        for row in verification_rows
        if str(row.get("phase") or "") == "validate" and str(row.get("status") or "").upper() == "UNVERIFIED"
    }
    unverified_patch_sql = {
        str(row.get("sql_key") or "")
        for row in verification_rows
        if str(row.get("phase") or "") == "patch_generate" and str(row.get("status") or "").upper() == "UNVERIFIED"
    }
    pass_sql = {str(row.get("sqlKey") or "") for row in acceptance_rows if str(row.get("status") or "") == "PASS"}
    applicable_patch_sql = {
        str(row.get("sqlKey") or "")
        for row in patch_rows
        if row.get("applicable") is True and str(row.get("sqlKey") or "").strip()
    }

    unverified_pass_sql = sorted(sql_key for sql_key in (pass_sql & unverified_validate_sql) if sql_key)
    unverified_applicable_patch_sql = sorted(sql_key for sql_key in (applicable_patch_sql & unverified_patch_sql) if sql_key)
    optimize_explain_syntax_sql = {
        str(row.get("sql_key") or "")
        for row in verification_rows
        if (
            str(row.get("reason_code") or "") == "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR"
            or any(
                isinstance(check, dict)
                and not bool(check.get("ok"))
                and str(check.get("reason_code") or "") == "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR"
                for check in (row.get("checks") or [])
            )
        )
    }
    optimize_explain_syntax_sql.discard("")

    warnings: list[str] = []
    if unverified_pass_sql:
        warnings.append(
            f"UNVERIFIED_PASS_ACCEPTANCE: {len(unverified_pass_sql)} sql(s) have PASS acceptance without complete verification evidence"
        )
    if unverified_applicable_patch_sql:
        warnings.append(
            f"UNVERIFIED_APPLICABLE_PATCH: {len(unverified_applicable_patch_sql)} sql(s) have applicable patches without complete verification evidence"
        )
    if optimize_explain_syntax_sql:
        warnings.append(
            "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR: "
            f"{len(optimize_explain_syntax_sql)} sql(s) hit SQL syntax errors during optimize DB evidence collection"
        )

    if warnings:
        confidence = "LOW"
    elif any(str(row.get("status") or "").upper() == "PARTIAL" for row in verification_rows):
        confidence = "MEDIUM"
    else:
        confidence = "HIGH"

    return (
        warnings,
        confidence,
        {
            "unverified_pass_count": len(unverified_pass_sql),
            "unverified_applicable_patch_count": len(unverified_applicable_patch_sql),
            "critical_unverified_sql_keys": sorted(set(unverified_pass_sql + unverified_applicable_patch_sql)),
        },
    )
