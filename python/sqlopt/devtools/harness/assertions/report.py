from __future__ import annotations

from ..runtime.models import HarnessArtifacts

_REPORT_KEYS = {
    "run_id",
    "generated_at",
    "status",
    "verdict",
    "next_action",
    "phase_status",
}


def assert_report_generated(artifacts: HarnessArtifacts) -> None:
    if not artifacts.report_path.exists():
        raise AssertionError(f"expected report at {artifacts.report_path}")
    missing = sorted(_REPORT_KEYS - set(artifacts.report))
    if missing:
        raise AssertionError(f"report missing keys: {missing}")
