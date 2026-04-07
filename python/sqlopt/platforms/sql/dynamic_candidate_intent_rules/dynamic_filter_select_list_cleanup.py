from __future__ import annotations

import re
from pathlib import Path

from ..canonicalization_support import split_select_list
from ..dynamic_candidate_intent_models import DynamicCandidateIntentMatch
from ..dynamic_template_support import parse_direct_select_template, render_select_alias_cleanup_template, replay_template_sql
from ..rewrite_facts_models import RewriteFacts
from ..template_rendering import normalize_sql_text
from .base import DynamicCandidateIntentRule

_PROJECTION_ALIAS_RE = re.compile(
    r"^(?P<expr>.+?)\s+AS\s+(?P<alias>[a-z_][a-z0-9_]*)$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _contains_non_trivial_projection_alias(select_list: str) -> bool:
    for part in split_select_list(select_list):
        match = _PROJECTION_ALIAS_RE.match(normalize_sql_text(part))
        if match is None:
            continue
        expr = normalize_sql_text(match.group("expr"))
        alias = normalize_sql_text(match.group("alias"))
        if expr.rsplit(".", 1)[-1].lower() != alias.lower():
            return True
    return False


class DynamicFilterSelectListCleanupIntentRule(DynamicCandidateIntentRule):
    rule_id = "DYNAMIC_FILTER_SELECT_LIST_TEMPLATE_EDIT"

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
            or profile.baseline_family != "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"
        ):
            return DynamicCandidateIntentMatch(rule_id=self.rule_id, matched=False)

        select_list, _ = parse_direct_select_template(str(sql_unit.get("templateSql") or ""))
        if select_list and _contains_non_trivial_projection_alias(select_list):
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="DYNAMIC_FILTER_SELECT_LIST_NON_TRIVIAL_ALIAS",
                details={"shapeFamily": profile.shape_family, "baselineFamily": profile.baseline_family},
            )

        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        namespace = str(sql_unit.get("namespace") or "").strip()
        rebuilt_template = None
        for strip_qualifiers in (False, True):
            candidate_template, changed = render_select_alias_cleanup_template(
                str(sql_unit.get("templateSql") or ""),
                strip_single_table_qualifiers=strip_qualifiers,
            )
            if not candidate_template or not changed:
                continue
            replayed = replay_template_sql(candidate_template, namespace, xml_path)
            if replayed is not None and normalize_sql_text(replayed) == normalize_sql_text(rewritten_sql):
                rebuilt_template = candidate_template
                break
        if rebuilt_template is None:
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                details={"shapeFamily": profile.shape_family, "baselineFamily": profile.baseline_family},
            )

        return DynamicCandidateIntentMatch(
            rule_id=self.rule_id,
            matched=True,
            intent="TEMPLATE_PRESERVING_STATEMENT_EDIT",
            rebuilt_template=rebuilt_template,
            details={"shapeFamily": profile.shape_family, "baselineFamily": profile.baseline_family},
        )
