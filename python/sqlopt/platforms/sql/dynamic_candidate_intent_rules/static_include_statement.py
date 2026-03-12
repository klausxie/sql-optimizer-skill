from __future__ import annotations

from ..dynamic_candidate_intent_models import DynamicCandidateIntentMatch
from ..rewrite_facts_models import RewriteFacts
from ..template_materializer import build_rewrite_materialization
from .base import DynamicCandidateIntentRule


class StaticIncludeStatementIntentRule(DynamicCandidateIntentRule):
    rule_id = "STATIC_INCLUDE_TEMPLATE_PRESERVING_STATEMENT_EDIT"

    def evaluate(
        self,
        sql_unit: dict[str, object],
        original_sql: str,
        rewritten_sql: str,
        rewrite_facts: RewriteFacts,
    ) -> DynamicCandidateIntentMatch:
        _ = original_sql
        profile = rewrite_facts.dynamic_template.capability_profile
        if not rewrite_facts.dynamic_template.present or profile.shape_family != "STATIC_INCLUDE_ONLY":
            return DynamicCandidateIntentMatch(rule_id=self.rule_id, matched=False)

        materialization, ops = build_rewrite_materialization(
            sql_unit,
            rewritten_sql,
            {},
            enable_fragment_materialization=False,
        )
        if str(materialization.get("mode") or "") != "STATEMENT_TEMPLATE_SAFE":
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                details={
                    "shapeFamily": profile.shape_family,
                    "reasonCode": str(materialization.get("reasonCode") or ""),
                },
            )

        statement_op = next((row for row in ops if str(row.get("op") or "") == "replace_statement_body"), None)
        rebuilt_template = str((statement_op or {}).get("afterTemplate") or "").strip() or None
        return DynamicCandidateIntentMatch(
            rule_id=self.rule_id,
            matched=True,
            intent="TEMPLATE_PRESERVING_STATEMENT_EDIT",
            rebuilt_template=rebuilt_template,
            details={"shapeFamily": profile.shape_family},
        )
