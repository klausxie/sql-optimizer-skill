from __future__ import annotations

from typing import Final

STAGE_ORDER: Final[list[str]] = [
    "init",
    "parse",
    "recognition",
    "optimize",
    "patch",
]

STAGE_SET: Final[frozenset[str]] = frozenset(STAGE_ORDER)
DB_REQUIRED_STAGES: Final[frozenset[str]] = frozenset({"recognition", "optimize"})


def require_v9_stage(stage_name: str) -> str:
    normalized = str(stage_name or "").strip()
    if normalized not in STAGE_SET:
        raise ValueError(
            f"unknown V9 target stage '{normalized}'; expected one of {STAGE_ORDER}"
        )
    return normalized
