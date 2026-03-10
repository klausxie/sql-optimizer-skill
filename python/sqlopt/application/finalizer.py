from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..contracts import ContractValidator
from ..errors import StageError
from ..manifest import log_event
from ..run_paths import canonical_paths
from .run_repository import RunRepository

RunPhaseAction = Callable[[dict[str, Any], str, Callable[[], object]], tuple[object, int]]
RecordFailure = Callable[[Path, dict[str, Any], str, str, str], None]


class RunFinalizer:
    def __init__(
        self,
        *,
        report_enabled: Callable[[dict[str, Any]], bool],
        report_generate: Callable[[str, str, dict[str, Any], Path, ContractValidator], object],
        run_repository_factory: Callable[[Path], RunRepository] = RunRepository,
    ) -> None:
        self._report_enabled = report_enabled
        self._report_generate = report_generate
        self._run_repository_factory = run_repository_factory

    def finalize_report_if_enabled(
        self,
        run_dir: Path,
        config: dict[str, Any],
        validator: ContractValidator,
        state: dict[str, Any],
        *,
        final_meta_status: str,
        repository: RunRepository | None = None,
        run_phase_action_fn: RunPhaseAction,
        record_failure_fn: RecordFailure,
    ) -> bool:
        paths = canonical_paths(run_dir)
        if not self._report_enabled(config):
            return False
        repo = repository or self._run_repository_factory(run_dir)
        report_was_done = state.get("phase_status", {}).get("report") == "DONE"

        # Persist report=done before rendering to keep state and report consumer view aligned.
        state["phase_status"]["report"] = "DONE"
        state["current_phase"] = "report"
        state["report_rebuild_required"] = True
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        repo.save_state(state)

        try:
            _, attempts = run_phase_action_fn(
                config,
                "report",
                lambda: self._report_generate(run_dir.name, "analyze", config, run_dir, validator),
            )
        except StageError as exc:
            reason_code = exc.reason_code or "RUNTIME_RETRY_EXHAUSTED"
            if report_was_done:
                state["phase_status"]["report"] = "DONE"
                state["current_phase"] = "report"
                state["last_error"] = str(exc)
                state["last_reason_code"] = reason_code
                state["report_rebuild_required"] = True
                state["updated_at"] = datetime.now(timezone.utc).isoformat()
                repo.save_state(state)
                repo.append_step_result(
                    "report",
                    "FAILED",
                    reason_code=reason_code,
                    artifact_refs=[str(paths.manifest_path)],
                    detail={"message": str(exc), "rebuild": True},
                )
                log_event(
                    paths.manifest_path,
                    "report",
                    "failed",
                    {"reason_code": reason_code, "message": str(exc)},
                )
                repo.set_meta_status(final_meta_status)
                return False

            record_failure_fn(run_dir, state, "report", reason_code, str(exc))
            state["report_rebuild_required"] = True
            state["current_phase"] = "report"
            state["updated_at"] = datetime.now(timezone.utc).isoformat()
            repo.save_state(state)
            repo.set_meta_status("READY_TO_FINALIZE" if final_meta_status == "COMPLETED" else final_meta_status)
            return False

        state["attempts_by_phase"]["report"] += attempts
        state["report_rebuild_required"] = False
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        repo.save_state(state)
        if not report_was_done:
            repo.append_step_result("report", "DONE", artifact_refs=[str(paths.report_json_path)])
        repo.set_meta_status(final_meta_status)
        return True

    def finalize_without_report(
        self,
        run_dir: Path,
        state: dict[str, Any],
        *,
        final_meta_status: str,
        repository: RunRepository | None = None,
    ) -> None:
        repo = repository or self._run_repository_factory(run_dir)
        report_was_skipped = state.get("phase_status", {}).get("report") == "SKIPPED"
        state["phase_status"]["report"] = "SKIPPED"
        state["report_rebuild_required"] = False
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        repo.save_state(state)
        if not report_was_skipped:
            repo.append_step_result("report", "SKIPPED")
        repo.set_meta_status(final_meta_status)
