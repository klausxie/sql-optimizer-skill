from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from . import run_index
from .v9_stages.patch import run_patch


def apply_run(run_id: str, *, repo_root: Path) -> dict[str, Any]:
    run_dir = run_index.resolve_run_dir(run_id, repo_root_fn=lambda: repo_root)
    validator = ContractValidator(repo_root)
    state = run_patch(run_dir, validator=validator)
    return {"run_id": run_id, "apply": state}
