from __future__ import annotations

from .base import CandidateGenerationContext
from ..candidate_generation_models import RecoveryAssessment
from ..candidate_generation_support import recover_candidates_from_shape, recover_candidates_from_text


class SafeBaselineRecoveryRule:
    rule_id = "SAFE_BASELINE_RECOVERY"

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
        if degraded_kind == "TEXT_ONLY_FALLBACK":
            text = str(((raw_candidates[0] or {}).get("rewrittenSql")) or "")
            candidates = recover_candidates_from_text(context.sql_key, context.original_sql, text)
            return RecoveryAssessment(
                strategy=(str((candidates[0] or {}).get("rewriteStrategy") or "") or None) if candidates else None,
                reason="SAFE_BASELINE_TEXT_RECOVERY" if candidates else "NO_SAFE_BASELINE_TEXT_MATCH",
                candidates=candidates,
                rule_id=self.rule_id,
            )
        if degraded_kind in {"EMPTY_CANDIDATES", "ONLY_LOW_VALUE_CANDIDATES"}:
            candidates = recover_candidates_from_shape(context.sql_key, context.original_sql)
            return RecoveryAssessment(
                strategy=(str((candidates[0] or {}).get("rewriteStrategy") or "") or None) if candidates else None,
                reason="SAFE_BASELINE_SHAPE_RECOVERY" if degraded_kind == "EMPTY_CANDIDATES" and candidates else (
                    "SAFE_BASELINE_REPLACED_LOW_VALUE" if candidates else "NONE"
                ),
                candidates=candidates,
                rule_id=self.rule_id,
            )
        return None
