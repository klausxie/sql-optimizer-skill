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
    "sqlunit": "stages/sqlunit.schema.json",
    "fragment_record": "stages/fragment_record.schema.json",
    "optimization_proposal": "stages/optimization_proposal.schema.json",
    "acceptance_result": "stages/acceptance_result.schema.json",
    "patch_result": "stages/patch_result.schema.json",
    "run_report": "run/run_report.schema.json",
    "run_index": "run/run_index.schema.json",
    "sql_artifact_index_row": "sql/sql_artifact_index_row.schema.json",
}


def _resolve_local_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ContractError(f"jsonschema dependency missing; cannot resolve external schema ref {ref}")
    current: Any = root_schema
    for part in ref[2:].split("/"):
        if not isinstance(current, dict) or part not in current:
            raise ContractError(f"jsonschema dependency missing; cannot resolve schema ref {ref}")
        current = current[part]
    if not isinstance(current, dict):
        raise ContractError(f"jsonschema dependency missing; invalid schema ref {ref}")
    return current


def _validate_required_fields_fallback(
    schema: dict[str, Any],
    payload: Any,
    path: str = "$",
    root_schema: dict[str, Any] | None = None,
) -> None:
    root = root_schema or schema
    if "$ref" in schema:
        _validate_required_fields_fallback(_resolve_local_ref(root, str(schema["$ref"])), payload, path, root)
        return
    schema_type = schema.get("type")
    allowed_types = set(schema_type) if isinstance(schema_type, list) else {schema_type}
    if payload is None and "null" in allowed_types:
        return
    if "object" in allowed_types and isinstance(payload, dict):
        missing = [key for key in schema.get("required", []) if key not in payload]
        if missing:
            raise ContractError(f"{path} missing required fields: {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = [key for key in payload.keys() if key not in properties]
            if unexpected:
                raise ContractError(f"{path} contains unexpected fields: {unexpected}")
        for key, subschema in properties.items():
            if key in payload and isinstance(subschema, dict):
                _validate_required_fields_fallback(subschema, payload[key], f"{path}.{key}", root)
        return
    if "array" in allowed_types and isinstance(payload, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(payload):
                _validate_required_fields_fallback(item_schema, item, f"{path}[{index}]", root)
        return


def _resolve_contract_dir(repo_root: Path) -> Path:
    """Resolve contracts directory for both repo-local and installed runtime layouts."""
    candidates = [
        repo_root / "contracts",
        Path(__file__).resolve().parents[2] / "contracts",
    ]
    for candidate in candidates:
        if candidate.exists():
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
                validator_cls = jsonschema.validators.validator_for(schema)
                validator_cls.check_schema(schema)
                validator = validator_cls(schema)
                validator.validate(payload)
            except Exception as exc:
                raise ContractError(f"{name} schema validation failed: {exc}") from exc
            return
        try:
            _validate_required_fields_fallback(schema, payload)
        except ContractError as exc:
            raise ContractError(f"{name} schema validation failed: {exc}") from exc
