from __future__ import annotations

from ..runtime.models import HarnessArtifacts


def assert_manifest_contains_stages(artifacts: HarnessArtifacts, stages: list[str]) -> None:
    manifest_stages = {
        str(row.get("stage") or "")
        for row in artifacts.manifest_rows
        if str(row.get("stage") or "").strip()
    }
    missing = [stage for stage in stages if stage not in manifest_stages]
    if missing:
        raise AssertionError(f"manifest missing stages: {missing}")
