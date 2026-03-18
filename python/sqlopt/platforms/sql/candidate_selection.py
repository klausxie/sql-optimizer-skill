from __future__ import annotations
from pathlib import Path
import re
from typing import Any, Callable, cast

from .candidate_patchability import assess_candidate_patchability_model
from .canonicalization_engine import assess_candidate_canonicalization_model
from .candidate_models import (
    Candidate,
    CandidateEvaluation,
    CandidateSelectionResult,
    EquivalenceCheck,
    PerfComparison,
)
from .candidate_selection_models import (
    CandidateCanonicalizationAssessmentEntry,
    CandidateSelectionRank,
    CandidateSelectionTraceEntry,
)

_SQL_CANDIDATE_PREFIX_RE = re.compile(
    r"^\s*(select|with|update|delete|insert)\b", flags=re.IGNORECASE
)


def _normalize_sql_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _numeric_cost(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float("inf")


def _is_valid_candidate_sql(sql: Any) -> bool:
    if not isinstance(sql, str):
        return False
    stripped = sql.strip()
    if not stripped or "${" in stripped:
        return False
    return _SQL_CANDIDATE_PREFIX_RE.match(stripped) is not None


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


def filter_valid_candidates(
    original_sql: str, candidates: list[Candidate]
) -> tuple[list[Candidate], int]:
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
    rewritten_sql = (
        candidate_sql
        if isinstance(candidate_sql, str) and candidate_sql.strip()
        else original_sql
    )
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
    canonicalization_assessment: list[dict[str, Any]] = []
    candidate_selection_trace: list[dict[str, Any]] = []

    if not compare_enabled:
        return CandidateSelectionResult(
            rewritten_sql=rewritten_sql,
            selected_candidate_id=selected_candidate_id,
            selected_candidate_source=selected_candidate_source,
            candidate_evaluations=candidate_evaluations,
            equivalence=equivalence,
            perf=perf,
            canonicalization=None,
            canonicalization_assessment=[],
            candidate_selection_trace=[],
        )

    selected_canonicalization: dict[str, Any] | None = None
    if valid_candidates:
        best: dict[str, Any] | None = None
        best_rank: tuple[int, int, int, int, float] | None = None
        runner_up: dict[str, Any] | None = None
        fallback: dict[str, Any] | None = None
        fallback_rank: tuple[int, int, int, int, float] | None = None
        for idx, candidate in enumerate(valid_candidates[:5], start=1):
            rewritten_candidate = candidate.rewritten_sql.strip()
            if not rewritten_candidate:
                continue
            candidate_dir = (
                evidence_dir / f"candidate_{idx}" if evidence_dir is not None else None
            )
            semantics = compare_semantics_fn(
                compare_policy, config, original_sql, rewritten_candidate, candidate_dir
            )
            plan = compare_plan_fn(
                compare_policy, config, original_sql, rewritten_candidate, candidate_dir
            )
            row_status = (
                (semantics.get("rowCount") or {}) if isinstance(semantics, dict) else {}
            ).get("status")
            semantic_match = row_status == "MATCH"
            improved_now = bool(plan.get("improved"))
            after_cost = _numeric_cost(
                (plan.get("afterSummary") or {}).get("totalCost")
            )
            patchability = assess_candidate_patchability_model(original_sql, candidate)
            patchability_score = patchability.score
            patchability_tier = patchability.tier
            patchability_reasons = list(patchability.reasons)
            canonicalization_model = assess_candidate_canonicalization_model(
                original_sql,
                rewritten_candidate,
                semantics if isinstance(semantics, dict) else {},
            )
            canonicalization = canonicalization_model.to_dict()
            canonical_preference = canonicalization_model.preference
            canonical_score = canonical_preference.preference_score
            effective_change = _normalize_sql_text(original_sql) != _normalize_sql_text(
                rewritten_candidate
            )
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
                    canonical_score=canonical_score,
                    canonical_rule_id=canonical_preference.primary_rule,
                    canonical_reason=canonical_preference.reason,
                )
            )
            canonicalization_assessment.append(
                CandidateCanonicalizationAssessmentEntry(
                    candidate_id=candidate.id,
                    source=candidate.source,
                    rewritten_sql=rewritten_candidate,
                    preferred=canonical_preference.preferred,
                    rule_id=canonical_preference.primary_rule,
                    score=canonical_score,
                    reason=canonical_preference.reason,
                    matched_rules=cast(
                        list[dict[str, object]],
                        canonicalization.get("matchedRules") or [],
                    ),
                ).to_dict()
            )
            payload = {
                "candidate": candidate,
                "semantics": semantics,
                "plan": plan,
                "sql": rewritten_candidate,
                "patchability_score": patchability_score,
                "patchability_tier": patchability_tier,
                "patchability_reasons": patchability_reasons,
                "canonicalization": canonicalization,
                "effective_change": effective_change,
            }
            rank_model = CandidateSelectionRank(
                effective_change=effective_change,
                patchability_score=patchability_score,
                canonical_score=canonical_score,
                improved=improved_now,
                after_cost=after_cost,
            )
            rank = rank_model.as_tuple()
            candidate_selection_trace.append(
                CandidateSelectionTraceEntry(
                    candidate_id=candidate.id,
                    semantic_match=semantic_match,
                    effective_change=effective_change,
                    patchability_score=patchability_score,
                    canonical_score=canonical_score,
                    improved=improved_now,
                    after_cost=None if after_cost == float("inf") else after_cost,
                    rank=rank_model,
                ).to_dict()
            )
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
            selected_canonicalization = dict(selected.get("canonicalization") or {})
            semantics = selected["semantics"] or {}
            plan = selected["plan"] or {}
            equivalence = EquivalenceCheck(
                checked=semantics.get("checked"),
                method=semantics.get("method", "sql_semantic_compare_v1"),
                row_count=semantics.get("rowCount"),
                key_set_hash=semantics.get("keySetHash"),
                row_sample_hash=semantics.get("rowSampleHash"),
                evidence_refs=semantics.get("evidenceRefs", []),
                evidence_ref_objects=semantics.get("evidenceRefObjects"),
            )
            perf = PerfComparison(
                checked=bool(plan.get("checked")),
                method=plan.get("method", "sql_explain_json_compare"),
                before_summary=plan.get("beforeSummary") or {},
                after_summary=plan.get("afterSummary") or {},
                reason_codes=list(plan.get("reasonCodes", [])),
                improved=plan.get("improved"),
                evidence_refs=list(plan.get("evidenceRefs", [])),
            )
            selection_rationale = {
                "strategy": "PATCHABILITY_FIRST",
                "reasonCodes": ["VALIDATE_PATCHABILITY_PRIORITY"],
                "summary": "selected the most patchable semantically valid candidate before cost tie-break",
                "runnerUpCandidateId": runner_up["candidate"].id
                if runner_up is not None
                else None,
            }
            delivery_readiness = {
                "tier": "READY"
                if selected.get("patchability_tier") in {"HIGH", "MEDIUM"}
                else "NEEDS_TEMPLATE_REWRITE",
                "autoPatchLikelihood": selected.get("patchability_tier") or "LOW",
                "blockingReasons": []
                if selected.get("patchability_tier") in {"HIGH", "MEDIUM"}
                else ["VALIDATE_LOW_PATCHABILITY"],
            }
        else:
            selection_rationale = None
            delivery_readiness = {
                "tier": "BLOCKED",
                "autoPatchLikelihood": "LOW",
                "blockingReasons": ["VALIDATE_NO_CANDIDATE"],
            }
    else:
        semantics = compare_semantics_fn(
            compare_policy, config, original_sql, rewritten_sql, evidence_dir
        )
        plan = compare_plan_fn(
            compare_policy, config, original_sql, rewritten_sql, evidence_dir
        )
        equivalence = EquivalenceCheck(
            checked=semantics.get("checked"),
            method=semantics.get("method", "sql_semantic_compare_v1"),
            row_count=semantics.get("rowCount"),
            key_set_hash=semantics.get("keySetHash"),
            row_sample_hash=semantics.get("rowSampleHash"),
            evidence_refs=semantics.get("evidenceRefs", []),
            evidence_ref_objects=semantics.get("evidenceRefObjects"),
        )
        perf = PerfComparison(
            checked=bool(plan.get("checked")),
            method=plan.get("method", "sql_explain_json_compare"),
            before_summary=plan.get("beforeSummary") or {},
            after_summary=plan.get("afterSummary") or {},
            reason_codes=list(plan.get("reasonCodes", [])),
            improved=plan.get("improved"),
            evidence_refs=list(plan.get("evidenceRefs", [])),
        )
        selection_rationale = None
        delivery_readiness = {
            "tier": "BLOCKED",
            "autoPatchLikelihood": "LOW",
            "blockingReasons": ["VALIDATE_NO_CANDIDATE"],
        }

    return CandidateSelectionResult(
        rewritten_sql=rewritten_sql,
        selected_candidate_id=selected_candidate_id,
        selected_candidate_source=selected_candidate_source,
        candidate_evaluations=candidate_evaluations,
        equivalence=equivalence,
        perf=perf,
        selection_rationale=selection_rationale,
        delivery_readiness=delivery_readiness,
        canonicalization=selected_canonicalization,
        canonicalization_assessment=canonicalization_assessment,
        candidate_selection_trace=candidate_selection_trace,
    )
