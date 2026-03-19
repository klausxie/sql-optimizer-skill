"""Discovery stage execute_one function.

Handles SQL unit discovery from MyBatis XML mapper files.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...application.stage_registry import StageRegistry, stage_registry
from ...contracts import ContractValidator, STAGE_BOUNDARIES
from ...io_utils import append_jsonl
from ...manifest import log_event
from ...run_paths import canonical_paths
from ..base import Stage, StageContext, StageResult
from .scanner import Scanner


@stage_registry.register
class DiscoveryStage(Stage):
    """Discovery stage implementation for V8 architecture.

    Discovers SQL units from MyBatis XML mapper files.
    """

    name: str = "discovery"
    version: str = "1.0.0"
    dependencies: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None, scanner: Any = None):
        self.config = config or {}
        self.scanner = scanner or Scanner(config)

    def execute(self, context: StageContext) -> StageResult:
        """Execute the discovery stage.

        Args:
            context: Stage execution context containing run_id, config, and data_dir

        Returns:
            StageResult with discovery artifacts
        """
        errors: list[str] = []
        warnings: list[str] = []
        artifacts: dict[str, Any] = {}
        output_files: list[Path] = []

        run_dir = context.data_dir
        paths = canonical_paths(run_dir)
        validator = ContractValidator(Path(__file__).resolve().parents[2])

        # Get mapper globs from config
        mapper_globs = self.config.get("scan", {}).get("mapper_globs", ["**/*.xml"])

        # Get root path from config or use data_dir
        root_path = self.config.get("project", {}).get("root_path", run_dir)
        root = Path(root_path)

        # Find all mapper files
        mapper_files: list[Path] = []
        for pattern in mapper_globs:
            for f in root.glob(pattern):
                if f.is_file() and f.suffix == ".xml":
                    mapper_files.append(f)

        mapper_files = sorted(set(mapper_files))

        if not mapper_files:
            warnings.append("no mapper files found matching globs")

        all_sql_units: list[dict[str, Any]] = []

        for mapper_path in mapper_files:
            try:
                sql_units = self.scanner.scan_single(mapper_path)

                # Validate each SQL unit against schema
                for unit in sql_units:
                    try:
                        validator.validate("sqlunit", unit)
                    except Exception as e:
                        errors.append(f"validation error in {mapper_path}: {e}")

                all_sql_units.extend(sql_units)

                # Log event for each mapper
                log_event(
                    paths.manifest_path,
                    "discovery",
                    "mapper_done",
                    {
                        "run_id": context.run_id,
                        "mapper_path": str(mapper_path),
                        "sql_unit_count": len(sql_units),
                    },
                )

            except Exception as e:
                errors.append(f"error scanning {mapper_path}: {e}")

        # Build discovery result
        discovery_result = {
            "sqlUnits": all_sql_units,
            "mapperCount": len(mapper_files),
            "totalCount": len(all_sql_units),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Persist to scan results file
        append_jsonl(paths.scan_units_path, discovery_result)
        output_files.append(paths.scan_units_path)

        # Log completion
        log_event(
            paths.manifest_path,
            "discovery",
            "done",
            {
                "run_id": context.run_id,
                "mapper_count": len(mapper_files),
                "sql_unit_count": len(all_sql_units),
            },
        )

        # Build artifacts
        artifacts = {
            "sql_units": all_sql_units,
            "mapper_count": len(mapper_files),
            "total_count": len(all_sql_units),
        }

        return StageResult(
            success=len(errors) == 0,
            output_files=output_files,
            artifacts=artifacts,
            errors=errors,
            warnings=warnings,
        )

    def get_input_contracts(self) -> list[str]:
        """Discovery has no input contracts (first stage).

        Returns:
            Empty list since discovery is the first stage
        """
        return []

    def get_output_contracts(self) -> list[str]:
        """Discovery outputs sqlunit contracts.

        Returns:
            List containing "sqlunit"
        """
        return ["sqlunit"]

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

        validator = ContractValidator(Path(__file__).resolve().parents[2])
        for unit in sql_units:
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
