from __future__ import annotations

from typing import Any

from .canonicalization_engine import assess_candidate_canonicalization_model


def assess_candidate_canonicalization(original_sql: str, rewritten_sql: str, semantics: dict[str, Any]) -> dict[str, Any]:
    return assess_candidate_canonicalization_model(original_sql, rewritten_sql, semantics).to_dict()
