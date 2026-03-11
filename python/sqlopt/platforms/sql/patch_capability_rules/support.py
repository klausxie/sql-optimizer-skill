from __future__ import annotations

from ..rewrite_facts_models import RewriteFacts


def common_gate_failures(rewrite_facts: RewriteFacts) -> list[str]:
    status = rewrite_facts.semantic.status
    confidence = rewrite_facts.semantic.confidence
    hard_conflicts = list(rewrite_facts.semantic.hard_conflicts)

    failures: list[str] = []
    if not rewrite_facts.effective_change:
        failures.append("PATCH_NO_EFFECTIVE_CHANGE")
    if status != "PASS":
        failures.append(f"SEMANTIC_GATE_{status}")
    if confidence == "LOW":
        failures.append("PATCH_SEMANTIC_CONFIDENCE_LOW")
    if hard_conflicts:
        failures.append(f"HARD_CONFLICT:{hard_conflicts[0]}")
    return failures


def semantic_gate_ready(rewrite_facts: RewriteFacts) -> bool:
    return not common_gate_failures(rewrite_facts)


def wrapper_blockers(rewrite_facts: RewriteFacts) -> list[str]:
    fingerprint_strength = rewrite_facts.semantic.fingerprint_strength
    wrapper = rewrite_facts.wrapper_query

    reasons: list[str] = []
    if fingerprint_strength != "EXACT":
        reasons.append("PATCH_FINGERPRINT_NOT_EXACT")
    if not wrapper.collapsible:
        blockers = list(wrapper.blockers)
        if blockers:
            reasons.append(f"WRAPPER_COLLAPSE_BLOCKED:{blockers[0]}")
        elif wrapper.present:
            reasons.append("WRAPPER_COLLAPSE_BLOCKED:UNKNOWN")
    if not wrapper.collapse_candidate:
        reasons.append("WRAPPER_COLLAPSE_CANDIDATE_MISMATCH")
    return reasons
