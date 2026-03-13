from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from sqlopt.adapters.scanner_java import run_scan
from sqlopt.contracts import ContractValidator
from sqlopt.io_utils import read_jsonl, write_jsonl
from sqlopt.platforms.sql.validator_sql import validate_proposal
from sqlopt.run_paths import canonical_paths
from sqlopt.stages.patch_generate import execute_one as execute_patch_one
from sqlopt.stages.report_builder import build_report_artifacts
from sqlopt.stages.report_interfaces import ReportInputs, ReportStateSnapshot

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PROJECT = ROOT / "tests" / "fixtures" / "project"
SCENARIO_MATRIX = FIXTURE_PROJECT / "fixture_scenarios.json"
SCENARIO_CLASSES = {
    "PATCH_READY_STATEMENT",
    "PATCH_READY_WRAPPER_COLLAPSE",
    "PATCH_BLOCKED_SECURITY",
    "PATCH_BLOCKED_SEMANTIC",
    "PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED",
}
ROADMAP_STAGES = {"BASELINE", "NEXT", "FUTURE"}
ROADMAP_THEMES = {
    "STATEMENT_PATCH",
    "WRAPPER_COLLAPSE",
    "DYNAMIC_TEMPLATE",
    "SECURITY_GUARDRAIL",
    "DML_BOUNDARY",
    "AGGREGATION_SEMANTICS",
    "CTE_ENABLEMENT",
    "COMPLEX_QUERY_SHAPE",
}
VALIDATE_STATUSES = {"PASS", "NEED_MORE_PARAMS", "FAIL"}
SEMANTIC_TARGETS = {"PASS", "UNCERTAIN", "BLOCKED", "FAIL"}
PATCHABILITY_TARGETS = {"READY", "REVIEW", "BLOCKED"}
VALIDATE_EVIDENCE_MODES = {"compare_disabled", "exact_match_improved", "rowcount_mismatch"}
BLOCKER_FAMILIES = {"READY", "SECURITY", "SEMANTIC", "TEMPLATE_UNSUPPORTED"}


def load_fixture_scenarios() -> list[dict]:
    return json.loads(SCENARIO_MATRIX.read_text(encoding="utf-8"))


def summarize_fixture_scenarios(scenarios: list[dict]) -> dict[str, object]:
    scenario_class_counts: dict[str, int] = {}
    blocker_family_counts: dict[str, int] = {}
    roadmap_stage_counts: dict[str, int] = {}
    roadmap_theme_counts: dict[str, int] = {}
    next_target_sql_keys: list[str] = []
    for row in scenarios:
        scenario_class = str(row.get("scenarioClass") or "")
        blocker_family = str(row.get("targetBlockerFamily") or "")
        roadmap_stage = str(row.get("roadmapStage") or "")
        roadmap_theme = str(row.get("roadmapTheme") or "")
        if scenario_class:
            scenario_class_counts[scenario_class] = scenario_class_counts.get(scenario_class, 0) + 1
        if blocker_family:
            blocker_family_counts[blocker_family] = blocker_family_counts.get(blocker_family, 0) + 1
        if roadmap_stage:
            roadmap_stage_counts[roadmap_stage] = roadmap_stage_counts.get(roadmap_stage, 0) + 1
        if roadmap_theme:
            roadmap_theme_counts[roadmap_theme] = roadmap_theme_counts.get(roadmap_theme, 0) + 1
        if roadmap_stage == "NEXT":
            next_target_sql_keys.append(str(row.get("sqlKey") or ""))
    return {
        "scenarioClassCounts": scenario_class_counts,
        "blockerFamilyCounts": blocker_family_counts,
        "roadmapStageCounts": roadmap_stage_counts,
        "roadmapThemeCounts": roadmap_theme_counts,
        "nextTargetSqlKeys": next_target_sql_keys,
    }


def scan_fixture_project() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    with tempfile.TemporaryDirectory(prefix="sqlopt_fixture_harness_") as td:
        run_dir = Path(td) / "runs" / "run_fixture_harness_scan"
        run_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "project": {"root_path": str(FIXTURE_PROJECT)},
            "scan": {
                "mapper_globs": ["src/main/resources/**/*.xml"],
                "max_variants_per_statement": 3,
            },
            "db": {"platform": "postgresql"},
        }
        units, warnings = run_scan(config, run_dir, run_dir / "pipeline" / "manifest.jsonl")
        fragments = read_jsonl(run_dir / "pipeline" / "scan" / "fragments.jsonl")

    if warnings:
        raise AssertionError(f"unexpected scan warnings: {warnings}")

    units_by_key = {str(row["sqlKey"]): row for row in units}
    fragment_catalog = {str(row.get("fragmentKey") or ""): row for row in fragments if str(row.get("fragmentKey") or "").strip()}
    return units, units_by_key, fragment_catalog


def semantic_gate_bucket(result: dict) -> str:
    feedback_code = str(((result.get("feedback") or {}).get("reason_code") or "")).strip()
    if feedback_code.startswith("VALIDATE_SECURITY_"):
        return "BLOCKED"
    gate = result.get("semanticEquivalence") or {}
    return str(gate.get("status") or "UNCERTAIN").upper()


def patchability_bucket(result: dict) -> str:
    feedback_code = str(((result.get("feedback") or {}).get("reason_code") or "")).strip()
    if feedback_code.startswith("VALIDATE_SECURITY_"):
        return "BLOCKED"
    patchability = result.get("patchability") or {}
    if bool(patchability.get("eligible")):
        return "READY"
    gate = semantic_gate_bucket(result)
    if gate == "FAIL" or str(result.get("status") or "").upper() == "FAIL":
        return "BLOCKED"
    return "REVIEW"


def primary_blocker(result: dict) -> str | None:
    patchability = result.get("patchability") or {}
    if bool(patchability.get("eligible")):
        return None
    code = str(patchability.get("blockingReason") or "").strip()
    if code:
        return code
    feedback_code = str(((result.get("feedback") or {}).get("reason_code") or "")).strip()
    if feedback_code:
        return feedback_code
    gate = result.get("semanticEquivalence") or {}
    reasons = [str(x) for x in (gate.get("reasons") or []) if str(x).strip()]
    return reasons[0] if reasons else None


def validate_blocker_family(result: dict) -> str:
    if bool((result.get("patchability") or {}).get("eligible")):
        return "READY"
    feedback_code = str(((result.get("feedback") or {}).get("reason_code") or "")).strip().upper()
    if feedback_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
        return "SECURITY"
    gate_status = str(((result.get("semanticEquivalence") or {}).get("status") or "")).strip().upper()
    if gate_status == "FAIL" or str(result.get("status") or "").upper() == "FAIL":
        return "SEMANTIC"
    return "TEMPLATE_UNSUPPORTED"


def patch_blocker_family(patch: dict) -> str:
    if patch.get("strategyType") or patch.get("applicable") is True:
        return "READY"
    reason_code = str(((patch.get("selectionReason") or {}).get("code") or "")).strip().upper()
    if reason_code == "PATCH_VALIDATION_BLOCKED_SECURITY":
        return "SECURITY"
    gate_status = str(((patch.get("gates") or {}).get("semanticEquivalenceStatus") or "")).strip().upper()
    if reason_code == "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS" or gate_status == "FAIL":
        return "SEMANTIC"
    return "TEMPLATE_UNSUPPORTED"


def proposal_for_candidate(candidate_sql: str) -> dict:
    return {
        "llmCandidates": [
            {
                "id": "fixture:validate",
                "rewrittenSql": candidate_sql,
                "rewriteStrategy": "fixture_harness",
            }
        ],
        "suggestions": [],
    }


def config_for_validate(mode: str) -> dict:
    config = {
        "db": {"platform": "postgresql"},
        "validate": {"validation_profile": "balanced"},
        "policy": {},
        "patch": {},
        "llm": {"enabled": False},
    }
    if mode != "compare_disabled":
        config["db"]["dsn"] = "postgresql://dummy"
    return config


def fake_semantics_for_mode(mode: str) -> dict:
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


def fake_plan_for_mode(mode: str) -> dict:
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


def validate_fixture_scenario(
    *,
    scenario: dict,
    units_by_key: dict[str, dict],
    fragment_catalog: dict[str, dict],
) -> tuple[dict, dict]:
    sql_key = str(scenario["sqlKey"])
    unit = units_by_key[sql_key]
    proposal = proposal_for_candidate(str(scenario["validateCandidateSql"]))
    mode = str(scenario["validateEvidenceMode"])
    config = config_for_validate(mode)

    with tempfile.TemporaryDirectory(prefix="sqlopt_fixture_validate_") as td:
        evidence_dir = Path(td)
        if mode == "compare_disabled":
            result = validate_proposal(unit, proposal, True, config=config, evidence_dir=evidence_dir, fragment_catalog=fragment_catalog)
        else:
            with patch("sqlopt.platforms.sql.validator_sql.compare_semantics", return_value=fake_semantics_for_mode(mode)), patch(
                "sqlopt.platforms.sql.validator_sql.compare_plan",
                return_value=fake_plan_for_mode(mode),
            ):
                result = validate_proposal(unit, proposal, True, config=config, evidence_dir=evidence_dir, fragment_catalog=fragment_catalog)
    return proposal, result.to_contract()


def run_fixture_validate_harness() -> tuple[list[dict], list[dict], list[dict], dict[str, dict], dict[str, dict], dict[str, dict]]:
    scenarios = load_fixture_scenarios()
    units, units_by_key, fragment_catalog = scan_fixture_project()
    proposals: list[dict] = []
    acceptance_rows: list[dict] = []
    acceptance_by_key: dict[str, dict] = {}
    for scenario in scenarios:
        proposal, acceptance = validate_fixture_scenario(
            scenario=scenario,
            units_by_key=units_by_key,
            fragment_catalog=fragment_catalog,
        )
        proposal["sqlKey"] = str(scenario["sqlKey"])
        proposals.append(proposal)
        acceptance_rows.append(acceptance)
        acceptance_by_key[str(scenario["sqlKey"])] = acceptance
    return scenarios, proposals, acceptance_rows, units_by_key, acceptance_by_key, fragment_catalog


def run_fixture_patch_and_report_harness() -> tuple[list[dict], list[dict], list[dict], list[dict], object]:
    scenarios, proposals, acceptance_rows, units_by_key, acceptance_by_key, _fragment_catalog = run_fixture_validate_harness()
    validator = ContractValidator(ROOT)

    with tempfile.TemporaryDirectory(prefix="sqlopt_fixture_patch_") as td:
        run_dir = Path(td) / "runs" / "run_fixture_patch_harness"
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        write_jsonl(paths.acceptance_path, acceptance_rows)

        patch_config = {
            "project": {"root_path": str(ROOT)},
            "patch": {"llm_assist": {"enabled": False}},
            "llm": {"enabled": False},
        }
        patches: list[dict] = []
        for scenario in scenarios:
            sql_key = str(scenario["sqlKey"])
            patch_row = execute_patch_one(
                units_by_key[sql_key],
                acceptance_by_key[sql_key],
                run_dir,
                validator,
                config=patch_config,
            )
            patch_files = [Path(str(x)) for x in (patch_row.get("patchFiles") or []) if str(x).strip()]
            patch_texts = [path.read_text(encoding="utf-8") for path in patch_files if path.exists()]
            patch_row["_patchTexts"] = patch_texts
            patches.append(patch_row)

        verification_rows = read_jsonl(paths.verification_ledger_path)
        report_config = {
            "policy": {},
            "runtime": {
                "stage_timeout_ms": {"scan": 100, "optimize": 200, "report": 300},
                "stage_retry_max": {"scan": 1, "report": 2},
                "stage_retry_backoff_ms": 50,
            },
            "llm": {"enabled": False},
        }
        report_artifacts = build_report_artifacts(
            "run_fixture_patch_harness",
            "analyze",
            report_config,
            run_dir,
            ReportInputs(
                units=[units_by_key[str(scenario["sqlKey"])] for scenario in scenarios],
                proposals=proposals,
                acceptance=acceptance_rows,
                patches=patches,
                state=ReportStateSnapshot(
                    phase_status={
                        "preflight": "DONE",
                        "scan": "DONE",
                        "optimize": "DONE",
                        "validate": "DONE",
                        "patch_generate": "DONE",
                        "report": "DONE",
                    },
                    attempts_by_phase={"report": 1},
                ),
                manifest_rows=[],
                verification_rows=verification_rows,
            ),
        )
    return scenarios, proposals, acceptance_rows, patches, report_artifacts
