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


def _estimate_patchability(original_sql: str, candidate: Candidate) -> tuple[int, str, list[str]]:
    rewritten = str(candidate.rewritten_sql or "")
    score = 60
    reasons: list[str] = []
    strategy = str(candidate.rewrite_strategy or "").strip()
    if candidate.source == "rule":
        score += 15
        reasons.append("rule-generated candidate is structurally conservative")
    if strategy in {"PROJECT_COLUMNS", "projection"}:
        score += 15
        reasons.append("projection-style rewrite is easy to patch")
    elif strategy in {"sort", "ORDER_BY_REWRITE"}:
        score += 5
        reasons.append("ordering rewrite is usually patchable")
    if "#{" in original_sql and "#{" in rewritten:
        score += 10
        reasons.append("mybatis placeholders are preserved")
    if " join " in rewritten.lower():
        score -= 10
        reasons.append("join-heavy rewrite expands structural patch surface")
    if "?" in rewritten and "#{" not in rewritten:
        score -= 20
        reasons.append("generic placeholders reduce mapper patch stability")
    score = max(0, min(score, 100))
    if score >= 80:
        tier = "HIGH"
    elif score >= 60:
        tier = "MEDIUM"
    else:
        tier = "LOW"
    return score, tier, reasons


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
        best_rank: tuple[int, int, float] | None = None
        runner_up: dict[str, Any] | None = None
        fallback: dict[str, Any] | None = None
        fallback_rank: tuple[int, int, float] | None = None
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
            patchability_score, patchability_tier, patchability_reasons = _estimate_patchability(original_sql, candidate)
            candidate_evaluations.append(
                CandidateEvaluation(
                    candidate_id=candidate.id,
                    source=candidate.source,
                    semantic_match=semantic_match,
                    improved=improved_now,
                    after_cost=None if after_cost == float("inf") else after_cost,
                    patchability_score=patchability_score,
                    patchability_tier=patchability_tier,
                    patchability_reasons=patchability_reasons,
                )
            )
            payload = {
                "candidate": candidate,
                "semantics": semantics,
                "plan": plan,
                "sql": rewritten_candidate,
                "patchability_score": patchability_score,
                "patchability_tier": patchability_tier,
                "patchability_reasons": patchability_reasons,
            }
            rank = (patchability_score, 1 if improved_now else 0, -after_cost)
            if semantic_match:
                if best_rank is None or rank > best_rank:
                    runner_up = best
                    best = payload
                    best_rank = rank
                elif runner_up is None:
                    runner_up = payload
            if fallback_rank is None or rank > fallback_rank:
                fallback = payload
                fallback_rank = rank
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
            selection_rationale = {
                "strategy": "PATCHABILITY_FIRST",
                "reasonCodes": ["VALIDATE_PATCHABILITY_PRIORITY"],
                "summary": "selected the most patchable semantically valid candidate before cost tie-break",
                "runnerUpCandidateId": runner_up["candidate"].id if runner_up is not None else None,
            }
            delivery_readiness = {
                "tier": "READY" if selected.get("patchability_tier") in {"HIGH", "MEDIUM"} else "NEEDS_TEMPLATE_REWRITE",
                "autoPatchLikelihood": selected.get("patchability_tier") or "LOW",
                "blockingReasons": []
                if selected.get("patchability_tier") in {"HIGH", "MEDIUM"}
                else ["VALIDATE_LOW_PATCHABILITY"],
            }
        else:
            selection_rationale = None
            delivery_readiness = {"tier": "BLOCKED", "autoPatchLikelihood": "LOW", "blockingReasons": ["VALIDATE_NO_CANDIDATE"]}
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
        selection_rationale = None
        delivery_readiness = {"tier": "BLOCKED", "autoPatchLikelihood": "LOW", "blockingReasons": ["VALIDATE_NO_CANDIDATE"]}

    return CandidateSelectionResult(
        rewritten_sql=rewritten_sql,
        selected_candidate_id=selected_candidate_id,
        selected_candidate_source=selected_candidate_source,
        candidate_evaluations=candidate_evaluations,
        equivalence=equivalence,
        perf=perf,
        selection_rationale=selection_rationale,
        delivery_readiness=delivery_readiness,
    )
