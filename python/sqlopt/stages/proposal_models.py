from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LlmCandidate:
    """LLM 生成的优化候选"""

    id: str
    rewritten_sql: str
    rewrite_strategy: str
    source: str = "llm"
    semantic_risk: str | None = None
    confidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，保持与现有 JSON 结构兼容"""
        result = {
            "id": self.id,
            "rewrittenSql": self.rewritten_sql,
            "rewriteStrategy": self.rewrite_strategy,
            "source": self.source,
        }
        if self.semantic_risk is not None:
            result["semanticRisk"] = self.semantic_risk
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LlmCandidate:
        """从字典创建"""
        return cls(
            id=str(data.get("id") or ""),
            rewritten_sql=str(data.get("rewrittenSql") or ""),
            rewrite_strategy=str(data.get("rewriteStrategy") or ""),
            source=str(data.get("source", "llm")),
            semantic_risk=data.get("semanticRisk"),
            confidence=data.get("confidence"),
        )


@dataclass
class CandidateGenerationDiagnostics:
    """候选生成诊断数据"""

    degradation_kind: str | None = None
    recovery_attempted: bool = False
    recovery_strategy: str | None = None
    recovery_succeeded: bool = False
    recovery_reason: str = "NONE"
    raw_candidate_count: int = 0
    validated_candidate_count: int = 0
    accepted_candidate_count: int = 0
    pruned_low_value_count: int = 0
    low_value_candidate_count: int = 0
    recovered_candidate_count: int = 0
    raw_rewrite_strategies: list[str] = field(default_factory=list)
    final_candidate_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "degradationKind": self.degradation_kind,
            "recoveryAttempted": self.recovery_attempted,
            "recoveryStrategy": self.recovery_strategy,
            "recoverySucceeded": self.recovery_succeeded,
            "recoveryReason": self.recovery_reason,
            "rawCandidateCount": self.raw_candidate_count,
            "validatedCandidateCount": self.validated_candidate_count,
            "acceptedCandidateCount": self.accepted_candidate_count,
            "prunedLowValueCount": self.pruned_low_value_count,
            "lowValueCandidateCount": self.low_value_candidate_count,
            "recoveredCandidateCount": self.recovered_candidate_count,
            "rawRewriteStrategies": self.raw_rewrite_strategies,
            "finalCandidateCount": self.final_candidate_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateGenerationDiagnostics:
        """从字典创建"""
        return cls(
            degradation_kind=data.get("degradationKind"),
            recovery_attempted=data.get("recoveryAttempted", False),
            recovery_strategy=data.get("recoveryStrategy"),
            recovery_succeeded=data.get("recoverySucceeded", False),
            recovery_reason=data.get("recoveryReason", "NONE"),
            raw_candidate_count=data.get("rawCandidateCount", 0),
            validated_candidate_count=data.get("validatedCandidateCount", 0),
            accepted_candidate_count=data.get("acceptedCandidateCount", 0),
            pruned_low_value_count=data.get("prunedLowValueCount", 0),
            low_value_candidate_count=data.get("lowValueCandidateCount", 0),
            recovered_candidate_count=data.get("recoveredCandidateCount", 0),
            raw_rewrite_strategies=data.get("rawRewriteStrategies", []),
            final_candidate_count=data.get("finalCandidateCount", 0),
        )


# 常量定义 - 替代字符串键
LLM_CANDIDATES_KEY = "llmCandidates"
CANDIDATE_GENERATION_DIAGNOSTICS_KEY = "candidateGenerationDiagnostics"
LLM_VALIDATION_RESULTS_KEY = "llmValidationResults"
LLM_RETRY_TRACES_KEY = "llmRetryTraces"
LLM_RETRY_STATS_KEY = "llmRetryStats"
LLM_TRACE_REFS_KEY = "llmTraceRefs"