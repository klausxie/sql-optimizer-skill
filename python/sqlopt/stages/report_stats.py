from __future__ import annotations

from typing import Any

from ..failure_classification import classify_reason_code
from ..platforms.sql.materialization_constants import materialization_reason_group


def compute_verdict(stats: dict[str, Any]) -> str:
    if int(stats.get("fatal_count") or 0) > 0:
        return "BLOCKED"
    if int(stats.get("acceptance_fail") or 0) > 0:
        return "ATTENTION"
    if int(stats.get("acceptance_need_more_params") or 0) > 0:
        return "PARTIAL"
    if int(stats.get("sql_units") or 0) == 0:
        return "EMPTY"
    return "PASS"


def compute_release_readiness(verdict: str, stats: dict[str, Any]) -> str:
    if verdict in {"BLOCKED", "ATTENTION"}:
        return "NO_GO"
    if verdict == "PARTIAL":
        return "CONDITIONAL_GO"
    if verdict == "PASS" and int(stats.get("patch_applicable_count") or 0) > 0:
        return "GO"
    return "CONDITIONAL_GO"


def default_next_actions(run_id: str, verdict: str, reason_counts: dict[str, int]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if verdict in {"BLOCKED", "ATTENTION", "PARTIAL"}:
        actions.append(
            {
                "action_id": "resume",
                "title": "Platform: resume run",
                "reason": "pipeline not fully healthy",
                "applicability": "pending or degraded pipeline",
                "expected_outcome": "continue or finalize processing",
                "commands": [f"PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id {run_id}"],
            }
        )
    if reason_counts.get("VALIDATE_DB_UNREACHABLE", 0) > 0:
        actions.append(
            {
                "action_id": "check-db",
                "title": "DBA: verify DB connectivity",
                "reason": "validation DB checks were skipped",
                "applicability": "VALIDATE_DB_UNREACHABLE present",
                "expected_outcome": "semantic and perf checks become executable",
                "commands": ['psql "$DSN" -c "select 1;"'],
            }
        )
    if reason_counts.get("VALIDATE_SECURITY_DOLLAR_SUBSTITUTION", 0) > 0:
        actions.append(
            {
                "action_id": "remove-dollar",
                "title": "Backend: remove ${} dynamic SQL",
                "reason": "unsafe SQL substitution blocks optimization",
                "applicability": "security warnings in validation",
                "expected_outcome": "statement becomes patchable",
                "commands": ['rg -n "\\$\\{" src/main/resources/**/*.xml'],
            }
        )
    if not actions:
        actions.append(
            {
                "action_id": "apply",
                "title": "Backend: apply generated patches",
                "reason": "run is healthy",
                "applicability": "applicable patches available",
                "expected_outcome": "land safe SQL improvements",
                "commands": [f"PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id {run_id}"],
            }
        )
    return actions


def build_top_blockers(failures: list[dict[str, Any]], reason_counts: dict[str, int]) -> list[dict[str, Any]]:
    sql_keys_by_code: dict[str, set[str]] = {}
    for row in failures:
        code = str(row.get("reason_code") or "UNKNOWN")
        sql_key = str(row.get("sql_key") or "")
        sql_keys_by_code.setdefault(code, set())
        if sql_key:
            sql_keys_by_code[code].add(sql_key)
    out: list[dict[str, Any]] = []
    for code, count in sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]:
        out.append(
            {
                "code": code,
                "count": int(count),
                "ratio": None,
                "severity": classify_reason_code(code, phase="validate"),
                "sql_keys": sorted(sql_keys_by_code.get(code, set())),
            }
        )
    return out


def build_prioritized_sql_keys(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sql: dict[str, dict[str, Any]] = {}
    for row in failures:
        sql_key = str(row.get("sql_key") or "")
        if not sql_key:
            continue
        rcode = str(row.get("reason_code") or "UNKNOWN")
        bucket = by_sql.setdefault(sql_key, {"sql_key": sql_key, "count": 0, "blocker_codes": set(), "has_fatal": False})
        bucket["count"] += 1
        bucket["blocker_codes"].add(rcode)
        if str(row.get("classification") or "") == "fatal":
            bucket["has_fatal"] = True
    rows: list[dict[str, Any]] = []
    for val in by_sql.values():
        rows.append(
            {
                "sql_key": val["sql_key"],
                "priority": "P0" if val["has_fatal"] else "P1",
                "score": int(val["count"]),
                "blocker_codes": sorted(val["blocker_codes"]),
            }
        )
    rows.sort(key=lambda x: (0 if x["priority"] == "P0" else 1, -int(x["score"])))
    return rows[:10]


def build_sql_rows(units: list[dict[str, Any]], acceptance: list[dict[str, Any]], patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    acceptance_by_sql_key = {str(row.get("sqlKey")): row for row in acceptance}
    patch_by_statement = {str(row.get("statementKey")): row for row in patches}
    rows: list[dict[str, Any]] = []
    for unit in units:
        sql_key = str(unit.get("sqlKey") or "")
        statement_key = sql_key.split("#", 1)[0]
        acceptance_row = acceptance_by_sql_key.get(sql_key, {})
        patch_row = patch_by_statement.get(statement_key, {})
        perf = acceptance_row.get("perfComparison") or {}
        eq = acceptance_row.get("equivalence") or {}
        rows.append(
            {
                "sql_key": sql_key,
                "status": acceptance_row.get("status") or "PENDING",
                "selected_source": acceptance_row.get("selectedCandidateSource") or "n/a",
                "semantic_risk": acceptance_row.get("semanticRisk") or "unknown",
                "perf_improved": perf.get("improved"),
                "before_cost": (perf.get("beforeSummary") or {}).get("totalCost"),
                "after_cost": (perf.get("afterSummary") or {}).get("totalCost"),
                "patch_applicable": patch_row.get("applicable"),
                "patch_selection_code": (patch_row.get("selectionReason") or {}).get("code"),
                "rewrite_materialization_mode": (acceptance_row.get("rewriteMaterialization") or {}).get("mode"),
                "rewrite_materialization_reason": (acceptance_row.get("rewriteMaterialization") or {}).get("reasonCode"),
                "row_status": (eq.get("rowCount") or {}).get("status"),
                "evidence_refs": eq.get("evidenceRefs") or [],
            }
        )
    return rows


def materialization_mode_counts(acceptance: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in acceptance:
        mode = str((row.get("rewriteMaterialization") or {}).get("mode") or "").strip()
        if not mode:
            continue
        counts[mode] = counts.get(mode, 0) + 1
    return counts


def materialization_reason_counts(acceptance: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in acceptance:
        reason = str((row.get("rewriteMaterialization") or {}).get("reasonCode") or "").strip()
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def materialization_reason_group_counts(reason_counts: dict[str, int]) -> dict[str, int]:
    grouped: dict[str, int] = {}
    for reason, count in reason_counts.items():
        group = materialization_reason_group(reason)
        if not group:
            continue
        grouped[group] = grouped.get(group, 0) + int(count)
    return grouped


def build_proposal_rows(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proposal in proposals:
        issues = proposal.get("issues") or []
        issue_codes = [str(x.get("code")) for x in issues if isinstance(x, dict) and x.get("code")]
        rows.append(
            {
                "sql_key": str(proposal.get("sqlKey") or ""),
                "verdict": str(proposal.get("verdict") or "UNKNOWN"),
                "issue_codes": issue_codes,
                "llm_candidate_count": len(proposal.get("llmCandidates") or []),
            }
        )
    return rows


def report_acceptance_llm_count(acceptance_rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in acceptance_rows if row.get("selectedCandidateSource") == "llm")
