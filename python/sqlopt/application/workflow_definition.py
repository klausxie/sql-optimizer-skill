from __future__ import annotations

from .status_resolver import PhaseExecutionPolicy

STAGE_ORDER = ["diagnose", "optimize", "validate", "apply", "report"]

PHASE_POLICIES = {
    "diagnose": PhaseExecutionPolicy("diagnose"),
    "optimize": PhaseExecutionPolicy("optimize"),
    "validate": PhaseExecutionPolicy("validate"),
    "apply": PhaseExecutionPolicy("apply"),
    "report": PhaseExecutionPolicy("report", allow_regenerate=True),
}

PHASE_TRANSITIONS = {
    "diagnose": "optimize",
    "optimize": "validate",
    "validate": "apply",
    "apply": "report",
    "report": None,
}

STATEMENT_PHASE_TARGETS = {
    "optimize": {"optimize", "validate", "apply", "report"},
    "validate": {"validate", "apply", "report"},
    "apply": {"apply", "report"},
}
