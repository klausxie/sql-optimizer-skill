"""
Optimize Stage Module

LLM-powered optimization proposal generation.
Re-exports from the main optimize stage.
"""

# Re-export main functions from the monolithic stage
from sqlopt.stages.optimize import execute_one

__all__ = [
    "execute_one",
]
