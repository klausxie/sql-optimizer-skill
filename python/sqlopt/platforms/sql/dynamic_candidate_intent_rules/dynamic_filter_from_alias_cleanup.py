from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..dynamic_candidate_intent_models import DynamicCandidateIntentMatch
from ..dynamic_template_support import parse_direct_select_template, render_from_alias_cleanup_template, replay_template_sql
from ..rewrite_facts_models import RewriteFacts
from ..template_rendering import normalize_sql_text
from .base import DynamicCandidateIntentRule

_FROM_ALIAS_RE = re.compile(
    r"^\s*from\s+(?P<table>[a-z_][a-z0-9_\.]*)\s+(?:as\s+)?(?P<alias>[a-z_][a-z0-9_]*)(?P<suffix>.*)?$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _extract_from_alias(from_suffix: str) -> str | None:
    match = _FROM_ALIAS_RE.match(normalize_sql_text(from_suffix))
    if match is None:
        return None
    alias = str(match.group("alias") or "").strip()
    return alias or None


def _if_inner_template(node: ET.Element) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        parts.append(ET.tostring(child, encoding="unicode"))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _requires_if_predicate_rewrite(template_sql: str) -> bool:
    _select_list, from_suffix = parse_direct_select_template(template_sql)
    if not from_suffix:
        return False
    alias = _extract_from_alias(from_suffix)
    if not alias:
        return False
    alias_ref = f"{alias.lower()}."
    try:
        wrapper = ET.fromstring(f"<root>{template_sql}</root>")
    except ET.ParseError:
        return False
    for node in wrapper.iter():
        if str(node.tag).rsplit("}", 1)[-1].lower() != "if":
            continue
        if alias_ref in normalize_sql_text(_if_inner_template(node)).lower():
            return True
    return False


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

        if _requires_if_predicate_rewrite(str(sql_unit.get("templateSql") or "")):
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="DYNAMIC_FILTER_FROM_ALIAS_REQUIRES_PREDICATE_REWRITE",
                details={"shapeFamily": profile.shape_family, "baselineFamily": profile.baseline_family},
            )

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
