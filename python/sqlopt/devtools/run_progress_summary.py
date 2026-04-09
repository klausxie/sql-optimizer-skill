from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .harness.runtime import load_run_artifacts


BLOCKER_BUCKETS = (
    "NO_PATCHABLE_CANDIDATE_SELECTED",
    "SEMANTIC_GATE_NOT_PASS",
    "VALIDATE_STATUS_NOT_PASS",
    "SHAPE_FAMILY_NOT_TARGET",
    "OTHER",
)


@dataclass(frozen=True)
class StatementProgressRow:
    statement_key: str
    shape_family: str
    convergence_decision: str
    conflict_reason: str
    patch_reason_code: str
    patch_files: tuple[str, ...]


@dataclass(frozen=True)
class RunProgressSummary:
    run_dir: Path
    total_statements: int
    decision_counts: dict[str, int]
    conflict_reason_counts: dict[str, int]
    patch_convergence_blocked_count: int
    rows: tuple[StatementProgressRow, ...]


def _normalize_statement_keys(statement_keys: Iterable[str] | None) -> set[str]:
    return {str(value).strip() for value in (statement_keys or []) if str(value).strip()}


def normalize_blocker_bucket(reason: str | None) -> str:
    normalized = str(reason or "").strip().upper()
    if normalized.startswith("NO_PATCHABLE_CANDIDATE") or normalized == "NO_SAFE_BASELINE_RECOVERY":
        return "NO_PATCHABLE_CANDIDATE_SELECTED"
    if normalized.startswith("SEMANTIC_"):
        return "SEMANTIC_GATE_NOT_PASS"
    if normalized.startswith("VALIDATE_"):
        return "VALIDATE_STATUS_NOT_PASS"
    if normalized in BLOCKER_BUCKETS[:-1]:
        return normalized
    return "OTHER"


def blocker_bucket_counts(conflict_reason_counts: dict[str, int]) -> dict[str, int]:
    counts = {bucket: 0 for bucket in BLOCKER_BUCKETS}
    for reason, count in conflict_reason_counts.items():
        counts[normalize_blocker_bucket(reason)] += int(count)
    return counts


def _patch_rows_by_statement(patch_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_statement: dict[str, list[dict[str, Any]]] = {}
    for row in patch_rows:
        statement_key = str(row.get("statementKey") or "").strip() or str(row.get("sqlKey") or "").split("#", 1)[0]
        if not statement_key:
            continue
        by_statement.setdefault(statement_key, []).append(row)
    return by_statement


def summarize_run_progress(
    run_dir: Path,
    *,
    statement_keys: Iterable[str] | None = None,
    shape_family: str | None = None,
) -> RunProgressSummary:
    artifacts = load_run_artifacts(Path(run_dir).resolve())
    selected_statement_keys = _normalize_statement_keys(statement_keys)
    normalized_shape_family = str(shape_family or "").strip().upper()
    patch_rows_by_statement = _patch_rows_by_statement(artifacts.patch_rows)

    rows: list[StatementProgressRow] = []
    decision_counts = {
        "AUTO_PATCHABLE": 0,
        "MANUAL_REVIEW": 0,
        "NOT_PATCHABLE": 0,
    }
    conflict_reason_counts: dict[str, int] = {}
    patch_convergence_blocked_count = 0

    for row in artifacts.statement_convergence_rows:
        statement_key = str(row.get("statementKey") or "").strip()
        if not statement_key:
            continue
        if selected_statement_keys and statement_key not in selected_statement_keys:
            continue
        row_shape_family = str(row.get("shapeFamily") or "").strip().upper()
        if normalized_shape_family and row_shape_family != normalized_shape_family:
            continue

        statement_patch_rows = patch_rows_by_statement.get(statement_key, [])
        patch_reason_code = ""
        patch_files: tuple[str, ...] = ()
        for patch_row in statement_patch_rows:
            code = str(((patch_row.get("selectionReason") or {}).get("code") or "")).strip()
            if code.startswith("PATCH_CONVERGENCE_"):
                patch_convergence_blocked_count += 1
            if not patch_reason_code and code:
                patch_reason_code = code
            if not patch_files:
                patch_files = tuple(str(value) for value in (patch_row.get("patchFiles") or []) if str(value).strip())

        convergence_decision = str(row.get("convergenceDecision") or "").strip().upper()
        if convergence_decision in decision_counts:
            decision_counts[convergence_decision] += 1
        conflict_reason = str(row.get("conflictReason") or "").strip()
        if conflict_reason:
            conflict_reason_counts[conflict_reason] = conflict_reason_counts.get(conflict_reason, 0) + 1

        rows.append(
            StatementProgressRow(
                statement_key=statement_key,
                shape_family=row_shape_family,
                convergence_decision=convergence_decision,
                conflict_reason=conflict_reason,
                patch_reason_code=patch_reason_code,
                patch_files=patch_files,
            )
        )

    rows.sort(key=lambda item: item.statement_key)
    return RunProgressSummary(
        run_dir=Path(run_dir).resolve(),
        total_statements=len(rows),
        decision_counts=decision_counts,
        conflict_reason_counts=dict(sorted(conflict_reason_counts.items(), key=lambda item: (-item[1], item[0]))),
        patch_convergence_blocked_count=patch_convergence_blocked_count,
        rows=tuple(rows),
    )


def summarize_progress_metrics(summary: RunProgressSummary) -> dict[str, Any]:
    auto_patchable = int(summary.decision_counts.get("AUTO_PATCHABLE", 0))
    blocked_statement_count = max(int(summary.total_statements) - auto_patchable, 0)
    auto_patchable_rate = (auto_patchable / summary.total_statements) if summary.total_statements else 0.0
    return {
        "auto_patchable_rate": auto_patchable_rate,
        "blocked_statement_count": blocked_statement_count,
        "blocker_bucket_counts": blocker_bucket_counts(summary.conflict_reason_counts),
    }
