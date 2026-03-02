from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class PlatformAdapter(Protocol):
    def check_db_connectivity(self, config: dict[str, Any]) -> dict[str, Any]: ...

    def collect_sql_evidence(self, config: dict[str, Any], sql: str) -> tuple[dict[str, Any], dict[str, Any]]: ...

    def compare_plan(self, config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]: ...

    def compare_semantics(self, config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]: ...

