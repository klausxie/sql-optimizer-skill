"""
Patch Decision Module

重构后的 patch 决策模块，包含门控架构。
"""

# 导出公共接口
from .constants import (
    GateResultStatus,
    DeliveryTier,
    ReasonCode,
)

from .gates import (
    Gate,
    GateContext,
    GateResult,
    extract_acceptance_reason_code,
    extract_fallback_reason_codes,
    build_selection_evidence,
)

from .context import PatchDecisionContext

from .engine import (
    PatchDecisionEngine,
    EngineConfig,
    create_engine,
)

from .compat import decide_patch_result

# Helper functions (inlined from patch_decision_helpers.py)
from .helpers import (
    attach_patch_diagnostics,
    build_patch_repair_hints,
    should_call_llm_assist,
)

__all__ = [
    # Constants
    "GateResultStatus",
    "DeliveryTier",
    "ReasonCode",
    # Gates
    "Gate",
    "GateContext",
    "GateResult",
    "extract_acceptance_reason_code",
    "extract_fallback_reason_codes",
    "build_selection_evidence",
    # Context
    "PatchDecisionContext",
    # Engine
    "PatchDecisionEngine",
    "EngineConfig",
    "create_engine",
    # Compat
    "decide_patch_result",
    # Legacy helpers (re-exported for backward compatibility)
    "attach_patch_diagnostics",
    "build_patch_repair_hints",
    "should_call_llm_assist",
]