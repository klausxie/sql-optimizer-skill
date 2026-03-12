from __future__ import annotations

from typing import Any

from .candidate_generation_engine import evaluate_candidate_generation
from .candidate_generation_support import recover_candidates_from_shape, recover_candidates_from_text


def build_candidate_generation_diagnostics(
    *,
    sql_key: str,
    original_sql: str,
    raw_candidates: list[dict[str, Any]],
    valid_candidates: list[dict[str, Any]],
    trace: dict[str, Any],
    sql_unit: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    outcome = evaluate_candidate_generation(
        sql_key=sql_key,
        original_sql=original_sql,
        sql_unit=sql_unit or {"dynamicFeatures": []},
        raw_candidates=raw_candidates,
        valid_candidates=valid_candidates,
        trace=trace,
    )
    return outcome.diagnostics.to_summary_dict(), outcome.recovery_candidates


__all__ = [
    "build_candidate_generation_diagnostics",
    "recover_candidates_from_shape",
    "recover_candidates_from_text",
]

