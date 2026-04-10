"""
Gate 9: Build Gate

补丁构建门控，负责生成最终的补丁。
"""

from pathlib import Path

from .gates import Gate, GateContext, GateResult, extract_fallback_reason_codes, build_selection_evidence
from .constants import ReasonCode, GateResultStatus


class BuildGate(Gate[dict]):
    """
    Gate 9: 补丁构建

    根据前面的门控结果，生成最终的补丁。
    支持两种模式：
    - 模板级补丁（从 ctx 传入已生成的 patch_text）
    - 语句级补丁（调用 build_unified_patch 生成）
    """

    def __init__(self, build_unified_fn, format_sql_fn):
        """
        初始化门控

        Args:
            build_unified_fn: 构建统一补丁的函数
            format_sql_fn: 格式化 SQL 的函数
        """
        super().__init__("Build", order=9)
        self._build_unified = build_unified_fn
        self._format_sql = format_sql_fn

    def execute(self, ctx: GateContext) -> GateResult[dict]:
        """
        执行补丁构建

        根据传入的上下文数据生成补丁：
        1. 如果已经有 patch_text（来自动态模板门控），直接使用
        2. 否则，调用 build_unified_patch 生成语句级补丁
        """
        fallback_reason_codes = extract_fallback_reason_codes(ctx.acceptance)

        # 检查是否有外部传入的 patch_text（来自动态模板门控）
        # 通过 ctx 的 context 传递
        external_patch = ctx.context.get("patch_text") if ctx.context else None

        if external_patch:
            return self._build_from_external(ctx, external_patch, fallback_reason_codes)

        # 生成语句级补丁
        return self._build_statement_patch(ctx, fallback_reason_codes)

    def _build_from_external(
        self,
        ctx: GateContext,
        patch_text: str,
        fallback_reason_codes: list[str]
    ) -> GateResult[dict]:
        """从外部传入的 patch_text 构建补丁"""
        changed_lines = ctx.context.get("changed_lines", 0)
        artifact_kind = ctx.context.get("artifact_kind", "STATEMENT")

        # 获取 statement 信息
        locators = ctx.sql_unit.get("locators") or {}
        statement_id = str((locators.get("statementId") or ctx.sql_unit.get("statementId") or "")).strip()
        statement_type = str(ctx.sql_unit.get("statementType") or "select").strip().lower()

        # 如果有 xml_path，使用它
        xml_path = Path(str(ctx.sql_unit.get("xmlPath") or ""))

        # 创建补丁文件路径
        patch_file = ctx.run_dir / "patches" / f"{ctx.sql_key.replace('/', '_')}.patch"

        # 返回成功结果，包含完整的补丁数据
        return GateResult(
            status=GateResultStatus.PASS,
            data={
                "patch_text": patch_text,
                "changed_lines": changed_lines,
                "artifact_kind": artifact_kind,
                "patch_file": str(patch_file),
            },
            context={
                "strategy": ctx.context.get("strategy", "EXACT_TEMPLATE_EDIT"),
            }
        )

    def _build_statement_patch(
        self,
        ctx: GateContext,
        fallback_reason_codes: list[str]
    ) -> GateResult[dict]:
        """生成语句级补丁"""
        dynamic_features = list(ctx.sql_unit.get("dynamicFeatures") or [])
        rewrite_materialization = dict(getattr(ctx.selection, "rewrite_materialization", {}) or {})
        if dynamic_features and str(rewrite_materialization.get("mode") or "").strip().upper() == "UNMATERIALIZABLE":
            return self.on_skip(
                ReasonCode.PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE,
                "dynamic mapper statement cannot be replaced by flattened sql",
                selection_evidence=build_selection_evidence(
                    status=ctx.acceptance.get("status"),
                    semantic_gate_status=ctx.selection.semantic_gate_status,
                    semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
                    acceptance=ctx.acceptance,
                ),
                fallback_reason_codes=fallback_reason_codes,
            )

        # 获取必要信息
        locators = ctx.sql_unit.get("locators") or {}
        statement_id = str((locators.get("statementId") or ctx.sql_unit.get("statementId") or "")).strip()
        statement_type = str(ctx.sql_unit.get("statementType") or "select").strip().lower()
        original_sql = str(ctx.sql_unit.get("sql") or "")
        rewritten_sql = ctx.selection.rewritten_sql

        xml_path = Path(str(ctx.sql_unit.get("xmlPath") or ""))

        # 格式化 SQL
        formatted_sql = self._format_sql(rewritten_sql) if rewritten_sql else rewritten_sql
        patch_sql = formatted_sql or rewritten_sql

        # 调用 build_unified_patch
        try:
            result = self._build_unified(xml_path, statement_id, statement_type, patch_sql)
            if result is None:
                patch_text, changed_lines = None, 0
            else:
                patch_text, changed_lines = result
        except Exception as e:
            # 构建失败时返回 None
            patch_text, changed_lines = None, 0

        if patch_text is None:
            return self.on_skip(
                ReasonCode.PATCH_BUILD_FAILED,
                "statement not found in mapper",
                selection_evidence=build_selection_evidence(
                    status=ctx.acceptance.get("status"),
                    semantic_gate_status=ctx.selection.semantic_gate_status,
                    semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
                    acceptance=ctx.acceptance,
                ),
                fallback_reason_codes=fallback_reason_codes,
            )

        # 创建补丁文件路径（直接构建，避免循环导入）
        patch_dir = Path(ctx.run_dir) / "patches"
        patch_file = patch_dir / f"{ctx.sql_key.replace('/', '_')}.patch"

        return GateResult(
            status=GateResultStatus.PASS,
            data={
                "patch_text": patch_text,
                "changed_lines": changed_lines,
                "artifact_kind": "STATEMENT",
                "patch_file": str(patch_file),
            },
            context={}
        )
