from __future__ import annotations

from ..runtime.models import HarnessArtifacts


def assert_run_completed(artifacts: HarnessArtifacts) -> None:
    if artifacts.state.get("status") != "COMPLETED":
        raise AssertionError(f"expected run status COMPLETED, got {artifacts.state.get('status')!r}")


def assert_phase_status(artifacts: HarnessArtifacts, phase: str, expected: str) -> None:
    actual = str((artifacts.state.get("phase_status") or {}).get(phase) or "")
    if actual != expected:
        raise AssertionError(f"expected phase {phase!r} to be {expected!r}, got {actual!r}")


def assert_report_rebuild_cleared(artifacts: HarnessArtifacts) -> None:
    if bool(artifacts.state.get("report_rebuild_required")):
        raise AssertionError("expected report_rebuild_required to be false")
