from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SemanticRewriteFacts:
    status: str
    confidence: str
    evidence_level: str
    fingerprint_strength: str
    hard_conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "evidenceLevel": self.evidence_level,
            "fingerprintStrength": self.fingerprint_strength,
            "hardConflicts": list(self.hard_conflicts),
        }


@dataclass(frozen=True)
class WrapperQueryRewriteFacts:
    present: bool
    aggregate: str | None
    static_include_tree: bool
    inner_sql: str | None
    inner_from_suffix: str | None
    collapsible: bool
    collapse_candidate: bool
    blockers: list[str] = field(default_factory=list)
    rewritten_count_expr: str | None = None
    rewritten_from_suffix: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "present": self.present,
            "aggregate": self.aggregate,
            "staticIncludeTree": self.static_include_tree,
            "innerSql": self.inner_sql,
            "innerFromSuffix": self.inner_from_suffix,
            "collapsible": self.collapsible,
            "collapseCandidate": self.collapse_candidate,
            "blockers": list(self.blockers),
            "rewrittenCountExpr": self.rewritten_count_expr,
            "rewrittenFromSuffix": self.rewritten_from_suffix,
        }


@dataclass(frozen=True)
class CteQueryRewriteFacts:
    present: bool
    cte_name: str | None
    inner_sql: str | None
    inner_from_suffix: str | None
    collapsible: bool
    inline_candidate: bool
    blockers: list[str] = field(default_factory=list)
    inlined_sql: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "present": self.present,
            "cteName": self.cte_name,
            "innerSql": self.inner_sql,
            "innerFromSuffix": self.inner_from_suffix,
            "collapsible": self.collapsible,
            "inlineCandidate": self.inline_candidate,
            "blockers": list(self.blockers),
            "inlinedSql": self.inlined_sql,
        }


@dataclass(frozen=True)
class AggregationCapabilityProfile:
    shape_family: str
    capability_tier: str
    constraint_family: str
    safe_baseline_family: str | None = None
    wrapper_flatten_candidate: bool = False
    direct_relaxation_candidate: bool = False
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "shapeFamily": self.shape_family,
            "capabilityTier": self.capability_tier,
            "constraintFamily": self.constraint_family,
            "safeBaselineFamily": self.safe_baseline_family,
            "wrapperFlattenCandidate": self.wrapper_flatten_candidate,
            "directRelaxationCandidate": self.direct_relaxation_candidate,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class DynamicTemplateCapabilityProfile:
    shape_family: str
    capability_tier: str
    patch_surface: str
    baseline_family: str | None = None
    blocker_family: str | None = None
    template_preserving_candidate: bool = False
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "shapeFamily": self.shape_family,
            "capabilityTier": self.capability_tier,
            "patchSurface": self.patch_surface,
            "baselineFamily": self.baseline_family,
            "blockerFamily": self.blocker_family,
            "templatePreservingCandidate": self.template_preserving_candidate,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class DynamicTemplateRewriteFacts:
    present: bool
    statement_features: list[str] = field(default_factory=list)
    include_fragment_refs: list[str] = field(default_factory=list)
    include_dynamic_subtree: bool = False
    include_property_bindings: bool = False
    capability_profile: DynamicTemplateCapabilityProfile = field(
        default_factory=lambda: DynamicTemplateCapabilityProfile(
            shape_family="NONE",
            capability_tier="NONE",
            patch_surface="NONE",
            blocker_family=None,
            template_preserving_candidate=False,
            blockers=[],
        )
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "present": self.present,
            "statementFeatures": list(self.statement_features),
            "includeFragmentRefs": list(self.include_fragment_refs),
            "includeDynamicSubtree": self.include_dynamic_subtree,
            "includePropertyBindings": self.include_property_bindings,
            "capabilityProfile": self.capability_profile.to_dict(),
        }


@dataclass(frozen=True)
class AggregationQueryRewriteFacts:
    present: bool
    distinct_present: bool
    group_by_present: bool
    having_present: bool
    window_present: bool
    union_present: bool
    distinct_relaxation_candidate: bool
    group_by_columns: list[str] = field(default_factory=list)
    projection_expressions: list[str] = field(default_factory=list)
    aggregate_functions: list[str] = field(default_factory=list)
    having_expression: str | None = None
    order_by_expression: str | None = None
    limit_present: bool = False
    offset_present: bool = False
    window_functions: list[str] = field(default_factory=list)
    union_branches: int | None = None
    blockers: list[str] = field(default_factory=list)
    capability_profile: AggregationCapabilityProfile = field(
        default_factory=lambda: AggregationCapabilityProfile(
            shape_family="NONE",
            capability_tier="NONE",
            constraint_family="NONE",
            safe_baseline_family=None,
            wrapper_flatten_candidate=False,
            direct_relaxation_candidate=False,
            blockers=[],
        )
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "present": self.present,
            "distinctPresent": self.distinct_present,
            "groupByPresent": self.group_by_present,
            "havingPresent": self.having_present,
            "windowPresent": self.window_present,
            "unionPresent": self.union_present,
            "distinctRelaxationCandidate": self.distinct_relaxation_candidate,
            "groupByColumns": list(self.group_by_columns),
            "projectionExpressions": list(self.projection_expressions),
            "aggregateFunctions": list(self.aggregate_functions),
            "havingExpression": self.having_expression,
            "orderByExpression": self.order_by_expression,
            "limitPresent": self.limit_present,
            "offsetPresent": self.offset_present,
            "windowFunctions": list(self.window_functions),
            "unionBranches": self.union_branches,
            "blockers": list(self.blockers),
            "capabilityProfile": self.capability_profile.to_dict(),
        }


@dataclass(frozen=True)
class RewriteFacts:
    effective_change: bool
    dynamic_features: list[str] = field(default_factory=list)
    template_anchor_stable: bool = False
    semantic: SemanticRewriteFacts = field(
        default_factory=lambda: SemanticRewriteFacts(
            status="UNCERTAIN",
            confidence="LOW",
            evidence_level="STRUCTURE",
            fingerprint_strength="NONE",
            hard_conflicts=[],
        )
    )
    wrapper_query: WrapperQueryRewriteFacts = field(
        default_factory=lambda: WrapperQueryRewriteFacts(
            present=False,
            aggregate=None,
            static_include_tree=False,
            inner_sql=None,
            inner_from_suffix=None,
            collapsible=False,
            collapse_candidate=False,
            blockers=[],
        )
    )
    cte_query: CteQueryRewriteFacts = field(
        default_factory=lambda: CteQueryRewriteFacts(
            present=False,
            cte_name=None,
            inner_sql=None,
            inner_from_suffix=None,
            collapsible=False,
            inline_candidate=False,
            blockers=[],
            inlined_sql=None,
        )
    )
    dynamic_template: DynamicTemplateRewriteFacts = field(
        default_factory=lambda: DynamicTemplateRewriteFacts(
            present=False,
            statement_features=[],
            include_fragment_refs=[],
            include_dynamic_subtree=False,
            include_property_bindings=False,
            capability_profile=DynamicTemplateCapabilityProfile(
                shape_family="NONE",
                capability_tier="NONE",
                patch_surface="NONE",
                baseline_family=None,
                blocker_family=None,
                template_preserving_candidate=False,
                blockers=[],
            ),
        )
    )
    aggregation_query: AggregationQueryRewriteFacts = field(
        default_factory=lambda: AggregationQueryRewriteFacts(
            present=False,
            distinct_present=False,
            group_by_present=False,
            having_present=False,
            window_present=False,
            union_present=False,
            distinct_relaxation_candidate=False,
            group_by_columns=[],
            projection_expressions=[],
            aggregate_functions=[],
            having_expression=None,
            order_by_expression=None,
            limit_present=False,
            offset_present=False,
            window_functions=[],
            union_branches=None,
            blockers=[],
            capability_profile=AggregationCapabilityProfile(
                shape_family="NONE",
                capability_tier="NONE",
                constraint_family="NONE",
                safe_baseline_family=None,
                wrapper_flatten_candidate=False,
                direct_relaxation_candidate=False,
                blockers=[],
            ),
        )
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "effectiveChange": self.effective_change,
            "dynamicFeatures": list(self.dynamic_features),
            "templateAnchorStable": self.template_anchor_stable,
            "semantic": self.semantic.to_dict(),
            "wrapperQuery": self.wrapper_query.to_dict(),
            "cteQuery": self.cte_query.to_dict(),
            "dynamicTemplate": self.dynamic_template.to_dict(),
            "aggregationQuery": self.aggregation_query.to_dict(),
        }
