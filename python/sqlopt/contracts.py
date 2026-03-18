from __future__ import annotations

import json
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
}


def _resolve_contract_dir(repo_root: Path) -> Path:
    """Resolve contracts directory for both repo-local and installed runtime layouts."""
    candidates = [
        repo_root / "contracts",
        Path(__file__).resolve().parents[2] / "contracts",
    ]
    for candidate in candidates:
        if candidate.exists():
            # Check if schemas are in subdirectory
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
        if jsonschema is not None:
            try:
                jsonschema.validate(instance=payload, schema=schema)
            except Exception as exc:
                raise ContractError(f"{name} schema validation failed: {exc}") from exc
            return
        if schema.get("type") == "object" and isinstance(payload, dict):
            missing = [k for k in schema.get("required", []) if k not in payload]
            if missing:
                raise ContractError(f"{name} missing required fields: {missing}")
        else:
            raise ContractError(
                f"jsonschema dependency missing; cannot validate {name}"
            )
