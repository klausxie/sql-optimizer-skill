from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from ....platforms.sql.candidate_generation_support import recover_candidates_from_shape
from ....platforms.sql.canonicalization_support import normalize_sql
from ....platforms.sql.patch_strategy_planner import plan_patch_strategy
from ....platforms.sql.validator_sql import validate_proposal
from ....utils import statement_key
from ..scenarios.loader import load_scenarios
from .scan_fixture import scan_fixture_project

_FIXTURE_RECOVERY_STRATEGY_BY_FAMILY = {
    "STATIC_ORDER_BY_SIMPLIFICATION": "REMOVE_CONSTANT_ORDER_BY_RECOVERED",
    "STATIC_BOOLEAN_SIMPLIFICATION": "REMOVE_BOOLEAN_TAUTOLOGY_RECOVERED",
    "STATIC_IN_LIST_SIMPLIFICATION": "SIMPLIFY_SINGLE_VALUE_IN_LIST_RECOVERED",
    "STATIC_OR_SIMPLIFICATION": "SIMPLIFY_OR_TO_IN_RECOVERED",
    "STATIC_CASE_SIMPLIFICATION": "SIMPLIFY_CASE_WHEN_TRUE_RECOVERED",
    "STATIC_COALESCE_SIMPLIFICATION": "SIMPLIFY_COALESCE_IDENTITY_RECOVERED",
    "STATIC_EXPRESSION_FOLDING": "FOLD_CONSTANT_EXPRESSION_RECOVERED",
    "STATIC_LIMIT_OPTIMIZATION": "REMOVE_LARGE_LIMIT_RECOVERED",
    "STATIC_NULL_COMPARISON": "SIMPLIFY_NULL_COMPARISON_RECOVERED",
    "STATIC_DISTINCT_ON_SIMPLIFICATION": "SIMPLIFY_DISTINCT_ON_RECOVERED",
    "STATIC_EXISTS_REWRITE": "SAFE_EXISTS_REWRITE",
    "STATIC_UNION_COLLAPSE": "SAFE_UNION_COLLAPSE",
}


def embedded_verification_rows(*collections: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for collection in collections:
        for row in collection:
            verification = row.get("verification") if isinstance(row, dict) else None
            if isinstance(verification, dict):
                rows.append(dict(verification))
    return rows


def _infer_fixture_rewrite_strategy(sql_key: str, original_sql: str, candidate_sql: str, scenario: dict) -> str:
    normalized_candidate = normalize_sql(candidate_sql).lower()
    for candidate in recover_candidates_from_shape(sql_key, original_sql):
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or "")).lower()
        if rewritten_sql == normalized_candidate:
            strategy = str(candidate.get("rewriteStrategy") or "").strip()
            if strategy:
                return strategy
    target_family = str(scenario.get("targetRegisteredFamily") or "").strip()
    mapped = _FIXTURE_RECOVERY_STRATEGY_BY_FAMILY.get(target_family)
    if mapped:
        return mapped
    return "fixture_harness"


def _proposal_for_candidate(sql_key: str, original_sql: str, candidate_sql: str, scenario: dict) -> dict:
    rewrite_strategy = _infer_fixture_rewrite_strategy(sql_key, original_sql, candidate_sql, scenario)
    return {
        "llmCandidates": [
            {
                "id": "fixture:validate",
                "rewrittenSql": candidate_sql,
                "rewriteStrategy": rewrite_strategy,
            }
        ],
        "candidateGenerationDiagnostics": {"recoveryStrategy": rewrite_strategy},
        "suggestions": [],
    }


def _config_for_validate() -> dict:
    return {
        "db": {"platform": "postgresql", "dsn": "postgresql://dummy"},
        "validate": {"validation_profile": "balanced"},
        "policy": {},
        "patch": {},
        "llm": {"enabled": False},
    }


def _fake_semantics_for_mode(mode: str) -> dict:
    if mode == "exact_match_improved":
        return {
            "checked": True,
            "method": "fixture_compare",
            "rowCount": {"status": "MATCH"},
            "keySetHash": {"status": "MATCH"},
            "rowSampleHash": {"status": "MATCH"},
            "evidenceRefs": [],
            "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "EXACT"}],
        }
    if mode == "rowcount_mismatch":
        return {
            "checked": True,
            "method": "fixture_compare",
            "rowCount": {"status": "MISMATCH"},
            "keySetHash": {"status": "MISMATCH"},
            "rowSampleHash": {"status": "MISMATCH"},
            "evidenceRefs": [],
            "evidenceRefObjects": [{"source": "DB_FINGERPRINT", "match_strength": "PARTIAL"}],
        }
    raise AssertionError(mode)


def _fake_plan_for_mode(mode: str) -> dict:
    if mode == "exact_match_improved":
        return {
            "checked": True,
            "method": "fixture_plan_compare",
            "beforeSummary": {"totalCost": 100.0},
            "afterSummary": {"totalCost": 40.0},
            "reasonCodes": ["TOTAL_COST_REDUCED"],
            "improved": True,
            "evidenceRefs": [],
        }
    if mode == "rowcount_mismatch":
        return {
            "checked": True,
            "method": "fixture_plan_compare",
            "beforeSummary": {"totalCost": 100.0},
            "afterSummary": {"totalCost": 100.0},
            "reasonCodes": ["TOTAL_COST_NOT_REDUCED"],
            "improved": False,
            "evidenceRefs": [],
        }
    raise AssertionError(mode)


def resolve_fixture_unit(sql_key: str, units_by_key: dict[str, dict]) -> dict:
    unit = units_by_key.get(sql_key)
    if unit is not None:
        return unit
    target_statement_key = statement_key(sql_key)
    statement_matches = [row for row in units_by_key.values() if statement_key(str(row.get("sqlKey") or "")) == target_statement_key]
    if len(statement_matches) == 1:
        return statement_matches[0]
    raise KeyError(sql_key)


def validate_fixture_scenario(
    *,
    scenario: dict,
    units_by_key: dict[str, dict],
) -> tuple[dict, dict]:
    sql_key = str(scenario["sqlKey"])
    unit = resolve_fixture_unit(sql_key, units_by_key)
    proposal = _proposal_for_candidate(sql_key, str(unit.get("sql") or ""), str(scenario["validateCandidateSql"]), scenario)
    mode = str(scenario["validateEvidenceMode"])
    config = _config_for_validate()

    with tempfile.TemporaryDirectory(prefix="sqlopt_fixture_validate_") as td:
        evidence_dir = Path(td)
        if mode == "compare_disabled":
            result = validate_proposal(unit, proposal, True, config=config, evidence_dir=evidence_dir)
        else:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", return_value=_fake_semantics_for_mode(mode)), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan",
                return_value=_fake_plan_for_mode(mode),
            ):
                result = validate_proposal(unit, proposal, True, config=config, evidence_dir=evidence_dir)
    return proposal, result.to_contract()


def run_fixture_validate_harness(
    *,
    project_root: Path | None = None,
) -> tuple[list[dict], list[dict], list[dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    scenarios = load_scenarios()
    _units, units_by_key, fragment_catalog = scan_fixture_project(project_root)
    proposals: list[dict] = []
    acceptance_rows: list[dict] = []
    acceptance_by_key: dict[str, dict] = {}
    for scenario in scenarios:
        proposal, acceptance = validate_fixture_scenario(
            scenario=scenario,
            units_by_key=units_by_key,
        )
        proposal["sqlKey"] = str(scenario["sqlKey"])
        proposals.append(proposal)

        sql_key = str(scenario["sqlKey"])
        unit = resolve_fixture_unit(sql_key, units_by_key)
        rewritten_sql = str(acceptance.get("rewrittenSql") or "").strip()
        if rewritten_sql and fragment_catalog:
            try:
                rewrite_facts, _, _, _, _, _, _ = plan_patch_strategy(
                    unit,
                    rewritten_sql,
                    fragment_catalog,
                    dict(acceptance.get("equivalence") or {}),
                    dict(acceptance.get("semanticEquivalence") or {}),
                    enable_fragment_materialization=False,
                )
                acceptance["rewriteFacts"] = rewrite_facts
            except Exception:
                pass

        acceptance_rows.append(acceptance)
        acceptance_by_key[sql_key] = acceptance
    return scenarios, proposals, acceptance_rows, units_by_key, acceptance_by_key, fragment_catalog
