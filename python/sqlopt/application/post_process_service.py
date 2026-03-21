from __future__ import annotations

from pathlib import Path
from typing import Any

from ..stages.patch import apply as apply_stage
from . import run_index


def apply_run(run_id: str, *, repo_root: Path) -> dict[str, Any]:
    """Apply generated patch artifacts as a post-processing action outside the V9 workflow."""
    run_dir = run_index.resolve_run_dir(run_id, repo_root_fn=lambda: repo_root)
    state = apply_stage.apply_from_config(run_dir)
    return {"run_id": run_id, "apply": state}
