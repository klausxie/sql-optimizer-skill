from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io_utils import write_json
from ..run_paths import canonical_paths
from ..supervisor import (
    append_step_result,
    get_plan,
    init_run,
    load_meta,
    load_state,
    save_state,
    set_meta_status,
    set_plan,
)


class RunRepository:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir

    def initialize(self, config: dict[str, Any], run_id: str) -> None:
        init_run(self.run_dir, config, run_id)

    def write_resolved_config(self, config: dict[str, Any]) -> None:
        write_json(canonical_paths(self.run_dir).config_resolved_path, config)

    def load_state(self) -> dict[str, Any]:
        return load_state(self.run_dir)

    def save_state(self, state: dict[str, Any]) -> None:
        save_state(self.run_dir, state)

    def get_plan(self) -> dict[str, Any]:
        return get_plan(self.run_dir)

    def set_plan(self, plan: dict[str, Any]) -> None:
        set_plan(self.run_dir, plan)

    def load_meta(self) -> dict[str, Any]:
        return load_meta(self.run_dir)

    def set_meta_status(self, status: str) -> None:
        set_meta_status(self.run_dir, status)

    def append_step_result(
        self,
        phase: str,
        status: str,
        *,
        sql_key: str | None = None,
        reason_code: str | None = None,
        artifact_refs: list[str] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        append_step_result(
            self.run_dir,
            phase,
            status,
            sql_key=sql_key,
            reason_code=reason_code,
            artifact_refs=artifact_refs,
            detail=detail,
        )
