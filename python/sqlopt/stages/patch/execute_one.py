"""Patch stage execute_one entry point.

This module re-exports the execute_one function from patch_generator
to maintain consistency with other stage modules.
"""

from sqlopt.stages.patch.patch_generator import (
    execute_one,
    PatchGenerator,
    PatchResult,
)

__all__ = ["execute_one", "PatchGenerator", "PatchResult"]
