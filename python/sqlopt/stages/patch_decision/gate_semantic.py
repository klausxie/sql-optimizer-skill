"""
Gate 3: Semantic Gate

语义等价门检查门控，验证语义等价验证是否通过。
"""

from .gates import Gate, GateContext, GateResult, extract_fallback_reason_codes, build_selection_evidence
from .constants import ReasonCode


class SemanticGate(Gate[None]):
    """
    Gate 3: 语义等价门检查

    验证语义等价门状态：
    - semantic_gate_status 必须为 "PASS"
    - semantic_gate_confidence 不能为 "LOW"
    """

    def __init__(self):
        super().__init__("Semantic", order=3)

    def execute(self, ctx: GateContext) -> GateResult[None]:
        semantic_gate_status = ctx.selection.semantic_gate_status
        semantic_gate_confidence = ctx.selection.semantic_gate_confidence
        fallback_reason_codes = extract_fallback_reason_codes(ctx.acceptance)

        # 检查语义门状态
        if semantic_gate_status != "PASS":
            return self.on_skip(
                ReasonCode.PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS,
                f"semantic equivalence gate is {semantic_gate_status}, patch generation is blocked",
                selection_evidence=build_selection_evidence(
                    status=ctx.acceptance.get("status"),
                    semantic_gate_status=semantic_gate_status,
                    semantic_gate_confidence=semantic_gate_confidence,
                    acceptance=ctx.acceptance,
                ),
                fallback_reason_codes=fallback_reason_codes,
                selected_candidate_id=ctx.acceptance.get("selectedCandidateId"),
            )

        # 检查置信度
        if semantic_gate_confidence == "LOW":
            return self.on_skip(
                ReasonCode.PATCH_SEMANTIC_CONFIDENCE_LOW,
                "semantic equivalence confidence is LOW, patch generation is blocked",
                selection_evidence=build_selection_evidence(
                    status=ctx.acceptance.get("status"),
                    semantic_gate_status=semantic_gate_status,
                    semantic_gate_confidence=semantic_gate_confidence,
                    acceptance=ctx.acceptance,
                ),
                fallback_reason_codes=fallback_reason_codes,
                selected_candidate_id=ctx.acceptance.get("selectedCandidateId"),
            )

        return self.on_pass(ctx)