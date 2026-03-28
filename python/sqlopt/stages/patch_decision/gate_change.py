"""
Gate 5: Change Gate

有效变更检查门控，验证优化后是否真的有变更。
"""

from .gates import Gate, GateContext, GateResult, extract_fallback_reason_codes, build_selection_evidence
from .constants import ReasonCode


class ChangeGate(Gate[None]):
    """
    Gate 5: 有效变更检查

    验证优化后的 SQL 与原始 SQL 是否有语义差异。
    对于静态 SQL（无 dynamicFeatures），通过 normalize 比较。
    如果没有有效变更，则不生成补丁。
    """

    def __init__(self, normalize_sql_fn):
        """
        初始化门控

        Args:
            normalize_sql_fn: SQL 规范化函数，用于比较两个 SQL 是否等价
        """
        super().__init__("Change", order=5)
        self._normalize = normalize_sql_fn

    def execute(self, ctx: GateContext) -> GateResult[None]:
        original_sql = str(ctx.sql_unit.get("sql") or "")
        rewritten_sql = ctx.selection.rewritten_sql
        dynamic_features = [str(x) for x in (ctx.sql_unit.get("dynamicFeatures") or []) if str(x).strip()]
        fallback_reason_codes = extract_fallback_reason_codes(ctx.acceptance)

        # 无动态特征时，检查是否有有效变更
        if not dynamic_features:
            if self._normalize(original_sql) == self._normalize(rewritten_sql):
                return self.on_skip(
                    ReasonCode.PATCH_NO_EFFECTIVE_CHANGE,
                    "rewritten sql has no semantic diff after normalization",
                    selection_evidence=build_selection_evidence(
                        status=ctx.acceptance.get("status"),
                        semantic_gate_status=ctx.selection.semantic_gate_status,
                        semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
                        acceptance=ctx.acceptance,
                    ),
                    fallback_reason_codes=fallback_reason_codes,
                )

        return self.on_pass(ctx)