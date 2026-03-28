"""
Gate 6: Template Gate

模板重复检查门控，验证模板重写操作是否有重复子句。
"""

from .gates import Gate, GateContext, GateResult, extract_fallback_reason_codes, build_selection_evidence
from .constants import ReasonCode


class TemplateGate(Gate[None]):
    """
    Gate 6: 模板重复检查

    验证 template_rewrite_ops 中是否有重复的子句
    （如重复的 WHERE、ORDER BY 等）。
    如果有重复，生成补丁可能导致 XML 格式错误。
    """

    def __init__(self, detect_duplicate_fn):
        """
        初始化门控

        Args:
            detect_duplicate_fn: 检测模板操作中重复子句的函数
        """
        super().__init__("Template", order=6)
        self._detect_duplicate = detect_duplicate_fn

    def execute(self, ctx: GateContext) -> GateResult[None]:
        fallback_reason_codes = extract_fallback_reason_codes(ctx.acceptance)

        # 如果 build 有 template_rewrite_ops，进行重复检查
        if hasattr(ctx.build, 'template_rewrite_ops') and ctx.build.template_rewrite_ops:
            template_acceptance = dict(ctx.acceptance)
            if ctx.selection.selected_candidate_id is not None:
                template_acceptance["selectedCandidateId"] = ctx.selection.selected_candidate_id

            template_acceptance["templateRewriteOps"] = [
                dict(row) for row in ctx.build.template_rewrite_ops if isinstance(row, dict)
            ]

            # 检测重复子句
            duplicate_clause = self._detect_duplicate(template_acceptance)

            if duplicate_clause:
                return self.on_skip(
                    ReasonCode.PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED,
                    f"template rewrite contains duplicated {duplicate_clause} clause",
                    selection_evidence=build_selection_evidence(
                        status=ctx.acceptance.get("status"),
                        semantic_gate_status=ctx.selection.semantic_gate_status,
                        semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
                        acceptance=ctx.acceptance,
                    ),
                    fallback_reason_codes=fallback_reason_codes,
                )

        return self.on_pass(ctx)

    def _format_template_ops(self, template_acceptance: dict, sql_unit: dict) -> dict:
        """
        格式化模板操作

        Args:
            template_acceptance: 模板级别的接受结果
            sql_unit: SQL 单元

        Returns:
            格式化后的模板操作
        """
        # 这个方法由 engine 在调用前通过 format_template_ops_for_patch 预处理
        # 门控只负责调用检测函数
        return template_acceptance