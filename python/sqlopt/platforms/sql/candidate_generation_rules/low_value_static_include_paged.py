from __future__ import annotations

import re

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import PAGED_RE, normalize_sql

_WHERE_RE = re.compile(r"\bwhere\b", flags=re.IGNORECASE)
_OFFSET_ZERO_RE = re.compile(r"\boffset\s+0\b", flags=re.IGNORECASE)
_OFFSET_RE = re.compile(r"\boffset\b", flags=re.IGNORECASE)
_FETCH_FIRST_RE = re.compile(r"\bfetch\s+first\s+\d+\s+rows\s+only\b", flags=re.IGNORECASE)
_LIMIT_LITERAL_RE = re.compile(r"\blimit\s+\d+\b", flags=re.IGNORECASE)
_ORDER_BY_RE = re.compile(r"\border\s+by\b", flags=re.IGNORECASE)


class StaticIncludePagedSpeculativeFilterRule:
    rule_id = "STATIC_INCLUDE_PAGED_SPECULATIVE_FILTER"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        features = {
            str(row).strip().upper()
            for row in (context.sql_unit.get("dynamicFeatures") or [])
            if str(row).strip()
        }
        if features != {"INCLUDE"}:
            return None

        original_sql = normalize_sql(context.original_sql)
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or ""))
        if not original_sql or not rewritten_sql:
            return None
        original_is_paged = bool(PAGED_RE.search(original_sql))
        if original_is_paged and not _OFFSET_RE.search(original_sql) and _OFFSET_ZERO_RE.search(rewritten_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="CANONICAL_NOOP_HINT",
                reason="candidate only adds an explicit OFFSET 0 to a static include paged statement without a material change",
            )
        if (
            not original_is_paged
            and (_LIMIT_LITERAL_RE.search(rewritten_sql) or _FETCH_FIRST_RE.search(rewritten_sql))
            and not _LIMIT_LITERAL_RE.search(original_sql)
            and not _FETCH_FIRST_RE.search(original_sql)
        ):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate adds speculative pagination to a static include statement without a safe baseline rewrite",
            )
        if _WHERE_RE.search(original_sql):
            return None
        if _WHERE_RE.search(rewritten_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate adds speculative filters to a static include statement without a safe baseline rewrite",
            )
        if original_is_paged and _FETCH_FIRST_RE.search(rewritten_sql) and not _FETCH_FIRST_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate rewrites static include pagination into an explicit FETCH FIRST clause without a safe template-preserving rewrite",
            )
        if (
            not _WHERE_RE.search(original_sql)
            and _WHERE_RE.search(rewritten_sql)
            and _ORDER_BY_RE.search(rewritten_sql)
            and (_LIMIT_LITERAL_RE.search(rewritten_sql) or _FETCH_FIRST_RE.search(rewritten_sql))
        ):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate adds speculative filters and repagination to a static include statement without a safe baseline rewrite",
            )
        return None
