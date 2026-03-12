from __future__ import annotations

from ..dynamic_candidate_intent_models import DynamicCandidateIntentMatch
from ..rewrite_facts_models import RewriteFacts


class DynamicCandidateIntentRule:
    rule_id = "BASE"

    def evaluate(
        self,
        sql_unit: dict[str, object],
        original_sql: str,
        rewritten_sql: str,
        rewrite_facts: RewriteFacts,
    ) -> DynamicCandidateIntentMatch:
        raise NotImplementedError
