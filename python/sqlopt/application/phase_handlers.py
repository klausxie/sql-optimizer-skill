from __future__ import annotations

from .phase_handlers_indexed import (
    advance_optimize,
    advance_patch_generate,
    advance_validate,
)
from .phase_handlers_pre import advance_scan
from .phase_handlers_report import advance_report

__all__ = [
    # preflight stage removed
    "advance_scan",
    "advance_optimize",
    "advance_validate",
    "advance_patch_generate",
    "advance_report",
]
