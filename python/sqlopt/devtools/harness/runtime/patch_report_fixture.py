from __future__ import annotations

import tempfile
from pathlib import Path

from ....contracts import ContractValidator
from ....io_utils import write_jsonl
from ....run_paths import canonical_paths
from ....stages.patch_generate import execute_one as execute_patch_one
from ....stages.report_builder import build_report_artifacts
from ....stages.report_interfaces import ReportInputs, ReportStateSnapshot
from .project import ROOT, prepare_fixture_project
from .validate_fixture import embedded_verification_rows, resolve_fixture_unit, run_fixture_validate_harness


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
