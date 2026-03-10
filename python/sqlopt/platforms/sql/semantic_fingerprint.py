from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(val) for key, val in sorted(value.items(), key=lambda kv: str(kv[0]))}
    return str(value)


def hash_rows(rows: Iterable[Any]) -> str:
    row_hashes: list[str] = []
    for row in rows:
        normalized_row = _normalize_value(row)
        payload = json.dumps(normalized_row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        row_hashes.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())
    row_hashes.sort()
    joined = json.dumps(row_hashes, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_fingerprint_evidence(
    *,
    fingerprint_key: str,
    expected_rows: list[Any],
    observed_rows: list[Any],
    match_strength_on_match: str,
    notes: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_hash = hash_rows(expected_rows)
    observed_hash = hash_rows(observed_rows)
    status = "MATCH" if expected_hash == observed_hash else "MISMATCH"
    evidence: dict[str, Any] = {
        "source": "DB_FINGERPRINT",
        "fingerprint_key": fingerprint_key,
        "observed": observed_hash,
        "expected": expected_hash,
        "match_strength": match_strength_on_match if status == "MATCH" else "NONE",
        "evidence_level": "DB_FINGERPRINT",
    }
    if notes:
        evidence["notes"] = notes
    bucket = {
        "status": status,
        "before": expected_hash,
        "after": observed_hash,
        "sampleSize": min(len(expected_rows), len(observed_rows)),
    }
    return bucket, evidence

