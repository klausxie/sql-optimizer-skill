"""
Patch Stage Module

Patch generation from validated optimization candidates.
"""

from sqlopt.stages.patch.apply import apply_from_config, apply_patch_only
from sqlopt.stages.patch.patch_generator import (
    execute_one as generate_patch,
    PatchGenerator,
    PatchResult,
)
from sqlopt.stages.base import StageResult

__all__ = [
    # Apply functions
    "apply_from_config",
    "apply_patch_only",
    # Patch generator
    "generate_patch",
    "PatchGenerator",
    "PatchResult",
    "StageResult",
]
