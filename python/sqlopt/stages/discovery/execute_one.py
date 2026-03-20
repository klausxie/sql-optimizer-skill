"""Discovery stage execute_one function.

Handles SQL unit discovery from MyBatis XML mapper files.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import stage_registry
from ...contracts import ContractValidator
from ...io_utils import append_jsonl, write_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from .scanner import Scanner


@stage_registry.register
class DiscoveryStage(Stage):
    """Discovery stage implementation for V8 architecture."""

    name: str = "discovery"
    version: str = "1.0.0"
    dependencies: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None, scanner: Any = None):
        self.config = config or {}
        self.scanner = scanner or Scanner(self.config)

    def execute(self, context: StageContext) -> StageResult:
        errors: list[str] = []
        warnings: list[str] = []
        output_files: list[Path] = []

        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        root_path = self.config.get("project", {}).get("root_path", run_dir)
        scan_result = self.scanner.scan(Path(root_path))
        all_sql_units = list(scan_result.sql_units)
        errors.extend(str(err) for err in (scan_result.errors or []))
        warnings.extend(str(w) for w in (scan_result.warnings or []))
        mapper_count = len({str(unit.get("xmlPath") or "") for unit in all_sql_units if unit.get("xmlPath")})

        for unit in all_sql_units:
            validator.validate("sqlunit", unit)

        write_jsonl(paths.scan_units_path, all_sql_units)
        output_files.append(paths.scan_units_path)

        log_event(
            paths.manifest_path,
            "discovery",
            "done",
            {
                "run_id": context.run_id,
                "mapper_count": mapper_count,
                "sql_unit_count": len(all_sql_units),
            },
        )

        return StageResult(
            success=len(errors) == 0,
            output_files=output_files,
            artifacts={
                "sql_units": all_sql_units,
                "sql_unit_count": len(all_sql_units),
                "mapper_count": mapper_count,
            },
            errors=errors,
            warnings=warnings,
        )

    def get_input_contracts(self) -> list[str]:
        return []

    def get_output_contracts(self) -> list[str]:
        return ["sqlunit"]

    def execute_one(
        self,
        run_id: str,
        ctx: StageContext,
        mapper_path: str | Path,
    ) -> DiscoveryResult:
        mapper_path = Path(mapper_path)
        start_time = datetime.now(timezone.utc)
        sql_units = self.scanner.scan_single(mapper_path)
        execution_time_ms = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000

        namespace = sql_units[0].get("namespace", "unknown") if sql_units else "unknown"
        result = DiscoveryResult(
            sql_units=sql_units,
            mapper_path=str(mapper_path),
            namespace=namespace,
            total_count=len(sql_units),
            execution_time_ms=execution_time_ms,
            trace={
                "stage": "discovery",
                "run_id": run_id,
                "mapper_path": str(mapper_path),
                "executor": "scanner",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        paths = canonical_paths(ctx.data_dir)
        validator = ContractValidator(Path(__file__).resolve().parents[2])
        for unit in sql_units:
            validator.validate("sqlunit", unit)
            append_jsonl(paths.scan_units_path, unit)

        log_event(
            paths.manifest_path,
            "discovery",
            "done",
            {
                "run_id": run_id,
                "mapper_path": str(mapper_path),
                "sql_unit_count": len(sql_units),
            },
        )
        return result

    def scan_mapper(self, mapper_path: str | Path) -> list[dict[str, Any]]:
        return self.scanner.scan_single(mapper_path)


@dataclass
class DiscoveryResult:
    """Result of discovery for a single mapper."""

    sql_units: list[dict[str, Any]]
    mapper_path: str
    namespace: str
    total_count: int
    execution_time_ms: float
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_one(
    run_id: str,
    mapper_path: str | Path,
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or {}
    paths = canonical_paths(run_dir)
    paths.ensure_layout()

    mapper_path = Path(mapper_path)
    scanner = Scanner(config)
    start_time = datetime.now(timezone.utc)
    sql_units = scanner.scan_single(mapper_path)
    execution_time_ms = (
        datetime.now(timezone.utc) - start_time
    ).total_seconds() * 1000

    for unit in sql_units:
        validator.validate("sqlunit", unit)
        append_jsonl(paths.scan_units_path, unit)

    namespace = sql_units[0].get("namespace", "unknown") if sql_units else "unknown"
    log_event(
        paths.manifest_path,
        "discovery",
        "done",
        {
            "run_id": run_id,
            "mapper_path": str(mapper_path),
            "sql_unit_count": len(sql_units),
        },
    )
    return {
        "mapperPath": str(mapper_path),
        "namespace": namespace,
        "sqlUnits": sql_units,
        "totalCount": len(sql_units),
        "executionTimeMs": execution_time_ms,
        "trace": {
            "stage": "discovery",
            "run_id": run_id,
            "mapper_path": str(mapper_path),
            "executor": "scanner",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
