from __future__ import annotations

from pathlib import Path
from typing import Any

from .compare import compare_plan as _compare_plan
from .compare import compare_semantics as _compare_semantics
from .evidence import check_db_connectivity as _check_db_connectivity
from .evidence import collect_sql_evidence as _collect_sql_evidence


def check_db_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    return _check_db_connectivity(config)


def collect_sql_evidence(config: dict[str, Any], sql: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return _collect_sql_evidence(config, sql)


def compare_plan(config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
    return _compare_plan(config, original_sql, rewritten_sql, evidence_dir)


def compare_semantics(config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
    return _compare_semantics(config, original_sql, rewritten_sql, evidence_dir)
