from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AcceptanceDecision:
    status: str
    feedback: dict[str, Any] | None
    warnings: list[str]
    reason_codes: list[str]


@dataclass(frozen=True)
class ValidationResult:
    sql_key: str
    status: str
    equivalence: dict[str, Any]
    perf_comparison: dict[str, Any]
    security_checks: dict[str, Any]
    semantic_risk: str
    feedback: dict[str, Any] | None
    selected_candidate_source: str
    warnings: list[str]
    risk_flags: list[str]
    rewritten_sql: str | None = None
    selected_candidate_id: str | None = None
    candidate_evaluations: list[dict[str, Any]] | None = None
    rewrite_materialization: dict[str, Any] | None = None
    template_rewrite_ops: list[dict[str, Any]] | None = None
    candidate_eval: dict[str, Any] | None = None
    selection_rationale: dict[str, Any] | None = None
    delivery_readiness: dict[str, Any] | None = None
    decision_layers: dict[str, Any] | None = None
    llm_semantic_check: dict[str, Any] | None = None
    semantic_equivalence: dict[str, Any] | None = None
    repairability: dict[str, Any] | None = None
    repair_hints: list[dict[str, Any]] | None = None
    rewrite_safety_level: str | None = None
    patchability: dict[str, Any] | None = None
    selected_patch_strategy: dict[str, Any] | None = None
    patch_target: dict[str, Any] | None = None
    dynamic_template: dict[str, Any] | None = None
    dynamic_candidate_intent: dict[str, Any] | None = None
    canonicalization: dict[str, Any] | None = None
    rewrite_facts: dict[str, Any] | None = None
    patch_strategy_candidates: list[dict[str, Any]] | None = None
    canonicalization_assessment: list[dict[str, Any]] | None = None
    candidate_selection_trace: list[dict[str, Any]] | None = None

    def to_contract(self) -> dict[str, Any]:
        payload = {
            "sqlKey": self.sql_key,
            "status": self.status,
            "equivalence": self.equivalence,
            "perfComparison": self.perf_comparison,
            "securityChecks": self.security_checks,
            "semanticRisk": self.semantic_risk,
            "feedback": self.feedback,
            "selectedCandidateSource": self.selected_candidate_source,
            "warnings": self.warnings,
            "riskFlags": self.risk_flags,
        }
        if self.rewritten_sql is not None:
            payload["rewrittenSql"] = self.rewritten_sql
        if self.selected_candidate_id is not None:
            payload["selectedCandidateId"] = self.selected_candidate_id
        if self.candidate_evaluations is not None:
            payload["candidateEvaluations"] = self.candidate_evaluations
        if self.rewrite_materialization is not None:
            payload["rewriteMaterialization"] = self.rewrite_materialization
        if self.template_rewrite_ops is not None:
            payload["templateRewriteOps"] = self.template_rewrite_ops
        if self.candidate_eval is not None:
            payload["candidateEval"] = self.candidate_eval
        if self.selection_rationale is not None:
            payload["selectionRationale"] = self.selection_rationale
        if self.delivery_readiness is not None:
            payload["deliveryReadiness"] = self.delivery_readiness
        if self.decision_layers is not None:
            payload["decisionLayers"] = self.decision_layers
        if self.llm_semantic_check is not None:
            payload["llmSemanticCheck"] = self.llm_semantic_check
        if self.semantic_equivalence is not None:
            payload["semanticEquivalence"] = self.semantic_equivalence
        if self.repairability is not None:
            payload["repairability"] = self.repairability
        if self.repair_hints is not None:
            payload["repairHints"] = self.repair_hints
        if self.rewrite_safety_level is not None:
            payload["rewriteSafetyLevel"] = self.rewrite_safety_level
        if self.patchability is not None:
            payload["patchability"] = self.patchability
        if self.selected_patch_strategy is not None:
            payload["selectedPatchStrategy"] = self.selected_patch_strategy
        if self.patch_target is not None:
            payload["patchTarget"] = self.patch_target
        if self.dynamic_template is not None:
            payload["dynamicTemplate"] = self.dynamic_template
        if self.canonicalization is not None:
            payload["canonicalization"] = self.canonicalization
        if self.rewrite_facts is not None:
            payload["rewriteFacts"] = self.rewrite_facts
        if self.patch_strategy_candidates is not None:
            payload["patchStrategyCandidates"] = self.patch_strategy_candidates
        if self.canonicalization_assessment is not None:
            payload["canonicalizationAssessment"] = self.canonicalization_assessment
        if self.candidate_selection_trace is not None:
            payload["candidateSelectionTrace"] = self.candidate_selection_trace
        return payload

    def __getitem__(self, key: str) -> Any:
        return self.to_contract()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_contract().get(key, default)
