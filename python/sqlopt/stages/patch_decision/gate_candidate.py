"""
Gate 4: Candidate Gate

候选唯一性检查门控，验证是否恰好有一个 PASS 候选。
"""

from .gates import Gate, GateContext, GateResult, extract_fallback_reason_codes, build_selection_evidence
from .constants import ReasonCode


class CandidateGate(Gate[None]):
    """
    Gate 4: 候选唯一性检查

    验证：
    - 必须恰好一个 PASS 候选
    - 选中的 winner 必须是该候选

    如果有多个 PASS 候选或选中的不是该候选，则无法确定唯一补丁。
    """

    def __init__(self):
        super().__init__("Candidate", order=4)

    def execute(self, ctx: GateContext) -> GateResult[None]:
        statement_key = ctx.statement_key

        # 查找同一 statement 的所有接受结果
        same_statement = [
            row for row in ctx.acceptance_rows
            if ctx.statement_key_fn(str(row.get("sqlKey", ""))) == statement_key
        ]

        # 查找 PASS 的候选
        pass_rows = [row for row in same_statement if row.get("status") == "PASS"]

        fallback_reason_codes = extract_fallback_reason_codes(ctx.acceptance)

        # 检查是否恰好一个 PASS 候选
        if len(pass_rows) != 1 or str(pass_rows[0].get("sqlKey")) != ctx.sql_key:
            return self.on_skip(
                ReasonCode.PATCH_CONFLICT_NO_CLEAR_WINNER,
                "multiple PASS variants found or selected winner mismatched",
                selection_evidence=build_selection_evidence(
                    status=ctx.acceptance.get("status"),
                    semantic_gate_status=ctx.selection.semantic_gate_status,
                    semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
                    acceptance=ctx.acceptance,
                ),
                fallback_reason_codes=fallback_reason_codes,
            )

        return self.on_pass(ctx)