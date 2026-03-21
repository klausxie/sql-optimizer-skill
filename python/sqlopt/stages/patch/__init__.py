"""
Patch Stage Module

Patch generation from validated optimization candidates.
"""

from sqlopt.stages.patch.apply import apply_from_config, apply_patch_only
from sqlopt.stages.patch.execute_one import PatchStage, execute_one
from sqlopt.stages.patch.patch_generator import (
    PatchGenerator,
    PatchResult,
)
from sqlopt.stages.base import StageResult

__all__ = [
    # Apply functions
    "apply_from_config",
    "apply_patch_only",
    # Patch stage
    "PatchStage",
    # Patch generator
    "execute_one",
    "PatchGenerator",
    "PatchResult",
    "StageResult",
]
