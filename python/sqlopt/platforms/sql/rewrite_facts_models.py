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

    def to_dict(self) -> dict[str, object]:
        return {
            "effectiveChange": self.effective_change,
            "dynamicFeatures": list(self.dynamic_features),
            "templateAnchorStable": self.template_anchor_stable,
            "semantic": self.semantic.to_dict(),
            "wrapperQuery": self.wrapper_query.to_dict(),
        }
