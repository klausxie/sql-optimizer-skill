"""
Baseline Stage Module (V8)

Performance baseline collection and testing.
"""

from .baseline_collector import (
    BaselineCollector,
    BaselineResult,
    ExplainPlan,
    collect_baseline,
)

__all__ = [
    "BaselineCollector",
    "BaselineResult",
    "ExplainPlan",
    "collect_baseline",
]
