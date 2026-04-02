from __future__ import annotations

from .calibrator import calculate_blocker_family, calibrate_extension_scenarios
from .contracts import (
    BLOCKER_FAMILIES,
    PATCHABILITY_TARGETS,
    ROADMAP_STAGES,
    ROADMAP_THEMES,
    SCENARIO_CLASSES,
    SEMANTIC_TARGETS,
    VALIDATE_EVIDENCE_MODES,
    VALIDATE_STATUSES,
)
from .generator import generate_extension_scenarios, generate_scenario, match_scenario_class
from .loader import load_scenarios, save_scenarios, summarize_scenarios

load_fixture_scenarios = load_scenarios
summarize_fixture_scenarios = summarize_scenarios

__all__ = [
    "BLOCKER_FAMILIES",
    "PATCHABILITY_TARGETS",
    "ROADMAP_STAGES",
    "ROADMAP_THEMES",
    "SCENARIO_CLASSES",
    "SEMANTIC_TARGETS",
    "VALIDATE_EVIDENCE_MODES",
    "VALIDATE_STATUSES",
    "calculate_blocker_family",
    "calibrate_extension_scenarios",
    "generate_extension_scenarios",
    "generate_scenario",
    "load_fixture_scenarios",
    "load_scenarios",
    "match_scenario_class",
    "save_scenarios",
    "summarize_fixture_scenarios",
    "summarize_scenarios",
]
