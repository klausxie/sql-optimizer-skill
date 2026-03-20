from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..io_utils import read_jsonl
from ..run_paths import canonical_paths


@dataclass(frozen=True)
class LoadedStageIndex:
    units: dict[str, Any]
    proposals: dict[str, Any]
    patch_ready_proposals: dict[str, Any]


def load_index(run_dir: Path) -> LoadedStageIndex:
    paths = canonical_paths(run_dir)
    units = {x["sqlKey"]: x for x in read_jsonl(paths.scan_units_path)}
    proposals = {x["sqlKey"]: x for x in read_jsonl(paths.proposals_path)}
    patch_ready_proposals = {
        x["sqlKey"]: x
        for x in read_jsonl(paths.proposals_path)
        if isinstance(x, dict) and x.get("validated") is True
    }
    return LoadedStageIndex(
        units=units,
        proposals=proposals,
        patch_ready_proposals=patch_ready_proposals,
    )
