from __future__ import annotations

from pathlib import Path

from ....io_utils import read_json, read_jsonl
from ....run_paths import canonical_paths
from .models import HarnessArtifacts


def _read_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def load_run_artifacts(run_dir: Path) -> HarnessArtifacts:
    paths = canonical_paths(run_dir)
    report = _read_json_if_exists(paths.report_json_path)
    state = _read_json_if_exists(paths.state_path)
    plan = _read_json_if_exists(paths.plan_path)
    return HarnessArtifacts(
        run_dir=run_dir,
        report_path=paths.report_json_path,
        state_path=paths.state_path,
        plan_path=paths.plan_path,
        manifest_path=paths.manifest_path,
        scan_path=paths.scan_units_path,
        fragments_path=paths.scan_fragments_path,
        proposals_path=paths.proposals_path,
        acceptance_path=paths.acceptance_path,
        patches_path=paths.patches_path,
        sql_catalog_path=paths.sql_catalog_path,
        report=report,
        state=state,
        plan=plan,
        manifest_rows=read_jsonl(paths.manifest_path),
        scan_rows=read_jsonl(paths.scan_units_path),
        fragment_rows=read_jsonl(paths.scan_fragments_path),
        proposal_rows=read_jsonl(paths.proposals_path),
        acceptance_rows=read_jsonl(paths.acceptance_path),
        patch_rows=read_jsonl(paths.patches_path),
        sql_catalog_rows=read_jsonl(paths.sql_catalog_path),
    )

