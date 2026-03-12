from __future__ import annotations

from pathlib import Path

from ..dynamic_candidate_intent_models import DynamicCandidateIntentMatch
from ..dynamic_template_support import render_from_alias_cleanup_template, replay_template_sql
from ..rewrite_facts_models import RewriteFacts
from ..template_rendering import normalize_sql_text
from .base import DynamicCandidateIntentRule


class DynamicFilterFromAliasCleanupIntentRule(DynamicCandidateIntentRule):
    rule_id = "DYNAMIC_FILTER_FROM_ALIAS_TEMPLATE_EDIT"

    def evaluate(
        self,
        sql_unit: dict[str, object],
        original_sql: str,
        rewritten_sql: str,
        rewrite_facts: RewriteFacts,
    ) -> DynamicCandidateIntentMatch:
        _ = original_sql
        profile = rewrite_facts.dynamic_template.capability_profile
        if (
            not rewrite_facts.dynamic_template.present
            or profile.shape_family != "IF_GUARDED_FILTER_STATEMENT"
            or profile.capability_tier != "SAFE_BASELINE"
            or profile.patch_surface != "STATEMENT_BODY"
            or profile.baseline_family != "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP"
        ):
            return DynamicCandidateIntentMatch(rule_id=self.rule_id, matched=False)

        rebuilt_template, changed = render_from_alias_cleanup_template(str(sql_unit.get("templateSql") or ""))
        if not rebuilt_template or not changed:
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                details={"shapeFamily": profile.shape_family, "baselineFamily": profile.baseline_family},
            )

        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        namespace = str(sql_unit.get("namespace") or "").strip()
        replayed = replay_template_sql(rebuilt_template, namespace, xml_path)
        if replayed is None or normalize_sql_text(replayed) != normalize_sql_text(rewritten_sql):
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                rebuilt_template=rebuilt_template,
                details={"shapeFamily": profile.shape_family, "baselineFamily": profile.baseline_family},
            )

        return DynamicCandidateIntentMatch(
            rule_id=self.rule_id,
            matched=True,
            intent="TEMPLATE_PRESERVING_STATEMENT_EDIT",
            rebuilt_template=rebuilt_template,
            details={"shapeFamily": profile.shape_family, "baselineFamily": profile.baseline_family},
        )
