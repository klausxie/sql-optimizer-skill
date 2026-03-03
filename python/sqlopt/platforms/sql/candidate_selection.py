from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .candidate_models import (
    Candidate,
    CandidateEvaluation,
    CandidateSelectionResult,
    EquivalenceCheck,
    PerfComparison,
)


def _numeric_cost(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float("inf")


def _is_valid_candidate_sql(sql: Any) -> bool:
    if not isinstance(sql, str):
        return False
    stripped = sql.strip()
    return bool(stripped) and "${" not in stripped


def _preserves_mybatis_placeholders(original_sql: str, rewritten_sql: str) -> bool:
    if "#{" not in str(original_sql):
        return True
    rewritten = str(rewritten_sql or "")
    if "#{" in rewritten:
        return True
    return "?" not in rewritten


def build_candidate_pool(sql_key: str, proposal: dict[str, Any]) -> list[Candidate]:
    out: list[Candidate] = []
    seen_sql: set[str] = set()
    for i, row in enumerate(proposal.get("llmCandidates") or [], start=1):
        if not isinstance(row, dict):
            continue
        rewritten = str(row.get("rewrittenSql") or "").strip()
        if not rewritten or rewritten in seen_sql:
            continue
        seen_sql.add(rewritten)
        out.append(
            Candidate(
                id=str(row.get("id") or f"{sql_key}:llm:c{i}"),
                source="llm",
                rewritten_sql=rewritten,
                rewrite_strategy=str(row.get("rewriteStrategy") or "llm"),
            )
        )
    for i, row in enumerate(proposal.get("suggestions") or [], start=1):
        if not isinstance(row, dict):
            continue
        rewritten = str(row.get("sql") or "").strip()
        if not rewritten or rewritten in seen_sql:
            continue
        seen_sql.add(rewritten)
        out.append(
            Candidate(
                id=f"{sql_key}:rule:c{i}",
                source="rule",
                rewritten_sql=rewritten,
                rewrite_strategy=str(row.get("action") or "rule"),
            )
        )
    return out


def filter_valid_candidates(original_sql: str, candidates: list[Candidate]) -> tuple[list[Candidate], int]:
    valid_candidates: list[Candidate] = []
    rejected_placeholder_semantics = 0
    for candidate in candidates:
        rewritten = candidate.rewritten_sql
        if not _is_valid_candidate_sql(rewritten):
            continue
        if not _preserves_mybatis_placeholders(original_sql, rewritten):
            rejected_placeholder_semantics += 1
            continue
        valid_candidates.append(candidate)
    return valid_candidates, rejected_placeholder_semantics


def evaluate_candidate_selection(
    original_sql: str,
    proposal: dict[str, Any],
    config: dict[str, Any] | None,
    evidence_dir: Path | None,
    compare_policy: Any,
    valid_candidates: list[Candidate],
    compare_semantics_fn: Callable[..., dict[str, Any]],
    compare_plan_fn: Callable[..., dict[str, Any]],
    *,
    compare_enabled: bool,
) -> CandidateSelectionResult:
    candidate_sql = valid_candidates[0].rewritten_sql if valid_candidates else None
    rewritten_sql = candidate_sql if isinstance(candidate_sql, str) and candidate_sql.strip() else original_sql
    equivalence = EquivalenceCheck(checked=True, method="static", evidence_refs=[])
    perf = PerfComparison(
        checked=True,
        method="heuristic",
        before_summary={},
        after_summary={},
        reason_codes=[],
        improved=bool(proposal.get("suggestions")),
        evidence_refs=[],
    )
    selected_candidate_id = None
    selected_candidate_source = None
    candidate_evaluations: list[CandidateEvaluation] = []

    if not compare_enabled:
        return CandidateSelectionResult(
            rewritten_sql=rewritten_sql,
            selected_candidate_id=selected_candidate_id,
            selected_candidate_source=selected_candidate_source,
            candidate_evaluations=candidate_evaluations,
            equivalence=equivalence,
            perf=perf,
        )

    if valid_candidates:
        best: dict[str, Any] | None = None
        best_cost = float("inf")
        fallback: dict[str, Any] | None = None
        fallback_cost = float("inf")
        for idx, candidate in enumerate(valid_candidates[:5], start=1):
            rewritten_candidate = candidate.rewritten_sql.strip()
            if not rewritten_candidate:
                continue
            candidate_dir = evidence_dir / f"candidate_{idx}" if evidence_dir is not None else None
            semantics = compare_semantics_fn(compare_policy, config, original_sql, rewritten_candidate, candidate_dir)
            plan = compare_plan_fn(compare_policy, config, original_sql, rewritten_candidate, candidate_dir)
            row_status = ((semantics.get("rowCount") or {}) if isinstance(semantics, dict) else {}).get("status")
            semantic_match = row_status == "MATCH"
            improved_now = bool(plan.get("improved"))
            after_cost = _numeric_cost((plan.get("afterSummary") or {}).get("totalCost"))
            candidate_evaluations.append(
                CandidateEvaluation(
                    candidate_id=candidate.id,
                    source=candidate.source,
                    semantic_match=semantic_match,
                    improved=improved_now,
                    after_cost=None if after_cost == float("inf") else after_cost,
                )
            )
            payload = {"candidate": candidate, "semantics": semantics, "plan": plan, "sql": rewritten_candidate}
            if semantic_match and after_cost < fallback_cost:
                fallback = payload
                fallback_cost = after_cost
            elif fallback is None:
                fallback = payload
            if semantic_match and improved_now and after_cost < best_cost:
                best = payload
                best_cost = after_cost
        selected = best or fallback
        if selected is not None:
            picked = selected["candidate"]
            rewritten_sql = str(selected["sql"])
            selected_candidate_id = picked.id
            selected_candidate_source = picked.source
            semantics = selected["semantics"] or {}
            plan = selected["plan"] or {}
            equivalence = EquivalenceCheck(
                checked=semantics.get("checked"),
                method=semantics.get("method", "sql_semantic_compare_v1"),
                row_count=semantics.get("rowCount"),
                evidence_refs=semantics.get("evidenceRefs", []),
            )
            perf = PerfComparison(
                checked=bool(plan.get("checked")),
                method=plan.get("method", "sql_explain_json_compare"),
                before_summary=plan.get("beforeSummary"),
                after_summary=plan.get("afterSummary"),
                reason_codes=list(plan.get("reasonCodes", [])),
                improved=plan.get("improved"),
                evidence_refs=list(plan.get("evidenceRefs", [])),
            )
    else:
        semantics = compare_semantics_fn(compare_policy, config, original_sql, rewritten_sql, evidence_dir)
        plan = compare_plan_fn(compare_policy, config, original_sql, rewritten_sql, evidence_dir)
        equivalence = EquivalenceCheck(
            checked=semantics.get("checked"),
            method=semantics.get("method", "sql_semantic_compare_v1"),
            row_count=semantics.get("rowCount"),
            evidence_refs=semantics.get("evidenceRefs", []),
        )
        perf = PerfComparison(
            checked=bool(plan.get("checked")),
            method=plan.get("method", "sql_explain_json_compare"),
            before_summary=plan.get("beforeSummary"),
            after_summary=plan.get("afterSummary"),
            reason_codes=list(plan.get("reasonCodes", [])),
            improved=plan.get("improved"),
            evidence_refs=list(plan.get("evidenceRefs", [])),
        )

    return CandidateSelectionResult(
        rewritten_sql=rewritten_sql,
        selected_candidate_id=selected_candidate_id,
        selected_candidate_source=selected_candidate_source,
        candidate_evaluations=candidate_evaluations,
        equivalence=equivalence,
        perf=perf,
    )
