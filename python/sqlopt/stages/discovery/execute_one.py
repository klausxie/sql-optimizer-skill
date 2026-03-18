"""Discovery stage execute_one function.

Handles SQL unit discovery from MyBatis XML mapper files.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import StageContext
from .scanner import Scanner


@dataclass
class DiscoveryResult:
    """Result of discovery for a single mapper."""

    sql_units: list[dict[str, Any]]
    mapper_path: str
    namespace: str
    total_count: int
    execution_time_ms: float
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_one(
    run_id: str,
    mapper_path: str | Path,
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute discovery for a single Mapper XML file.

    Args:
        run_id: Run identifier
        mapper_path: Path to Mapper XML file
        run_dir: Run directory
        validator: Contract validator
        config: Optional configuration

    Returns:
        Discovery result dictionary with sql_units
    """
    config = config or {}
    paths = canonical_paths(run_dir)

    mapper_path = Path(mapper_path)
    scanner = Scanner(config)

    start_time = datetime.now(timezone.utc)

    # Scan single mapper file
    sql_units = scanner.scan_single(mapper_path)

    end_time = datetime.now(timezone.utc)
    execution_time_ms = (end_time - start_time).total_seconds() * 1000

    # Extract namespace from first unit or default
    namespace = "unknown"
    if sql_units:
        namespace = sql_units[0].get("namespace", "unknown")

    discovery_result = {
        "sqlUnits": sql_units,
        "mapperPath": str(mapper_path),
        "namespace": namespace,
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

    # Validate against sqlunit schema
    for unit in sql_units:
        validator.validate("sqlunit", unit)

    # Append to scan results file
    append_jsonl(paths.scan_units_path, discovery_result)

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

    return discovery_result


class DiscoveryStage:
    """Discovery stage wrapper for V8 architecture."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.scanner = Scanner(config)

    def execute_one(
        self,
        run_id: str,
        ctx: StageContext,
        mapper_path: str | Path,
    ) -> DiscoveryResult:
        """Execute discovery for a single Mapper XML.

        Args:
            run_id: Run identifier
            ctx: Stage context
            mapper_path: Path to Mapper XML file

        Returns:
            DiscoveryResult object
        """
        mapper_path = Path(mapper_path)

        start_time = datetime.now(timezone.utc)
        sql_units = self.scanner.scan_single(mapper_path)
        end_time = datetime.now(timezone.utc)

        execution_time_ms = (end_time - start_time).total_seconds() * 1000

        namespace = "unknown"
        if sql_units:
            namespace = sql_units[0].get("namespace", "unknown")

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

        # Persist to run directory
        run_dir = ctx.data_dir
        paths = canonical_paths(run_dir)

        for unit in sql_units:
            validator = ContractValidator(Path(__file__).resolve().parents[2])
            validator.validate("sqlunit", unit)

        append_jsonl(paths.scan_units_path, result.to_dict())

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
        """Scan a single Mapper XML file.

        Args:
            mapper_path: Path to Mapper XML file

        Returns:
            List of SQL unit dictionaries
        """
        return self.scanner.scan_single(mapper_path)
