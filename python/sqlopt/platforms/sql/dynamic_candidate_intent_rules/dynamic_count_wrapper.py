from __future__ import annotations

import re
from pathlib import Path

from ..dynamic_candidate_intent_models import DynamicCandidateIntentMatch
from ..dynamic_template_support import replay_template_sql
from ..rewrite_facts_models import RewriteFacts
from ..template_rendering import normalize_sql_text
from .base import DynamicCandidateIntentRule

_COUNT_SQL_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+(?P<from_suffix>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_COUNT_WRAPPER_TEMPLATE_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+from\s*\(\s*(?P<inner>.+)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_SELECT_FROM_RE = re.compile(r"^\s*select\s+.+?\s+(?P<from_suffix>from\b.+)$", flags=re.IGNORECASE | re.DOTALL)


def _extract_count_from_suffix(sql: str) -> tuple[str | None, str | None]:
    match = _COUNT_SQL_RE.match(str(sql or "").strip())
    if not match:
        return None, None
    return normalize_sql_text(match.group("count_expr")) or None, normalize_sql_text(match.group("from_suffix")) or None


def _extract_template_from_suffix(template_sql: str) -> str | None:
    match = _SELECT_FROM_RE.match(str(template_sql or "").strip())
    if not match:
        return None
    return str(match.group("from_suffix") or "").strip() or None


def _normalize_count_sql(sql: str) -> str:
    count_expr, from_suffix = _extract_count_from_suffix(sql)
    if count_expr in {"1", "*"} and from_suffix:
        return normalize_sql_text(f"SELECT COUNT(*) {from_suffix}")
    return normalize_sql_text(sql)


class DynamicCountWrapperIntentRule(DynamicCandidateIntentRule):
    rule_id = "DYNAMIC_FILTER_COUNT_WRAPPER_TEMPLATE_EDIT"

    def evaluate(
        self,
        sql_unit: dict[str, object],
        original_sql: str,
        rewritten_sql: str,
        rewrite_facts: RewriteFacts,
    ) -> DynamicCandidateIntentMatch:
        _ = original_sql
        profile = rewrite_facts.dynamic_template.capability_profile
        if not rewrite_facts.dynamic_template.present or profile.shape_family != "IF_GUARDED_COUNT_WRAPPER":
            return DynamicCandidateIntentMatch(rule_id=self.rule_id, matched=False)

        template_sql = str(sql_unit.get("templateSql") or "")
        template_match = _COUNT_WRAPPER_TEMPLATE_RE.match(template_sql.strip())
        rewritten_count_expr, rewritten_from_suffix = _extract_count_from_suffix(rewritten_sql)
        inner_template = str((template_match.group("inner") if template_match else "") or "").strip()
        inner_from_suffix_template = _extract_template_from_suffix(inner_template)
        if template_match is None or inner_from_suffix_template is None or rewritten_from_suffix is None:
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                details={"shapeFamily": profile.shape_family},
            )

        rebuilt_template = f"SELECT COUNT(*) {inner_from_suffix_template}".strip()
        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        namespace = str(sql_unit.get("namespace") or "").strip()
        statement_id = str(sql_unit.get("statementId") or "").strip()
        if not xml_path.exists() or not statement_id:
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                details={"shapeFamily": profile.shape_family},
            )
        replayed = replay_template_sql(rebuilt_template, namespace, xml_path)
        if replayed is None:
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                details={"shapeFamily": profile.shape_family},
            )
        if rewritten_count_expr not in {"1", "*"}:
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                rebuilt_template=rebuilt_template,
                details={"shapeFamily": profile.shape_family},
            )

        if _normalize_count_sql(replayed or "") != _normalize_count_sql(rewritten_sql):
            return DynamicCandidateIntentMatch(
                rule_id=self.rule_id,
                matched=True,
                intent="UNSAFE_DYNAMIC_REWRITE",
                blocking_reason="NO_TEMPLATE_PRESERVING_INTENT",
                rebuilt_template=rebuilt_template,
                details={"shapeFamily": profile.shape_family},
            )

        return DynamicCandidateIntentMatch(
            rule_id=self.rule_id,
            matched=True,
            intent="TEMPLATE_PRESERVING_STATEMENT_EDIT",
            rebuilt_template=rebuilt_template,
            details={"shapeFamily": profile.shape_family},
        )
