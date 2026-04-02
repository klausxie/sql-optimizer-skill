from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from ....adapters.scanner_java import run_scan
from ....contracts import ContractValidator
from ....io_utils import read_jsonl, write_jsonl
from ....platforms.sql.patch_strategy_planner import plan_patch_strategy
from ....platforms.sql.validator_sql import validate_proposal
from ....run_paths import canonical_paths
from ....stages.patch_generate import execute_one as execute_patch_one
from ....stages.report_builder import build_report_artifacts
from ....stages.report_interfaces import ReportInputs, ReportStateSnapshot
from ..scenarios import load_scenarios
from .project import FIXTURE_PROJECT_ROOT, ROOT, prepare_fixture_project


def scan_fixture_project(project_root: Path | None = None) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    effective_project_root = project_root or FIXTURE_PROJECT_ROOT
    with tempfile.TemporaryDirectory(prefix="sqlopt_fixture_harness_") as td:
        run_dir = Path(td) / "runs" / "run_fixture_harness_scan"
        run_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "project": {"root_path": str(effective_project_root)},
            "scan": {
                "mapper_globs": ["src/main/resources/**/*.xml"],
                "max_variants_per_statement": 3,
            },
            "db": {"platform": "postgresql"},
        }
        units, warnings = run_scan(config, run_dir, run_dir / "control" / "manifest.jsonl")
        fragments = read_jsonl(run_dir / "artifacts" / "fragments.jsonl")

    if warnings:
        raise AssertionError(f"unexpected scan warnings: {warnings}")

    units_by_key = {str(row["sqlKey"]): row for row in units}
    fragment_catalog = {str(row.get("fragmentKey") or ""): row for row in fragments if str(row.get("fragmentKey") or "").strip()}
    return units, units_by_key, fragment_catalog


def _embedded_verification_rows(*collections: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for collection in collections:
        for row in collection:
            verification = row.get("verification") if isinstance(row, dict) else None
            if isinstance(verification, dict):
                rows.append(dict(verification))
    return rows


def _proposal_for_candidate(candidate_sql: str) -> dict:
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


def validate_fixture_scenario(
    *,
    scenario: dict,
    units_by_key: dict[str, dict],
) -> tuple[dict, dict]:
    sql_key = str(scenario["sqlKey"])
    unit = units_by_key[sql_key]
    proposal = _proposal_for_candidate(str(scenario["validateCandidateSql"]))
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
    units, units_by_key, fragment_catalog = scan_fixture_project(project_root)
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
        unit = units_by_key[sql_key]
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


def run_fixture_patch_and_report_harness() -> tuple[list[dict], list[dict], list[dict], list[dict], object]:
    with tempfile.TemporaryDirectory(prefix="sqlopt_fixture_patch_") as td:
        project_root = prepare_fixture_project(Path(td), mutable=True, init_git=True).root_path
        scenarios, proposals, acceptance_rows, units_by_key, acceptance_by_key, fragment_catalog = run_fixture_validate_harness(
            project_root=project_root
        )
        validator = ContractValidator(ROOT)
        run_dir = Path(td) / "runs" / "run_fixture_patch_harness"
        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        write_jsonl(paths.acceptance_path, acceptance_rows)
        write_jsonl(paths.scan_fragments_path, list(fragment_catalog.values()))

        patch_config = {
            "project": {"root_path": str(project_root)},
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

        verification_rows = _embedded_verification_rows(
            [units_by_key[str(scenario["sqlKey"])] for scenario in scenarios],
            proposals,
            acceptance_rows,
            patches,
        )
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
