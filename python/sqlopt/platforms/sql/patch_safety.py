from __future__ import annotations

from .patch_capability_rules import iter_capability_rules
from .patchability_models import CapabilityDecision, PatchabilityAssessment, RegisteredCapabilityRule
from .rewrite_facts_models import RewriteFacts


def _blocking_reason_priority(reason: str) -> tuple[int, str]:
    value = str(reason or "").strip().upper()
    if value.startswith("SEMANTIC_GATE_"):
        return (0, value)
    if value.startswith("HARD_CONFLICT:"):
        return (1, value)
    if value.startswith("AGGREGATION_CONSTRAINT:"):
        return (2, value)
    if value == "PATCH_NO_EFFECTIVE_CHANGE":
        return (3, value)
    if value == "PATCH_SEMANTIC_CONFIDENCE_LOW":
        return (4, value)
    if value.startswith("PATCH_FINGERPRINT_NOT_EXACT"):
        return (5, value)
    if value.startswith("WRAPPER_COLLAPSE_BLOCKED:"):
        return (6, value)
    if value.startswith("WRAPPER_QUERY_ABSENT"):
        return (90, value)
    if value.startswith("WRAPPER_COLLAPSE_CANDIDATE_MISMATCH"):
        return (91, value)
    if value == "PATCH_STRATEGY_UNAVAILABLE":
        return (99, value)
    return (50, value)


def _coerce_rewrite_facts(rewrite_facts: dict[str, object] | RewriteFacts) -> RewriteFacts:
    if isinstance(rewrite_facts, RewriteFacts):
        return rewrite_facts
    semantic = dict(rewrite_facts.get("semantic") or {})
    wrapper = dict(rewrite_facts.get("wrapperQuery") or {})
    cte = dict(rewrite_facts.get("cteQuery") or {})
    aggregation = dict(rewrite_facts.get("aggregationQuery") or {})
    from .rewrite_facts_models import (
        AggregationCapabilityProfile,
        AggregationQueryRewriteFacts,
        CteQueryRewriteFacts,
        DynamicTemplateCapabilityProfile,
        DynamicTemplateRewriteFacts,
        SemanticRewriteFacts,
        WrapperQueryRewriteFacts,
    )

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
        cte_query=CteQueryRewriteFacts(
            present=bool(cte.get("present")),
            cte_name=str(cte.get("cteName") or "").strip() or None,
            inner_sql=str(cte.get("innerSql") or "").strip() or None,
            inner_from_suffix=str(cte.get("innerFromSuffix") or "").strip() or None,
            collapsible=bool(cte.get("collapsible")),
            inline_candidate=bool(cte.get("inlineCandidate")),
            blockers=[str(code) for code in (cte.get("blockers") or []) if str(code).strip()],
            inlined_sql=str(cte.get("inlinedSql") or "").strip() or None,
        ),
        dynamic_template=DynamicTemplateRewriteFacts(
            present=bool((rewrite_facts.get("dynamicTemplate") or {}).get("present")),
            statement_features=[
                str(x)
                for x in (((rewrite_facts.get("dynamicTemplate") or {}).get("statementFeatures")) or [])
                if str(x).strip()
            ],
            include_fragment_refs=[
                str(x)
                for x in (((rewrite_facts.get("dynamicTemplate") or {}).get("includeFragmentRefs")) or [])
                if str(x).strip()
            ],
            include_dynamic_subtree=bool((rewrite_facts.get("dynamicTemplate") or {}).get("includeDynamicSubtree")),
            include_property_bindings=bool((rewrite_facts.get("dynamicTemplate") or {}).get("includePropertyBindings")),
            capability_profile=DynamicTemplateCapabilityProfile(
                shape_family=str((((rewrite_facts.get("dynamicTemplate") or {}).get("capabilityProfile") or {}).get("shapeFamily") or "NONE")).strip().upper()
                or "NONE",
                capability_tier=str((((rewrite_facts.get("dynamicTemplate") or {}).get("capabilityProfile") or {}).get("capabilityTier") or "NONE")).strip().upper()
                or "NONE",
                patch_surface=str((((rewrite_facts.get("dynamicTemplate") or {}).get("capabilityProfile") or {}).get("patchSurface") or "NONE")).strip().upper()
                or "NONE",
                baseline_family=str((((rewrite_facts.get("dynamicTemplate") or {}).get("capabilityProfile") or {}).get("baselineFamily") or "")).strip()
                or None,
                blocker_family=str((((rewrite_facts.get("dynamicTemplate") or {}).get("capabilityProfile") or {}).get("blockerFamily") or "")).strip().upper()
                or None,
                template_preserving_candidate=bool(
                    (((rewrite_facts.get("dynamicTemplate") or {}).get("capabilityProfile") or {}).get("templatePreservingCandidate"))
                ),
                blockers=[
                    str(code)
                    for code in ((((rewrite_facts.get("dynamicTemplate") or {}).get("capabilityProfile") or {}).get("blockers")) or [])
                    if str(code).strip()
                ],
                surface_contract=dict(
                    ((((rewrite_facts.get("dynamicTemplate") or {}).get("capabilityProfile") or {}).get("surfaceContract")) or {})
                ),
            ),
        ),
        aggregation_query=AggregationQueryRewriteFacts(
            present=bool(aggregation.get("present")),
            distinct_present=bool(aggregation.get("distinctPresent")),
            group_by_present=bool(aggregation.get("groupByPresent")),
            having_present=bool(aggregation.get("havingPresent")),
            window_present=bool(aggregation.get("windowPresent")),
            union_present=bool(aggregation.get("unionPresent")),
            distinct_relaxation_candidate=bool(aggregation.get("distinctRelaxationCandidate")),
            group_by_columns=[str(x) for x in (aggregation.get("groupByColumns") or []) if str(x).strip()],
            projection_expressions=[str(x) for x in (aggregation.get("projectionExpressions") or []) if str(x).strip()],
            aggregate_functions=[str(x) for x in (aggregation.get("aggregateFunctions") or []) if str(x).strip()],
            having_expression=str(aggregation.get("havingExpression") or "").strip() or None,
            order_by_expression=str(aggregation.get("orderByExpression") or "").strip() or None,
            limit_present=bool(aggregation.get("limitPresent")),
            offset_present=bool(aggregation.get("offsetPresent")),
            window_functions=[str(x) for x in (aggregation.get("windowFunctions") or []) if str(x).strip()],
            union_branches=int(aggregation["unionBranches"]) if aggregation.get("unionBranches") is not None else None,
            blockers=[str(code) for code in (aggregation.get("blockers") or []) if str(code).strip()],
            capability_profile=AggregationCapabilityProfile(
                shape_family=str(((aggregation.get("capabilityProfile") or {}).get("shapeFamily") or "NONE")).strip().upper() or "NONE",
                capability_tier=str(((aggregation.get("capabilityProfile") or {}).get("capabilityTier") or "NONE")).strip().upper() or "NONE",
                constraint_family=str(((aggregation.get("capabilityProfile") or {}).get("constraintFamily") or "NONE")).strip().upper() or "NONE",
                safe_baseline_family=str(((aggregation.get("capabilityProfile") or {}).get("safeBaselineFamily") or "")).strip() or None,
                review_only_family=str(((aggregation.get("capabilityProfile") or {}).get("reviewOnlyFamily") or "")).strip() or None,
                wrapper_flatten_candidate=bool((aggregation.get("capabilityProfile") or {}).get("wrapperFlattenCandidate")),
                direct_relaxation_candidate=bool((aggregation.get("capabilityProfile") or {}).get("directRelaxationCandidate")),
                blockers=[str(code) for code in (((aggregation.get("capabilityProfile") or {}).get("blockers")) or []) if str(code).strip()],
            ),
        ),
    )


def _normalize_dynamic_intent(dynamic_candidate_intent: dict[str, object] | None) -> dict[str, object]:
    payload = dict(dynamic_candidate_intent or {})
    return {
        "intent": str(payload.get("intent") or "").strip().upper() or None,
        "templatePreserving": bool(payload.get("templatePreserving")),
        "blockingReason": str(payload.get("blockingReason") or "").strip().upper() or None,
        "templateEffectiveChange": bool(payload.get("templateEffectiveChange")),
    }


def _derive_dynamic_blocking_reason(
    rewrite_facts: RewriteFacts,
    dynamic_intent: dict[str, object],
    dynamic_intent_blocker: str | None,
) -> str | None:
    dynamic_template = rewrite_facts.dynamic_template
    profile = dynamic_template.capability_profile
    if not dynamic_template.present:
        return None
    if dynamic_intent_blocker:
        return dynamic_intent_blocker

    shape_family = str(profile.shape_family or "").strip().upper()
    if not rewrite_facts.effective_change:
        if shape_family == "STATIC_INCLUDE_ONLY":
            return "STATIC_INCLUDE_NO_EFFECTIVE_DIFF"
        if shape_family in {"IF_GUARDED_FILTER_STATEMENT", "IF_GUARDED_COUNT_WRAPPER"}:
            return "DYNAMIC_FILTER_NO_EFFECTIVE_DIFF"

    intent = str(dynamic_intent.get("intent") or "").strip().upper()
    if intent == "NO_EFFECTIVE_TEMPLATE_CHANGE":
        if shape_family == "STATIC_INCLUDE_ONLY":
            return "STATIC_INCLUDE_NO_EFFECTIVE_DIFF"
        if shape_family in {"IF_GUARDED_FILTER_STATEMENT", "IF_GUARDED_COUNT_WRAPPER"}:
            return "DYNAMIC_FILTER_NO_EFFECTIVE_DIFF"

    if profile.blocker_family:
        return profile.blocker_family

    if shape_family == "STATIC_INCLUDE_ONLY" and dynamic_template.include_property_bindings:
        return "STATIC_INCLUDE_FRAGMENT_DEPENDENT"
    return None


def assess_patch_safety_model(
    rewrite_facts: dict[str, object] | RewriteFacts,
    dynamic_candidate_intent: dict[str, object] | None = None,
) -> PatchabilityAssessment:
    typed_facts = _coerce_rewrite_facts(rewrite_facts)
    aggregation_profile = typed_facts.aggregation_query.capability_profile
    dynamic_profile = typed_facts.dynamic_template.capability_profile
    dynamic_intent = _normalize_dynamic_intent(dynamic_candidate_intent)
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
    dynamic_intent_blocker = None
    if (
        typed_facts.dynamic_template.present
        and dynamic_profile.capability_tier == "SAFE_BASELINE"
        and dynamic_profile.patch_surface == "STATEMENT_BODY"
    ):
        if dynamic_intent.get("intent") != "TEMPLATE_PRESERVING_STATEMENT_EDIT" or not dynamic_intent.get("templatePreserving"):
            dynamic_intent_blocker = str(dynamic_intent.get("blockingReason") or "NO_TEMPLATE_PRESERVING_INTENT")
            blocking_code = f"DYNAMIC_TEMPLATE:{dynamic_intent_blocker}"
            if blocking_code not in blocking_reasons:
                blocking_reasons.append(blocking_code)
            allowed = [
                capability
                for capability in allowed
                if capability not in {"DYNAMIC_STATEMENT_CANONICAL_EDIT", "EXACT_TEMPLATE_EDIT"}
            ]
    if not allowed and not blocking_reasons:
        blocking_reasons.append("PATCH_STRATEGY_UNAVAILABLE")
    # If there are allowed capabilities, clear blocking_reasons as the patch is still possible
    # Only keep blockers if no capabilities are allowed
    if allowed:
        blocking_reasons = []
    blocking_reasons = [reason for reason in sorted(blocking_reasons, key=_blocking_reason_priority) if reason]
    blocking_reason = None if allowed else (blocking_reasons[0] if blocking_reasons else None)
    dynamic_blocking_reason = _derive_dynamic_blocking_reason(
        typed_facts,
        dynamic_intent,
        dynamic_intent_blocker,
    )
    return PatchabilityAssessment(
        blocking_reasons=blocking_reasons,
        blocking_reason=blocking_reason,
        allowed_capabilities=allowed,
        capability_decisions=[decision for _, decision in decisions],
        aggregation_constraint_family=(
            aggregation_profile.constraint_family
            if str(aggregation_profile.constraint_family or "").strip().upper() not in {"", "NONE"}
            else None
        ),
        aggregation_capability_tier=(
            aggregation_profile.capability_tier
            if str(aggregation_profile.capability_tier or "").strip().upper() not in {"", "NONE"}
            else None
        ),
        aggregation_safe_baseline_family=aggregation_profile.safe_baseline_family,
        aggregation_review_only_family=(
            aggregation_profile.review_only_family
            if str(aggregation_profile.review_only_family or "").strip().upper() not in {"", "NONE"}
            else None
        ),
        dynamic_shape_family=(
            dynamic_profile.shape_family if str(dynamic_profile.shape_family or "").strip().upper() not in {"", "NONE"} else None
        ),
        dynamic_capability_tier=(
            dynamic_profile.capability_tier
            if str(dynamic_profile.capability_tier or "").strip().upper() not in {"", "NONE"}
            else None
        ),
        dynamic_patch_surface=(
            dynamic_profile.patch_surface
            if str(dynamic_profile.patch_surface or "").strip().upper() not in {"", "NONE"}
            else None
        ),
        dynamic_blocking_reason=dynamic_blocking_reason,
    )


def assess_patch_safety(
    rewrite_facts: dict[str, object] | RewriteFacts,
    dynamic_candidate_intent: dict[str, object] | None = None,
) -> dict[str, object]:
    return assess_patch_safety_model(rewrite_facts, dynamic_candidate_intent).to_dict()
