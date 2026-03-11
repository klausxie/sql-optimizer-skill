from __future__ import annotations

from .patch_capability_rules import iter_capability_rules
from .patchability_models import CapabilityDecision, PatchabilityAssessment, RegisteredCapabilityRule
from .rewrite_facts_models import RewriteFacts


def _coerce_rewrite_facts(rewrite_facts: dict[str, object] | RewriteFacts) -> RewriteFacts:
    if isinstance(rewrite_facts, RewriteFacts):
        return rewrite_facts
    semantic = dict(rewrite_facts.get("semantic") or {})
    wrapper = dict(rewrite_facts.get("wrapperQuery") or {})
    from .rewrite_facts_models import SemanticRewriteFacts, WrapperQueryRewriteFacts

    return RewriteFacts(
        effective_change=bool(rewrite_facts.get("effectiveChange")),
        dynamic_features=[str(x) for x in (rewrite_facts.get("dynamicFeatures") or []) if str(x).strip()],
        template_anchor_stable=bool(rewrite_facts.get("templateAnchorStable")),
        semantic=SemanticRewriteFacts(
            status=str(semantic.get("status") or "UNCERTAIN").strip().upper(),
            confidence=str(semantic.get("confidence") or "LOW").strip().upper(),
            evidence_level=str(semantic.get("evidenceLevel") or "STRUCTURE").strip().upper(),
            fingerprint_strength=str(semantic.get("fingerprintStrength") or "NONE").strip().upper(),
            hard_conflicts=[str(code) for code in (semantic.get("hardConflicts") or []) if str(code).strip()],
        ),
        wrapper_query=WrapperQueryRewriteFacts(
            present=bool(wrapper.get("present")),
            aggregate=str(wrapper.get("aggregate") or "").strip() or None,
            static_include_tree=bool(wrapper.get("staticIncludeTree")),
            inner_sql=str(wrapper.get("innerSql") or "").strip() or None,
            inner_from_suffix=str(wrapper.get("innerFromSuffix") or "").strip() or None,
            collapsible=bool(wrapper.get("collapsible")),
            collapse_candidate=bool(wrapper.get("collapseCandidate")),
            blockers=[str(code) for code in (wrapper.get("blockers") or []) if str(code).strip()],
            rewritten_count_expr=str(wrapper.get("rewrittenCountExpr") or "").strip() or None,
            rewritten_from_suffix=str(wrapper.get("rewrittenFromSuffix") or "").strip() or None,
        ),
    )


def assess_patch_safety_model(rewrite_facts: dict[str, object] | RewriteFacts) -> PatchabilityAssessment:
    typed_facts = _coerce_rewrite_facts(rewrite_facts)
    decisions: list[tuple[RegisteredCapabilityRule, CapabilityDecision]] = []
    blocking_reasons: list[str] = []
    for registered_rule in iter_capability_rules():
        decision = registered_rule.implementation.evaluate(typed_facts)
        decisions.append((registered_rule, decision))
        if not decision.allowed and decision.reason and decision.reason not in blocking_reasons:
            blocking_reasons.append(decision.reason)

    allowed = [
        decision.capability
        for _, decision in sorted(
            decisions,
            key=lambda row: (-row[0].priority, -row[1].priority, row[1].capability),
        )
        if decision.allowed
    ]
    if not allowed and not blocking_reasons:
        blocking_reasons.append("PATCH_STRATEGY_UNAVAILABLE")
    return PatchabilityAssessment(
        eligible=bool(allowed),
        allowed_capabilities=allowed,
        blocking_reason=blocking_reasons[0] if blocking_reasons else None,
        blocking_reasons=blocking_reasons,
        capability_decisions=[decision for _, decision in decisions],
    )


def assess_patch_safety(rewrite_facts: dict[str, object] | RewriteFacts) -> dict[str, object]:
    return assess_patch_safety_model(rewrite_facts).to_dict()
