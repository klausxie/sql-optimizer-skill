"""
Patch Stage Module

Patch generation from validated optimization candidates.
Re-exports from the main patch stages.
"""

# Re-export main functions from patch_generate
from sqlopt.stages.patch_generate import execute_one as generate_patch

# Re-export from apply
from sqlopt.stages.apply import apply_patch_only

__all__ = [
    "generate_patch",
    "apply_patch_only",
]
