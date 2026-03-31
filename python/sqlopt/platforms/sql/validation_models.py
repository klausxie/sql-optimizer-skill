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
    """Validation result containing semantic and performance validation evidence.

    Note: rewrite_facts is computed by patch_select stage, not validate.
    """
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
    candidate_eval: dict[str, Any] | None = None
    selection_rationale: dict[str, Any] | None = None
    decision_layers: dict[str, Any] | None = None
    llm_semantic_check: dict[str, Any] | None = None
    semantic_equivalence: dict[str, Any] | None = None
    canonicalization: dict[str, Any] | None = None
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
        if self.candidate_eval is not None:
            payload["candidateEval"] = self.candidate_eval
        if self.selection_rationale is not None:
            payload["selectionRationale"] = self.selection_rationale
        if self.decision_layers is not None:
            payload["decisionLayers"] = self.decision_layers
        if self.llm_semantic_check is not None:
            payload["llmSemanticCheck"] = self.llm_semantic_check
        if self.semantic_equivalence is not None:
            payload["semanticEquivalence"] = self.semantic_equivalence
        if self.canonicalization is not None:
            payload["canonicalization"] = self.canonicalization
        if self.candidate_selection_trace is not None:
            payload["candidateSelectionTrace"] = self.candidate_selection_trace
        return payload

    def __getitem__(self, key: str) -> Any:
        return self.to_contract()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_contract().get(key, default)
