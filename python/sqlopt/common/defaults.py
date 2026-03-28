"""Shared default values for SQL Optimizer.

All tunable constants live here. Each module imports from here instead of
hardcoding values.  This makes it possible to change a default in one place
and have the entire pipeline reflect the new value without hunting down
duplicate literals.
"""

# ---------------------------------------------------------------------------
# Parse stage - branch expansion
# ---------------------------------------------------------------------------

# Default maximum number of branches to generate per SQL unit.
# Changing this value automatically affects:
#   • SQLOptConfig.parse_max_branches (dataclass default)
#   • SQLOptConfig YAML-loader fallback
#   • BranchExpander.__init__.default parameter
#   • BranchGenerator.__init__.default parameter
#   • RiskGuidedLadderPlanner.__init__.default parameter
#   • all BranchStrategy.generate() default parameters
DEFAULT_MAX_BRANCHES: int = 100

# Upper bound used by the adaptive branch-cap formula.
# adaptive_max_branches() returns min(max(BASE, 2**(n-1)), MAX_CAP) for 2**n > BASE.
MAX_CAP: int = DEFAULT_MAX_BRANCHES * 10  # 1000
