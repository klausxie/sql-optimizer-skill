from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..errors import ConfigError

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

LEGACY_DOTTED_KEYS = {
    "project.root",
    "db.type",
    "runtime.scan_timeout_ms",
    "runtime.optimize_timeout_ms",
    "runtime.validate_timeout_ms",
    "runtime.apply_timeout_ms",
    "runtime.report_timeout_ms",
    "runtime.scan_retry_max",
    "runtime.optimize_retry_max",
    "runtime.validate_retry_max",
    "runtime.apply_retry_max",
    "runtime.report_retry_max",
}

REMOVED_KEYS = {
    "validate",
    "policy",
    "apply",
    "patch",
    "diagnostics",
    "runtime",
    "verification",
    "validate.sample_count",
    "validate.min_sample_rows_for_hash",
    "validate.db_unreachable_high_rate_threshold",
    "validate.key_columns",
    "validate.compare_columns",
    "scan.max_variants_per_statement",
    "scan.java_scanner",
    "scan.class_resolution",
    "scan.enable_fragment_catalog",
    "db.statement_timeout_ms",
    "db.allow_explain_analyze",
    "llm.retry",
    "llm.output_validation",
    "llm.executor",
    "llm.strict_required",
}


def check_snake_case(obj: Any, path: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            # Allow arbitrary HTTP header keys under llm.api_headers.
            if path.endswith("llm.api_headers."):
                check_snake_case(value, path + key + ".")
                continue
            # Allow rule-id keyed overrides under diagnostics.severity_overrides.
            if path.endswith("diagnostics.severity_overrides."):
                check_snake_case(value, path + key + ".")
                continue
            if not SNAKE_CASE_RE.match(key):
                raise ConfigError(f"config key not snake_case: {path + key}")
            check_snake_case(value, path + key + ".")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            check_snake_case(item, f"{path}[{i}].")


def load_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yml", ".yaml"}:
        if yaml is None:
            raise ConfigError("pyyaml is required for yaml config")
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ConfigError("config must be object")
    return data


def merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def required(config: dict[str, Any], dotted: str) -> None:
    node: Any = config
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            raise ConfigError(f"missing required config: {dotted}")
        node = node[key]


def has_key(config: dict[str, Any], dotted: str) -> bool:
    node: Any = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True
