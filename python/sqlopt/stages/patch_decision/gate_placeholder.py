"""
Gate 8: Placeholder Gate

占位符语义检查门控，验证 #{} 和 ? 的语义是否匹配。
"""

from .gates import Gate, GateContext, GateResult, extract_fallback_reason_codes, build_selection_evidence
from .constants import ReasonCode


class PlaceholderGate(Gate[None]):
    """
    Gate 8: 占位符语义检查

    验证原始 SQL 和重写 SQL 之间的占位符语义是否一致：
    - 如果原始 SQL 有 #{}，重写后应该有对应的占位符
    - 如果出现 #{} → ? 的转换，需要确保语义等价
    """

    def __init__(self):
        super().__init__("Placeholder", order=8)

    def execute(self, ctx: GateContext) -> GateResult[None]:
        original_sql = str(ctx.sql_unit.get("sql") or "")
        rewritten_sql = ctx.selection.rewritten_sql
        fallback_reason_codes = extract_fallback_reason_codes(ctx.acceptance)

        # 检查占位符语义是否匹配
        # 原 SQL 有 #{} 但重写后变成 ?，可能语义不匹配
        if "#{" in original_sql and "?" in rewritten_sql and "#{" not in rewritten_sql:
            return self.on_skip(
                ReasonCode.PATCH_PLACEHOLDER_MISMATCH,
                "placeholder semantics mismatch",
                selection_evidence=build_selection_evidence(
                    status=ctx.acceptance.get("status"),
                    semantic_gate_status=ctx.selection.semantic_gate_status,
                    semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
                    acceptance=ctx.acceptance,
                ),
                fallback_reason_codes=fallback_reason_codes,
            )

        return self.on_pass(ctx)