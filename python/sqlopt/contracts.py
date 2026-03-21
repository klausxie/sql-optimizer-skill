from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ContractError

try:
    import jsonschema  # type: ignore
except Exception:  # pragma: no cover
    jsonschema = None

SCHEMA_MAP = {
    "sqlunit": "sqlunit.schema.json",
    "fragment_record": "fragment_record.schema.json",
    "optimization_proposal": "optimization_proposal.schema.json",
    "acceptance_result": "acceptance_result.schema.json",
    "patch_result": "patch_result.schema.json",
    "run_report": "run_report.schema.json",
    "ops_health": "ops_health.schema.json",
    "ops_topology": "ops_topology.schema.json",
    "run_index": "run_index.schema.json",
    "sql_artifact_index_row": "sql_artifact_index_row.schema.json",
    "verification_record": "verification_record.schema.json",
    "verification_summary": "verification_summary.schema.json",
    "baseline_result": "baseline_result.schema.json",
    "risks": "risks.schema.json",
}


@dataclass(frozen=True)
class StageBoundary:
    input_schemas: tuple[str, ...] = ()
    output_schemas: tuple[str, ...] = ()


# Canonical V9 boundaries used by the top-level workflow.
STAGE_BOUNDARIES: dict[str, StageBoundary] = {
    "init": StageBoundary(output_schemas=("sqlunit",)),
    # Parse materializes two artifacts: branched sqlunits and risk reports.
    "parse": StageBoundary(
        input_schemas=("sqlunit",), output_schemas=("sqlunit", "risks")
    ),
    "recognition": StageBoundary(
        input_schemas=("sqlunit",), output_schemas=("baseline_result",)
    ),
    # Optimize owns candidate generation + validation in V9, so patch only consumes optimize output.
    "optimize": StageBoundary(
        input_schemas=("baseline_result", "sqlunit"),
        output_schemas=("optimization_proposal",),
    ),
    "patch": StageBoundary(
        input_schemas=("optimization_proposal",), output_schemas=("patch_result",)
    ),
}

STAGE_NAMES = frozenset(STAGE_BOUNDARIES.keys())


def _resolve_contract_dir(repo_root: Path) -> Path:
    """Resolve contracts directory for both repo-local and installed runtime layouts."""
    candidates = [
        repo_root / "contracts",
        Path(__file__).resolve().parents[2] / "contracts",
    ]
    for candidate in candidates:
        if candidate.exists():
            schemas_dir = candidate / "schemas"
            if schemas_dir.exists():
                return schemas_dir
            return candidate
    return candidates[0]


class ContractValidator:
    def __init__(self, repo_root: Path):
        self.contract_dir = _resolve_contract_dir(repo_root)
        self._schemas: dict[str, dict[str, Any]] = {}

    def _schema(self, name: str) -> dict[str, Any]:
        if name not in SCHEMA_MAP:
            raise ContractError(f"unknown schema: {name}")
        if name not in self._schemas:
            path = self.contract_dir / SCHEMA_MAP[name]
            self._schemas[name] = json.loads(path.read_text(encoding="utf-8"))
        return self._schemas[name]

    def validate(self, name: str, payload: Any) -> None:
        schema = self._schema(name)
        self._validate_against_schema(schema, payload, label=name)

    def get_stage_schema(self, stage_name: str, io_type: str) -> dict[str, Any] | None:
        if stage_name not in STAGE_BOUNDARIES:
            raise ContractError(
                f"unknown stage: {stage_name}; valid stages: {sorted(STAGE_NAMES)}"
            )
        if io_type not in ("input", "output"):
            raise ContractError(f"io_type must be 'input' or 'output', got: {io_type}")
        boundary = STAGE_BOUNDARIES[stage_name]
        schema_names = (
            boundary.input_schemas if io_type == "input" else boundary.output_schemas
        )
        if not schema_names:
            return None
        if len(schema_names) == 1:
            return self._schema(schema_names[0])
        return {"anyOf": [self._schema(name) for name in schema_names]}

    def validate_stage_input(self, stage_name: str, data: Any) -> None:
        self._validate_stage_io(stage_name, "input", data)

    def validate_stage_output(self, stage_name: str, data: Any) -> None:
        self._validate_stage_io(stage_name, "output", data)

    def _validate_stage_io(self, stage_name: str, io_type: str, data: Any) -> None:
        if stage_name not in STAGE_BOUNDARIES:
            raise ContractError(
                f"unknown stage: {stage_name}; valid stages: {sorted(STAGE_NAMES)}"
            )
        boundary = STAGE_BOUNDARIES[stage_name]
        schema_names = (
            boundary.input_schemas if io_type == "input" else boundary.output_schemas
        )
        if not schema_names:
            return
        errors: list[str] = []
        for schema_name in schema_names:
            schema = self._schema(schema_name)
            try:
                self._validate_against_schema(
                    schema,
                    data,
                    label=f"stage '{stage_name}' {io_type}",
                )
                return
            except ContractError as exc:
                errors.append(f"{schema_name}: {exc}")
        allowed = ", ".join(schema_names)
        detail = "; ".join(errors)
        raise ContractError(
            f"stage '{stage_name}' {io_type} validation failed against allowed schemas [{allowed}]: {detail}"
        )

    def _validate_against_schema(
        self, schema: dict[str, Any], payload: Any, *, label: str
    ) -> None:
        if jsonschema is not None:
            try:
                jsonschema.validate(instance=payload, schema=schema)
            except Exception as exc:
                path = _extract_error_path(exc)
                raise ContractError(f"{label} validation failed{path}: {exc}") from exc
            return
        if schema.get("type") == "object" and isinstance(payload, dict):
            missing = [k for k in schema.get("required", []) if k not in payload]
            if missing:
                raise ContractError(f"{label} missing required fields: {missing}")
            return
        raise ContractError(f"jsonschema dependency missing; cannot validate {label}")


def _extract_error_path(exc: Exception) -> str:
    if jsonschema is None:
        return ""
    if isinstance(exc, jsonschema.ValidationError):
        path = ".".join(str(p) for p in exc.path)
        if path:
            return f" at path '{path}'"
    return ""
