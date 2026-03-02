from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

CheckDbConnectivityFn = Callable[[dict[str, Any]], dict[str, Any]]
CollectSqlEvidenceFn = Callable[[dict[str, Any], str], tuple[dict[str, Any], dict[str, Any]]]
CompareSqlFn = Callable[[dict[str, Any], str, str, Path], dict[str, Any]]


@dataclass(frozen=True)
class PlatformCapabilities:
    supports_connectivity_check: bool = True
    supports_plan_compare: bool = True
    supports_semantic_compare: bool = True
    supports_sql_evidence: bool = True


class PlatformAdapter(Protocol):
    @property
    def capabilities(self) -> PlatformCapabilities: ...

    def check_db_connectivity(self, config: dict[str, Any]) -> dict[str, Any]: ...

    def collect_sql_evidence(self, config: dict[str, Any], sql: str) -> tuple[dict[str, Any], dict[str, Any]]: ...

    def compare_plan(self, config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]: ...

    def compare_semantics(self, config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]: ...


@dataclass(frozen=True)
class FunctionPlatformAdapter:
    name: str
    capabilities: PlatformCapabilities
    check_db_connectivity_fn: CheckDbConnectivityFn
    collect_sql_evidence_fn: CollectSqlEvidenceFn
    compare_plan_fn: CompareSqlFn
    compare_semantics_fn: CompareSqlFn

    def check_db_connectivity(self, config: dict[str, Any]) -> dict[str, Any]:
        return self.check_db_connectivity_fn(config)

    def collect_sql_evidence(self, config: dict[str, Any], sql: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.collect_sql_evidence_fn(config, sql)

    def compare_plan(self, config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
        return self.compare_plan_fn(config, original_sql, rewritten_sql, evidence_dir)

    def compare_semantics(self, config: dict[str, Any], original_sql: str, rewritten_sql: str, evidence_dir: Path) -> dict[str, Any]:
        return self.compare_semantics_fn(config, original_sql, rewritten_sql, evidence_dir)
