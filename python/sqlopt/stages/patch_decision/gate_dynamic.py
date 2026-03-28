"""
Gate 7: Dynamic Template Gate

动态模板处理门控，负责生成动态模板的补丁。
这是重点增强的模块：不再只返回 BLOCKED，而是实际尝试生成模板级补丁。
"""

import re

from .gates import Gate, GateContext, GateResult, extract_fallback_reason_codes, build_selection_evidence
from .constants import ReasonCode, GateResultStatus

# 已支持的动态模板类型
SUPPORTED_BLOCKING_REASONS = {
    "",
    "NO_TEMPLATE_PRESERVING_INTENT",
    "INCLUDE_DYNAMIC_SUBTREE",
    "DYNAMIC_FILTER_SUBTREE",
    "DYNAMIC_FILTER_NO_EFFECTIVE_DIFF",
}

SUPPORTED_SHAPE_FAMILIES = {
    "IF_GUARDED_FILTER_STATEMENT",
    "IF_GUARDED_COUNT_WRAPPER",
}

# 需人工审查的类型
REVIEW_REQUIRED_BLOCKING_REASONS = {
    "FOREACH_COLLECTION_PREDICATE",
    "FOREACH_INCLUDE_PREDICATE",
    "DYNAMIC_SET_CLAUSE",
}

_TEMPLATE_TAG_PATTERN = re.compile(r"</?(if|where|set|trim|foreach|choose|when|otherwise|bind|include)\b")


class DynamicTemplateGate(Gate[dict]):
    """
    Gate 7: 动态模板处理

    增强点：
    1. 不再只返回 BLOCKED，而是尝试生成模板级补丁
    2. 根据动态模板类型选择合适的策略
    3. 失败时才返回 BLOCKED
    """

    def __init__(
        self,
        build_template_fn,           # build_template_plan_patch
        format_template_ops_fn,       # format_template_ops_for_patch
        detect_duplicate_fn,          # detect_duplicate_clause_in_template_ops
    ):
        """
        初始化门控

        Args:
            build_template_fn: 生成模板补丁的函数
            format_template_ops_fn: 格式化模板操作的函数
            detect_duplicate_fn: 检测重复子句的函数
        """
        super().__init__("DynamicTemplate", order=7)
        self._build_template = build_template_fn
        self._format_template_ops = format_template_ops_fn
        self._detect_duplicate = detect_duplicate_fn

    def execute(self, ctx: GateContext) -> GateResult[dict]:
        dynamic_features = ctx.sql_unit.get("dynamicFeatures") or []
        fallback_reason_codes = extract_fallback_reason_codes(ctx.acceptance)

        # 无动态特征，直接通过，交给后续门控处理
        if not dynamic_features:
            return self.on_pass(ctx)

        # 尝试生成模板级补丁
        return self._try_template_patch(ctx, dynamic_features, fallback_reason_codes)

    def _try_template_patch(
        self,
        ctx: GateContext,
        dynamic_features: list,
        fallback_reason_codes: list[str]
    ) -> GateResult[dict]:
        """核心逻辑：尝试生成模板级补丁"""
        dynamic_template = ctx.selection.dynamic_template or {}
        blocking_reason = str(dynamic_template.get("blockingReason") or "").strip().upper()
        shape_family = str(dynamic_template.get("shapeFamily") or "").strip().upper()

        # Step 1: 检查是否支持当前动态模板类型
        is_supported, skip_code, skip_msg = self._check_support(blocking_reason, shape_family)

        if not is_supported:
            return self.on_skip(
                skip_code,
                skip_msg,
                selection_evidence=build_selection_evidence(
                    status=ctx.acceptance.get("status"),
                    semantic_gate_status=ctx.selection.semantic_gate_status,
                    semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
                    acceptance=ctx.acceptance,
                ),
                fallback_reason_codes=fallback_reason_codes,
            )

        # Step 2: 格式化模板操作
        template_acceptance = self._format_template_ops_for_check(ctx)

        # Step 3: 检测重复子句
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

        # Step 4: 尝试生成模板补丁
        patch_text, changed_lines, error = self._build_template(
            ctx.sql_unit, template_acceptance, ctx.run_dir
        )

        if error:
            # 生成失败，记录错误原因但继续尝试其他方式
            error_code = error.get("code", "PATCH_TEMPLATE_BUILD_FAILED")
            error_msg = error.get("message", "template patch build failed")

            # 如果有错误，返回跳过
            return self.on_skip(
                error_code,
                error_msg,
                selection_evidence=build_selection_evidence(
                    status=ctx.acceptance.get("status"),
                    semantic_gate_status=ctx.selection.semantic_gate_status,
                    semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
                    acceptance=ctx.acceptance,
                ),
                fallback_reason_codes=fallback_reason_codes,
            )

        if patch_text:
            # 成功生成模板补丁！
            return GateResult(
                status=GateResultStatus.PASS,
                data={
                    "patch_text": patch_text,
                    "changed_lines": changed_lines,
                    "artifact_kind": self._detect_artifact_kind(patch_text),
                    "strategy": self._detect_strategy(dynamic_features, dynamic_template),
                },
                context={
                    "dynamic_template_processed": True,
                    "strategy": self._detect_strategy(dynamic_features, dynamic_template),
                    "dynamic_template_blocking_reason": blocking_reason,
                }
            )

        # Step 5: 模板补丁未生成，但这是正常的（比如没有有效的重写操作）
        # 回退到语句级处理
        return self.on_pass(ctx)

    def _format_template_ops_for_check(self, ctx: GateContext) -> dict:
        """格式化模板操作用于检测"""
        # 构建 template_acceptance
        template_acceptance = dict(ctx.acceptance)

        # 添加 selectedCandidateId
        if ctx.selection.selected_candidate_id is not None:
            template_acceptance["selectedCandidateId"] = ctx.selection.selected_candidate_id

        # 添加 selectedPatchStrategy
        if hasattr(ctx.selection, 'selected_patch_strategy') and ctx.selection.selected_patch_strategy:
            template_acceptance["selectedPatchStrategy"] = dict(ctx.selection.selected_patch_strategy)

        # 添加 templateRewriteOps
        if hasattr(ctx.selection, 'template_rewrite_ops') and ctx.selection.template_rewrite_ops:
            template_acceptance["templateRewriteOps"] = [
                dict(row) for row in ctx.selection.template_rewrite_ops if isinstance(row, dict)
            ]

        # 添加 rewriteMaterialization
        if hasattr(ctx.selection, 'rewrite_materialization') and ctx.selection.rewrite_materialization:
            template_acceptance["rewriteMaterialization"] = dict(ctx.selection.rewrite_materialization)

        # 调用外部格式化函数
        return self._format_template_ops(ctx.sql_unit, template_acceptance, ctx.run_dir)

    def _check_support(self, blocking_reason: str, shape_family: str) -> tuple:
        """
        检查动态模板类型是否支持自动补丁生成

        Returns:
            (is_supported: bool, reason_code: str | None, reason_message: str | None)
        """
        # 已支持
        if blocking_reason in SUPPORTED_BLOCKING_REASONS:
            return True, None, None
        if shape_family in SUPPORTED_SHAPE_FAMILIES:
            return True, None, None
        if not blocking_reason and not shape_family:  # 无动态特征也算支持
            return True, None, None

        # 需人工审查的类型
        if blocking_reason.startswith("FOREACH_") or shape_family == "FOREACH_IN_PREDICATE":
            return False, ReasonCode.PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED, \
                "dynamic foreach predicate requires template-aware rewrite before patch generation"

        if blocking_reason == "DYNAMIC_SET_CLAUSE":
            return False, ReasonCode.PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED, \
                "dynamic set clause requires template-aware rewrite before patch generation"

        if blocking_reason.startswith("DYNAMIC_FILTER_"):
            return False, ReasonCode.PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED, \
                "dynamic filter subtree requires template-aware rewrite before patch generation"

        # 默认不支持
        return False, ReasonCode.PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE, \
            "dynamic mapper statement cannot be replaced by flattened sql"

    def _detect_artifact_kind(self, patch_text: str) -> str:
        """检测补丁产物类型"""
        if _TEMPLATE_TAG_PATTERN.search(patch_text):
            return "TEMPLATE"
        return "STATEMENT"

    def _detect_strategy(self, dynamic_features: list, dynamic_template: dict) -> str:
        """检测使用的策略类型"""
        blocking_reason = str(dynamic_template.get("blockingReason") or "").strip().upper()
        shape_family = str(dynamic_template.get("shapeFamily") or "").strip().upper()

        if "COUNT" in str(dynamic_features) or "WRAPPER" in blocking_reason:
            if "DYNAMIC" in blocking_reason:
                return "DYNAMIC_COUNT_WRAPPER_COLLAPSE"
            return "SAFE_WRAPPER_COLLAPSE"

        if "FILTER" in str(dynamic_features) or "FILTER" in blocking_reason:
            return "DYNAMIC_FILTER_WRAPPER_COLLAPSE"

        if "INCLUDE" in dynamic_features:
            return "STATIC_INCLUDE_WRAPPER_COLLAPSE"

        return "DYNAMIC_STATEMENT_TEMPLATE_EDIT"

    def _skip_for_unsupported(
        self,
        blocking_reason: str,
        shape_family: str,
        fallback_reason_codes: list[str]
    ) -> GateResult[dict]:
        """返回不支持的原因"""
        if blocking_reason.startswith("FOREACH_") or shape_family == "FOREACH_IN_PREDICATE":
            return self.on_skip(
                ReasonCode.PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED,
                "dynamic foreach predicate requires template-aware rewrite before patch generation",
            )

        if blocking_reason == "DYNAMIC_SET_CLAUSE":
            return self.on_skip(
                ReasonCode.PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED,
                "dynamic set clause requires template-aware rewrite before patch generation",
            )

        return self.on_skip(
            ReasonCode.PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED,
            "dynamic template type not supported for automatic patch generation",
        )