from __future__ import annotations

import re

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import normalize_sql

_DYNAMIC_FILTER_FEATURES = {"WHERE", "IF", "CHOOSE", "TRIM", "BIND"}
_HINT_RE = re.compile(r"/\*\+\s*.+?\*/", flags=re.IGNORECASE | re.DOTALL)
_HINT_STRATEGY_RE = re.compile(r"index|hint", flags=re.IGNORECASE)
_ORDER_STRATEGY_RE = re.compile(r"order", flags=re.IGNORECASE)
_TIME_FILTER_STRATEGY_RE = re.compile(r"time[_ ]?filter", flags=re.IGNORECASE)
_JOIN_REWRITE_STRATEGY_RE = re.compile(
    r"driving[_ ]?table|join[_ ]?reorder|reorder[_ ]?join|join[_ ]?order|push.*join",
    flags=re.IGNORECASE,
)
_PREDICATE_REWRITE_STRATEGY_RE = re.compile(
    r"ilike[_ ]?to[_ ]?like|standardize[_ ]?ilike|standardize[_ ]?like|simplify[_ ]?or|or[_ ]|coalesce[_ ]?null[_ ]?handling|coalesce|redundant[_ ]?condition[_ ]?optimization|redundant[_ ]?condition",
    flags=re.IGNORECASE,
)
_COUNT_REWRITE_STRATEGY_RE = re.compile(r"count[_ ]?to[_ ]?exists|exists", flags=re.IGNORECASE)
_WITH_RE = re.compile(r"^\s*with\b", flags=re.IGNORECASE)
_ORDER_BY_RE = re.compile(r"\border\s+by\b", flags=re.IGNORECASE)
_UNION_RE = re.compile(r"\bunion(?:\s+all)?\b", flags=re.IGNORECASE)
_LIMIT_RE = re.compile(r"\blimit\b|\bfetch\s+first\b", flags=re.IGNORECASE)
_JOIN_SUBQUERY_RE = re.compile(r"\bjoin\s*\(\s*select\b", flags=re.IGNORECASE)
_FROM_SUBQUERY_RE = re.compile(r"\bfrom\s*\(\s*select\b", flags=re.IGNORECASE)
_JOIN_CLAUSE_RE = re.compile(r"\bjoin\b.+?\bon\b(?P<on_clause>.+?)(?=\bjoin\b|\bwhere\b|\border\s+by\b|\blimit\b|\boffset\b|$)", flags=re.IGNORECASE | re.DOTALL)


def _extract_on_clauses(sql: str) -> list[str]:
    return [normalize_sql(match.group("on_clause") or "") for match in _JOIN_CLAUSE_RE.finditer(sql or "")]


def _dynamic_filter_features(context: CandidateGenerationContext) -> set[str]:
    features = {
        str(row).strip().upper()
        for row in (context.sql_unit.get("dynamicFeatures") or [])
        if str(row).strip()
    }
    trace = dict(context.sql_unit.get("dynamicTrace") or {})
    for row in (trace.get("statementFeatures") or []):
        feature = str(row).strip().upper()
        if feature:
            features.add(feature)
    return features


class DynamicFilterSpeculativeRewriteRule:
    rule_id = "DYNAMIC_FILTER_SPECULATIVE_REWRITE"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        features = _dynamic_filter_features(context)
        if not (features & _DYNAMIC_FILTER_FEATURES):
            return None

        original_sql = normalize_sql(context.original_sql)
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or ""))
        strategy = str(candidate.get("rewriteStrategy") or "").strip()
        if not original_sql or not rewritten_sql:
            return None

        if _HINT_RE.search(rewritten_sql) or _HINT_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate adds optimizer hints on a dynamic filter template without a stable template-preserving rewrite",
            )

        if rewritten_sql.startswith(f"{original_sql} AND ") or rewritten_sql.startswith(f"{original_sql} OR "):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate appends speculative predicates on a dynamic filter template",
            )

        if rewritten_sql.startswith(f"{original_sql} LIMIT ") or rewritten_sql.startswith(f"{original_sql} FETCH "):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate appends speculative pagination on a dynamic filter template",
            )

        if _LIMIT_RE.search(rewritten_sql) and not _LIMIT_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate introduces pagination on a dynamic filter template without a safe template-preserving baseline",
            )

        if _TIME_FILTER_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate introduces a time-based filter on a dynamic filter template without a safe template-preserving rewrite",
            )

        if _ORDER_BY_RE.search(rewritten_sql) and not _ORDER_BY_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate adds ordering on a dynamic filter template without a safe template-preserving rewrite",
            )

        if _ORDER_STRATEGY_RE.search(strategy) and normalize_sql(rewritten_sql) != normalize_sql(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate alters ordering on a dynamic filter template without a safe template-preserving rewrite",
            )

        if _JOIN_REWRITE_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate introduces a join-order or join-predicate rewrite on a dynamic filter template without a safe template-preserving baseline",
            )

        if _PREDICATE_REWRITE_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate rewrites dynamic filter predicates without a safe template-preserving baseline",
            )

        if _COUNT_REWRITE_STRATEGY_RE.search(strategy):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate rewrites count semantics on a dynamic filter template without a safe template-preserving baseline",
            )

        if _WITH_RE.search(rewritten_sql) and not _WITH_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate introduces a CTE-based structural rewrite on a dynamic filter template without a safe template-preserving baseline",
            )

        if _UNION_RE.search(rewritten_sql) and not _UNION_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate introduces a UNION-based structural rewrite on a dynamic filter template without a safe template-preserving baseline",
            )

        if (
            (_JOIN_SUBQUERY_RE.search(rewritten_sql) or _FROM_SUBQUERY_RE.search(rewritten_sql))
            and not (_JOIN_SUBQUERY_RE.search(original_sql) or _FROM_SUBQUERY_RE.search(original_sql))
        ):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate introduces a subquery pushdown rewrite on a dynamic filter template without a safe template-preserving baseline",
            )

        original_on_clauses = _extract_on_clauses(original_sql)
        rewritten_on_clauses = _extract_on_clauses(rewritten_sql)
        if (
            rewritten_on_clauses
            and any("#{"
                    in clause for clause in rewritten_on_clauses)
            and not any("#{" in clause for clause in original_on_clauses)
        ):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="DYNAMIC_FILTER_SPECULATIVE_REWRITE",
                reason="candidate pushes dynamic filter predicates into join conditions without a safe template-preserving baseline",
            )
        return None
