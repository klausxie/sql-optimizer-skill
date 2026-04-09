from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ...io_utils import ensure_dir

_FINGERPRINT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_VOLATILE_KEYS = {
    "createdAt",
    "created_at",
    "runId",
    "run_id",
    "tempPath",
    "temp_path",
    "tmpPath",
    "tmp_path",
    "timestamp",
    "time",
    "host",
    "hostname",
    "machine",
    "machineId",
    "machine_id",
    "workspace",
    "workingDir",
    "working_dir",
    "cwd",
}
_PATHLIKE_KEY_PARTS = ("path", "dir", "cwd", "workspace", "home")
_RAW_REQUIRED_FIELDS = frozenset(
    {
        "fingerprint",
        "provider",
        "model",
        "promptVersion",
        "sqlKey",
        "request",
        "response",
        "createdAt",
    }
)
_NORMALIZED_REQUIRED_FIELDS = frozenset(
    {
        "fingerprint",
        "sqlKey",
        "rawCandidateCount",
        "validCandidates",
        "trace",
    }
)


@dataclass(frozen=True)
class CassetteMiss:
    path: Path
    fingerprint: str
    cassette_kind: str


class CassetteFormatError(ValueError):
    pass


def _normalize_sql_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_dynamic_features(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple, set)):
        raise CassetteFormatError("dynamicFeatures must be a list-like collection of feature names")
    features = {str(item).strip() for item in (value or []) if str(item).strip()}
    return sorted(features)


def _normalize_stable_value(value: Any, *, key_hint: str | None = None) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str) and key_hint and any(part in key_hint.lower() for part in _PATHLIKE_KEY_PARTS):
            stripped = value.strip()
            if stripped.startswith("/") or stripped.startswith("~") or re.match(r"^[A-Za-z]:[\\/]", stripped):
                return "<path>"
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, tuple):
        return [_normalize_stable_value(item, key_hint=key_hint) for item in value]
    if isinstance(value, list):
        return [_normalize_stable_value(item, key_hint=key_hint) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, raw_val in sorted(value.items(), key=lambda kv: str(kv[0])):
            key_text = str(key)
            if key_text in _VOLATILE_KEYS:
                continue
            normalized[key_text] = _normalize_stable_value(raw_val, key_hint=key_text)
        return normalized
    return str(value)


def build_optimize_cassette_fingerprint_input(request: Mapping[str, Any]) -> dict[str, Any]:
    stable_db_evidence = request.get("stableDbEvidence")
    return {
        "sqlKey": str(request.get("sqlKey") or ""),
        "sql": _normalize_sql_text(request.get("sql")),
        "templateSql": _normalize_sql_text(request.get("templateSql")),
        "dynamicFeatures": _normalize_dynamic_features(request.get("dynamicFeatures")),
        "stableDbEvidence": _normalize_stable_value(stable_db_evidence or {}),
        "retryContext": _normalize_stable_value(request.get("retryContext") or {}),
        "promptVersion": str(request.get("promptVersion") or ""),
        "provider": str(request.get("provider") or ""),
        "model": str(request.get("model") or ""),
    }


def fingerprint_optimize_cassette_input(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_fingerprint(fingerprint: str) -> str:
    text = str(fingerprint).strip()
    if not text or not _FINGERPRINT_RE.fullmatch(text):
        raise CassetteFormatError(f"unsafe cassette fingerprint: {fingerprint!r}")
    return text


def _cassette_path(root: Path, cassette_kind: str, fingerprint: str) -> Path:
    kind = str(cassette_kind).strip().lower()
    if kind not in {"raw", "normalized"}:
        raise CassetteFormatError(f"unsupported cassette kind: {cassette_kind!r}")
    return root / "optimize" / kind / f"{_validate_fingerprint(fingerprint)}.json"


def optimize_raw_cassette_path(root: Path, fingerprint: str) -> Path:
    return _cassette_path(root, "raw", fingerprint)


def optimize_normalized_cassette_path(root: Path, fingerprint: str) -> Path:
    return _cassette_path(root, "normalized", fingerprint)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _required_fields_for_kind(cassette_kind: str) -> frozenset[str]:
    kind = str(cassette_kind).strip().lower()
    if kind == "raw":
        return _RAW_REQUIRED_FIELDS
    if kind == "normalized":
        return _NORMALIZED_REQUIRED_FIELDS
    raise CassetteFormatError(f"unsupported cassette kind: {cassette_kind!r}")


def _validate_cassette_payload(cassette_kind: str, payload: Mapping[str, Any]) -> None:
    missing = sorted(field for field in _required_fields_for_kind(cassette_kind) if field not in payload)
    if missing:
        raise CassetteFormatError(
            f"{cassette_kind} cassette missing required fields: {', '.join(missing)}"
        )


def save_optimize_cassette(root: Path, cassette_kind: str, fingerprint: str, payload: Mapping[str, Any]) -> None:
    _validate_cassette_payload(cassette_kind, payload)
    _write_json(_cassette_path(root, cassette_kind, fingerprint), payload)


def load_optimize_cassette(root: Path, cassette_kind: str, fingerprint: str) -> dict[str, Any] | CassetteMiss:
    path = _cassette_path(root, cassette_kind, fingerprint)
    if not path.exists():
        return CassetteMiss(path=path, fingerprint=fingerprint, cassette_kind=str(cassette_kind).strip().lower())
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CassetteFormatError(f"failed to load cassette at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CassetteFormatError(f"cassette at {path} must contain a JSON object")
    _validate_cassette_payload(cassette_kind, payload)
    return payload
