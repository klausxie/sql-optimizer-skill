from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..candidate_generation_models import LowValueAssessment, RecoveryAssessment


@dataclass(frozen=True)
class CandidateGenerationContext:
    sql_key: str
    original_sql: str
    sql_unit: dict[str, Any]
    trace: dict[str, Any]


class LowValueRule(Protocol):
    rule_id: str

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, Any]) -> LowValueAssessment | None:
        ...


class RecoveryRule(Protocol):
    rule_id: str

    def recover(
        self,
        context: CandidateGenerationContext,
        *,
        degraded_kind: str,
        raw_candidates: list[dict[str, Any]],
        accepted_candidates: list[dict[str, Any]],
    ) -> RecoveryAssessment | None:
        ...

