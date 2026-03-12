from __future__ import annotations

from .base import CandidateGenerationContext
from ..candidate_generation_models import RecoveryAssessment
from ..candidate_generation_support import classify_blocked_shape


class BlockedShapeRecoveryRule:
    rule_id = "BLOCKED_SHAPE_REASON"

    def recover(
        self,
        context: CandidateGenerationContext,
        *,
        degraded_kind: str,
        raw_candidates: list[dict[str, object]],
        accepted_candidates: list[dict[str, object]],
    ) -> RecoveryAssessment | None:
        if accepted_candidates:
            return None
        if degraded_kind != "EMPTY_CANDIDATES":
            return None
        return RecoveryAssessment(
            strategy=None,
            reason=classify_blocked_shape(context.original_sql, context.sql_unit),
            candidates=[],
            rule_id=self.rule_id,
        )

