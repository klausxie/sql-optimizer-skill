from __future__ import annotations

import tempfile
from pathlib import Path

from ....adapters.scanner_java import run_scan
from ....io_utils import read_jsonl
from .project import FIXTURE_PROJECT_ROOT


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
