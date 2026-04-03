from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..manifest import log_event
from ..run_paths import canonical_paths
from ..runtime import execute_with_retry
from .run_repository import RunRepository

PHASE_RUNTIME_ALIASES = {
    "patch_generate": "apply",
}


def runtime_cfg(config: dict[str, Any], phase: str) -> tuple[int, int, int]:
    rt = config["runtime"]
    phase_key = phase
    if phase_key not in rt.get("stage_timeout_ms", {}):
        phase_key = PHASE_RUNTIME_ALIASES.get(phase_key, phase_key)
    timeout_ms = int(rt["stage_timeout_ms"][phase_key])
    retry_max = int(rt["stage_retry_max"][phase_key])
    retry_backoff_ms = int(rt["stage_retry_backoff_ms"])
    return timeout_ms, retry_max, retry_backoff_ms


def run_phase_action(config: dict[str, Any], phase: str, fn: Callable[[], object]) -> tuple[object, int]:
    timeout_ms, retry_max, retry_backoff_ms = runtime_cfg(config, phase)
    return execute_with_retry(
        phase,
        fn,
        timeout_ms=timeout_ms,
        retry_max=retry_max,
        retry_backoff_ms=retry_backoff_ms,
    )


def record_failure(
    run_dir: Path,
    state: dict[str, Any],
    phase: str,
    reason_code: str,
    message: str,
    *,
    repository: RunRepository | None = None,
    run_repository_factory: Callable[[Path], RunRepository] = RunRepository,
) -> None:
    paths = canonical_paths(run_dir)
    repo = repository or run_repository_factory(run_dir)
    state["phase_status"][phase] = "FAILED"
    state["last_error"] = message
    state["last_reason_code"] = reason_code
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo.save_state(state)
    repo.append_phase_event(
        phase,
        "FAILED",
        reason_code=reason_code,
        artifact_refs=[str(paths.manifest_path)],
        detail={"message": message},
    )
    log_event(paths.manifest_path, phase, "failed", {"reason_code": reason_code, "message": message})
