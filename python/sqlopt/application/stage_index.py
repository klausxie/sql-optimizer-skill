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
    acceptance: dict[str, Any]


def load_index(run_dir: Path) -> LoadedStageIndex:
    paths = canonical_paths(run_dir)
    units = {x["sqlKey"]: x for x in read_jsonl(paths.scan_units_path)}
    proposals = {x["sqlKey"]: x for x in read_jsonl(paths.proposals_path)}
    acceptance = {x["sqlKey"]: x for x in read_jsonl(paths.acceptance_path)}
    return LoadedStageIndex(units=units, proposals=proposals, acceptance=acceptance)
