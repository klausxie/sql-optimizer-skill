from __future__ import annotations

from .status_resolver import PhaseExecutionPolicy

STAGE_ORDER = ["preflight", "scan", "optimize", "validate", "patch_generate", "report"]

PHASE_POLICIES = {
    "preflight": PhaseExecutionPolicy("preflight"),
    "scan": PhaseExecutionPolicy("scan"),
    "optimize": PhaseExecutionPolicy("optimize"),
    "validate": PhaseExecutionPolicy("validate"),
    "patch_generate": PhaseExecutionPolicy("patch_generate"),
    "report": PhaseExecutionPolicy("report", allow_regenerate=True),
}

PHASE_TRANSITIONS = {
    "preflight": "scan",
    "scan": "optimize",
    "optimize": "validate",
    "validate": "patch_generate",
    "patch_generate": "report",
    "report": None,
}

STATEMENT_PHASE_TARGETS = {
    "optimize": {"optimize", "validate", "patch_generate", "report"},
    "validate": {"validate", "patch_generate", "report"},
    "patch_generate": {"patch_generate", "report"},
}
