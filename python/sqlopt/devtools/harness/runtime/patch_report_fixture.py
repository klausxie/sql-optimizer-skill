from __future__ import annotations

import tempfile
from pathlib import Path

from ....contracts import ContractValidator
from ....io_utils import write_jsonl
from ....run_paths import canonical_paths
from ....stages.patch_generate import execute_one as execute_patch_one
from ....stages.validate_convergence import build_statement_convergence_row
from ....stages.report_builder import build_report_artifacts
from ....stages.report_interfaces import ReportInputs, ReportStateSnapshot
from .project import ROOT, prepare_fixture_project
from .validate_fixture import embedded_verification_rows, resolve_fixture_unit, run_fixture_validate_harness

_FIXTURE_CONVERGENCE_REGISTERED_FAMILIES = {
    "STATIC_ORDER_BY_SIMPLIFICATION",
    "STATIC_OR_SIMPLIFICATION",
    "STATIC_CASE_SIMPLIFICATION",
    "STATIC_COALESCE_SIMPLIFICATION",
    "STATIC_EXPRESSION_FOLDING",
    "STATIC_BOOLEAN_SIMPLIFICATION",
    "STATIC_IN_LIST_SIMPLIFICATION",
    "STATIC_LIMIT_OPTIMIZATION",
    "STATIC_NULL_COMPARISON",
    "STATIC_DISTINCT_ON_SIMPLIFICATION",
    "STATIC_EXISTS_REWRITE",
    "STATIC_UNION_COLLAPSE",
}


def _scenario_requires_fixture_convergence(scenario: dict, convergence_row: dict) -> bool:
    expected_reason = str(scenario.get("targetPatchReasonCode") or "").strip().upper()
    if expected_reason.startswith("PATCH_CONVERGENCE_"):
        return True
    tracked_family = str(scenario.get("targetRegisteredFamily") or "").strip()
    if tracked_family in _FIXTURE_CONVERGENCE_REGISTERED_FAMILIES:
        return True
    return False


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
        convergence_rows: list[dict] = []
        for scenario in scenarios:
            sql_key = str(scenario["sqlKey"])
            unit = resolve_fixture_unit(sql_key, units_by_key)
            acceptance_row = acceptance_by_key[sql_key]
            statement_key = str(acceptance_row.get("statementKey") or unit.get("statementKey") or sql_key)
            sql_index_path = paths.sql_artifact_dir(sql_key) / "index.json"
            convergence_row = build_statement_convergence_row(
                statement_key_value=statement_key,
                rows=[acceptance_row],
                sql_key=sql_key,
                acceptance_path=paths.acceptance_path,
                sql_index_path=sql_index_path,
                sql_unit=unit,
                proposal=next((row for row in proposals if str(row.get("sqlKey") or "") == sql_key), None),
            )
            if not _scenario_requires_fixture_convergence(scenario, convergence_row):
                continue
            convergence_rows.append(convergence_row)
        write_jsonl(paths.statement_convergence_path, convergence_rows)

        patch_config = {
            "project": {"root_path": str(project_root)},
            "patch": {"llm_assist": {"enabled": False}},
            "llm": {"enabled": False},
        }
        patches: list[dict] = []
        for scenario in scenarios:
            sql_key = str(scenario["sqlKey"])
            patch_row = execute_patch_one(
                resolve_fixture_unit(sql_key, units_by_key),
                acceptance_by_key[sql_key],
                run_dir,
                validator,
                config=patch_config,
            )
            patch_files = [Path(str(x)) for x in (patch_row.get("patchFiles") or []) if str(x).strip()]
            patch_texts = [path.read_text(encoding="utf-8") for path in patch_files if path.exists()]
            patch_row["_patchTexts"] = patch_texts
            patches.append(patch_row)

        verification_rows = embedded_verification_rows(
            [resolve_fixture_unit(str(scenario["sqlKey"]), units_by_key) for scenario in scenarios],
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
                units=[resolve_fixture_unit(str(scenario["sqlKey"]), units_by_key) for scenario in scenarios],
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
