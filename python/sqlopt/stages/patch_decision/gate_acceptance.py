"""
Gate 2: Acceptance Gate

Acceptance 状态检查门控，验证 validate 阶段的接受结果。
"""

from __future__ import annotations

from typing import Optional

from .gates import Gate, GateContext, GateResult, extract_acceptance_reason_code, extract_fallback_reason_codes, build_selection_evidence
from .constants import ReasonCode


class AcceptanceGate(Gate[None]):
    """
    Gate 2: Acceptance 状态检查

    验证 acceptance.status 是否为 "PASS"。
    非 PASS 状态根据原因分类处理：
    - 动态模板阻断 (FOREACH/SET/FILTER) → BLOCKED
    - 安全问题 ($ {}) → PATCHABLE_WITH_REWRITE
    - 其他 → PATCH_CONFLICT_NO_CLEAR_WINNER
    """

    def __init__(self):
        super().__init__("Acceptance", order=2)

    def execute(self, ctx: GateContext) -> GateResult[None]:
        status = ctx.acceptance.get("status")
        acceptance_reason_code = extract_acceptance_reason_code(ctx.acceptance)
        fallback_reason_codes = extract_fallback_reason_codes(ctx.acceptance)

        if status == "PASS":
            return self.on_pass(ctx)

        # 非 PASS 状态，根据原因分类处理
        dynamic_template = ctx.selection.dynamic_template or {}
        dynamic_blocking_reason = str(dynamic_template.get("blockingReason") or "").strip().upper()
        dynamic_shape_family = str(dynamic_template.get("shapeFamily") or "").strip().upper()
        semantic_gate_status = ctx.selection.semantic_gate_status

        # 首先检查语义门是否通过
        if semantic_gate_status == "PASS":
            reason_code, reason_message = self._check_dynamic_blocking(
                dynamic_blocking_reason, dynamic_shape_family
            )
            if reason_code:
                # 动态模板阻断
                return self.on_skip(
                    reason_code,
                    reason_message,
                    selection_evidence=self._build_evidence(ctx),
                    fallback_reason_codes=fallback_reason_codes,
                )

        # 检查安全问题
        if acceptance_reason_code == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION":
            return self.on_skip(
                ReasonCode.PATCH_VALIDATION_BLOCKED_SECURITY,
                "validate blocked patch generation due unsafe ${} substitution",
                selection_evidence=self._build_evidence(ctx),
                fallback_reason_codes=fallback_reason_codes,
            )

        # 默认：冲突无明确获胜者
        return self.on_skip(
            ReasonCode.PATCH_CONFLICT_NO_CLEAR_WINNER,
            "acceptance status is not PASS",
            selection_evidence=self._build_evidence(ctx),
            fallback_reason_codes=fallback_reason_codes,
            selected_candidate_id=ctx.acceptance.get("selectedCandidateId"),
        )

    def _check_dynamic_blocking(self, blocking_reason: str, shape_family: str) -> tuple[Optional[str], Optional[str]]:
        """检查动态模板阻断原因"""
        if blocking_reason.startswith("FOREACH_") or shape_family == "FOREACH_IN_PREDICATE":
            return (
                ReasonCode.PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED,
                "dynamic foreach predicate requires template-aware rewrite before patch generation"
            )

        if blocking_reason == "DYNAMIC_SET_CLAUSE" or shape_family == "SET_SELECTIVE_UPDATE":
            return (
                ReasonCode.PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED,
                "dynamic set clause requires template-aware rewrite before patch generation"
            )

        if blocking_reason.startswith("DYNAMIC_FILTER_") or shape_family in {
            "IF_GUARDED_FILTER_STATEMENT",
            "IF_GUARDED_COUNT_WRAPPER",
        }:
            return (
                ReasonCode.PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED,
                "dynamic filter subtree requires template-aware rewrite before patch generation"
            )

        return None, None

    def _build_evidence(self, ctx: GateContext) -> dict:
        return build_selection_evidence(
            status=ctx.acceptance.get("status"),
            semantic_gate_status=ctx.selection.semantic_gate_status,
            semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
            acceptance=ctx.acceptance,
        )