from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..io_utils import read_jsonl
from ..run_paths import RunPaths, canonical_paths


@dataclass(frozen=True)
class LoadedStageIndex:
    units: dict[str, Any]
    proposals: dict[str, Any]
    patch_ready_proposals: dict[str, Any]


def _load_proposal_rows(paths: RunPaths) -> list[dict[str, Any]]:
    if paths.v9_proposals_path.exists():
        raw = json.loads(paths.v9_proposals_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
    if paths.proposals_path.exists():
        return [x for x in read_jsonl(paths.proposals_path) if isinstance(x, dict)]
    return []


def load_index(run_dir: Path) -> LoadedStageIndex:
    paths = canonical_paths(run_dir)
    units = paths.load_sql_units_map()
    proposal_rows = _load_proposal_rows(paths)
    proposals = {
        str(x["sqlKey"]): x for x in proposal_rows if isinstance(x.get("sqlKey"), str)
    }
    patch_ready_proposals = {
        str(x["sqlKey"]): x
        for x in proposal_rows
        if isinstance(x, dict) and x.get("validated") is True and x.get("sqlKey")
    }
    return LoadedStageIndex(
        units=units,
        proposals=proposals,
        patch_ready_proposals=patch_ready_proposals,
    )
