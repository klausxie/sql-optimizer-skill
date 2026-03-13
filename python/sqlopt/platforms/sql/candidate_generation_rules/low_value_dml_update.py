from __future__ import annotations

import re

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import normalize_sql

_DML_START_RE = re.compile(r"^\s*(update|delete|insert)\b", flags=re.IGNORECASE)
_COALESCE_RE = re.compile(r"\bcoalesce\s*\(", flags=re.IGNORECASE)
_SUBQUERY_IN_RE = re.compile(r"\bin\s*\(\s*select\b", flags=re.IGNORECASE)
_LITERAL_IN_RE = re.compile(r"\bin\s*\(\s*'[^']+'", flags=re.IGNORECASE)
_ASSIGN_STRING_LITERAL_RE = re.compile(r"\bset\b.+?=\s*'[^']+'", flags=re.IGNORECASE | re.DOTALL)
_ANY_RE = re.compile(r"=\s*any\s*\(", flags=re.IGNORECASE)
_EXISTS_RE = re.compile(r"\bexists\s*\(\s*select\b", flags=re.IGNORECASE)
_UNNEST_RE = re.compile(r"\bunnest\s*\(", flags=re.IGNORECASE)
_NOW_RE = re.compile(r"\b(now|current_timestamp)\s*\(", flags=re.IGNORECASE)
_IN_PLACEHOLDER_RE = re.compile(r"\bin\s*#\{[a-z0-9_\.]+\}", flags=re.IGNORECASE)
_IN_PAREN_PLACEHOLDER_RE = re.compile(r"\bin\s*\(\s*#\{[a-z0-9_\.]+\}\s*\)", flags=re.IGNORECASE)
_MYBATIS_TAG_RE = re.compile(r"<\s*(foreach|if|choose|when|otherwise|trim|where|set)\b", flags=re.IGNORECASE)
_UPDATE_SET_RE = re.compile(
    r"^\s*update\s+[a-z_][a-z0-9_\.]*\s+set\s+(?P<set_clause>.+?)(?:\s+where\s+.+)?$",
    flags=re.IGNORECASE | re.DOTALL,
)
_STRATEGY_RE = re.compile(
    r"parameter_substitution|batch_optimization|null_safe_update|conditional_update|array_parameter|temp_table_cte|exists_subquery|in_to_any|in_to_exists|in_to_unnest_subquery|timestamp_auto_update|safe_update_guard|template_fix|null_safe_wrapper|dynamic_sql_fix|null_safe_rewrite|fix_syntax",
    flags=re.IGNORECASE,
)


class DmlUpdateSpeculativeRewriteRule:
    rule_id = "DML_UPDATE_SPECULATIVE_REWRITE"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        original_sql = normalize_sql(context.original_sql)
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or ""))
        strategy = str(candidate.get("rewriteStrategy") or "").strip()
        statement_type = str(context.sql_unit.get("statementType") or "").strip().upper()
        if statement_type != "UPDATE" and not _DML_START_RE.match(original_sql):
            return None
        if not rewritten_sql:
            return None

        if _STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DML_SPECULATIVE_REWRITE",
                reason="candidate rewrites update semantics on a dynamic DML template without a safe template-preserving baseline",
            )

        if _MYBATIS_TAG_RE.search(rewritten_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DML_SPECULATIVE_REWRITE",
                reason="candidate injects MyBatis control tags into update SQL text instead of preserving the original template structure",
            )

        if _COALESCE_RE.search(rewritten_sql) and not _COALESCE_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DML_SPECULATIVE_REWRITE",
                reason="candidate introduces COALESCE-based update semantics on a dynamic DML template",
            )

        if _SUBQUERY_IN_RE.search(rewritten_sql) and not _SUBQUERY_IN_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DML_SPECULATIVE_REWRITE",
                reason="candidate introduces a subquery-based collection rewrite on a dynamic DML template",
            )

        if (
            (_ANY_RE.search(rewritten_sql) and not _ANY_RE.search(original_sql))
            or (_EXISTS_RE.search(rewritten_sql) and not _EXISTS_RE.search(original_sql))
            or (_UNNEST_RE.search(rewritten_sql) and not _UNNEST_RE.search(original_sql))
        ):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DML_SPECULATIVE_REWRITE",
                reason="candidate rewrites a collection update predicate into ANY/EXISTS/UNNEST form that cannot map back to the template safely",
            )

        if _IN_PLACEHOLDER_RE.search(original_sql) and _IN_PAREN_PLACEHOLDER_RE.search(rewritten_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DML_SPECULATIVE_REWRITE",
                reason="candidate rewrites a foreach collection placeholder into a parenthesized single binding that cannot map back to the template safely",
            )

        if _LITERAL_IN_RE.search(rewritten_sql) and not _LITERAL_IN_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DML_SPECULATIVE_REWRITE",
                reason="candidate materializes a foreach collection update into literal values that cannot map back to the template safely",
            )

        if _ASSIGN_STRING_LITERAL_RE.search(rewritten_sql) and "#{" in original_sql and "#{" not in rewritten_sql:
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DML_SPECULATIVE_REWRITE",
                reason="candidate substitutes update bindings with literals on a dynamic DML template",
            )

        original_set_match = _UPDATE_SET_RE.match(original_sql)
        rewritten_set_match = _UPDATE_SET_RE.match(rewritten_sql)
        if original_set_match is not None and rewritten_set_match is not None:
            original_set = normalize_sql(original_set_match.group("set_clause") or "")
            rewritten_set = normalize_sql(rewritten_set_match.group("set_clause") or "")
            if original_set != rewritten_set and _NOW_RE.search(rewritten_set):
                return LowValueAssessment(
                    candidate_id=str(candidate.get("id") or ""),
                    rule_id=self.rule_id,
                    category="DML_SPECULATIVE_REWRITE",
                    reason="candidate injects runtime update expressions on a selective update template without a safe template-preserving baseline",
                )
        return None
