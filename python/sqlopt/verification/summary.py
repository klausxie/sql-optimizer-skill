from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import VerificationSummary


def summarize_records(run_id: str, rows: list[dict[str, Any]], *, total_sql: int) -> VerificationSummary:
    records_by_phase: dict[str, int] = {}
    verified_count = 0
    partial_count = 0
    unverified_count = 0
    reason_counts: dict[str, int] = {}
    blocking_sql_keys: set[str] = set()

    for row in rows:
        phase = str(row.get("phase") or "unknown")
        records_by_phase[phase] = records_by_phase.get(phase, 0) + 1
        status = str(row.get("status") or "UNVERIFIED").upper()
        if status == "VERIFIED":
            verified_count += 1
        elif status == "PARTIAL":
            partial_count += 1
        elif status == "UNVERIFIED":
            unverified_count += 1
            sql_key = str(row.get("sql_key") or "").strip()
            if sql_key:
                blocking_sql_keys.add(sql_key)
        row_reason_codes: set[str] = set()
        code = str(row.get("reason_code") or "").strip()
        if status != "VERIFIED" and code:
            row_reason_codes.add(code)
        for check in row.get("checks") or []:
            if not isinstance(check, dict):
                continue
            if bool(check.get("ok")):
                continue
            check_code = str(check.get("reason_code") or "").strip()
            if check_code:
                row_reason_codes.add(check_code)
        for reason_code in row_reason_codes:
            reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1

    expected = total_sql if total_sql > 0 else 0
    coverage_by_phase: dict[str, dict[str, Any]] = {}
    for phase, recorded in records_by_phase.items():
        ratio = round(recorded / expected, 3) if expected > 0 else 1.0
        coverage_by_phase[phase] = {"recorded": recorded, "expected": expected, "ratio": ratio}

    top_reason_codes = [
        {"reason_code": code, "count": count}
        for code, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]

    return VerificationSummary(
        run_id=run_id,
        total_sql=max(total_sql, 0),
        records_by_phase=records_by_phase,
        verified_count=verified_count,
        partial_count=partial_count,
        unverified_count=unverified_count,
        coverage_by_phase=coverage_by_phase,
        top_reason_codes=top_reason_codes,
        blocking_sql_keys=sorted(blocking_sql_keys),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
