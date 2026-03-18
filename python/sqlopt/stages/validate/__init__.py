"""
Validate Stage Module

Database validation of optimization candidates.
Re-exports from the main validate stage.
"""

# Re-export main functions from the monolithic stage
from sqlopt.stages.validate import execute_one

__all__ = [
    "execute_one",
]
