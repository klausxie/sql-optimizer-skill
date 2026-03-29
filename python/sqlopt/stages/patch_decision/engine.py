"""
Patch Decision Engine

决策引擎，负责编排所有门控按顺序执行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .gates import Gate, GateContext, GateResult
from .constants import GateResultStatus, DeliveryTier, ReasonCode
from .context import PatchDecisionContext


@dataclass
class EngineConfig:
    """引擎配置"""
    stop_on_first_skip: bool = True  # 遇到 SKIP 是否继续
    enable_dynamic_template: bool = True  # 是否启用动态模板处理


class PatchDecisionEngine:
    """
    Patch 决策引擎

    职责：
    1. 编排所有门控按顺序执行
    2. 收集门控结果，生成最终补丁决策
    3. 处理向后兼容
    """

    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        self._gates: list[Gate] = []

    def register(self, gate: Gate) -> "PatchDecisionEngine":
        """注册门控"""
        self._gates.append(gate)
        self._gates.sort(key=lambda g: g.order)
        return self

    def execute(
        self,
        ctx: GateContext,
        skip_patch_result_fn: Callable | None = None,
        finalize_patch_fn: Callable | None = None,
    ) -> tuple[dict, PatchDecisionContext]:
        """
        执行所有门控，返回最终结果

        Args:
            ctx: 门控执行上下文
            skip_patch_result_fn: 生成跳过结果的函数（向后兼容）
            finalize_patch_fn: 完成补丁生成的函数（向后兼容）

        Returns:
            (patch_result: dict, decision_context: PatchDecisionContext)
        """
        results: list[GateResult] = []
        last_pass_data: dict | None = None

        for gate in self._gates:
            # 将前一个门控的 pass 数据传递到 context 中
            if last_pass_data:
                ctx.context.update(last_pass_data)

            result = gate.execute(ctx)
            results.append(result)

            # 收集 pass 数据
            if result.is_pass and result.data:
                last_pass_data = result.data

            # 如果遇到 SKIP 且配置要求停止
            if result.is_skip and self.config.stop_on_first_skip:
                return self._build_skip_result(result, ctx, results), self._build_context(ctx, results)

        # 所有门控通过，生成成功结果
        return self._build_success_result(results, ctx, skip_patch_result_fn, finalize_patch_fn), self._build_context(ctx, results)

    def _build_skip_result(
        self,
        result: GateResult,
        ctx: GateContext,
        results: list[GateResult]
    ) -> dict:
        """构建跳过结果"""
        tier = ReasonCode.map_to_tier(result.reason_code)

        # 合并上下文中的额外数据
        extra_context = {}
        for r in results:
            if r.context:
                extra_context.update(r.context)

        return {
            "sqlKey": ctx.sql_key,
            "statementKey": ctx.statement_key,
            "patchFiles": [],
            "diffSummary": {"skipped": True},
            "applyMode": "PATCH_ONLY",
            "rollback": "not_applied",
            "selectionReason": {
                "code": result.reason_code,
                "message": result.reason_message,
            },
            "rejectedCandidates": [{"reason_code": result.reason_code}],
            "candidatesEvaluated": len(ctx.acceptance_rows) or 1,
            "selectionEvidence": result.context.get("selection_evidence", {}) or {},
            "fallbackReasonCodes": list(result.context.get("fallback_reason_codes", []) or []),
            "deliveryOutcome": {
                "tier": tier,
                "reasonCodes": [result.reason_code] if result.reason_code else [],
                "summary": result.reason_message or "",
            },
            "repairHints": [],
            "patchability": {
                "applyCheckPassed": None,
                "templateSafePath": False,
                "locatorStable": True,
                "structuralBlockers": [result.reason_code] if result.reason_code else [],
            },
        }

    def _build_success_result(
        self,
        results: list[GateResult],
        ctx: GateContext,
        skip_patch_result_fn: Callable | None,
        finalize_patch_fn: Callable | None,
    ) -> dict:
        """构建成功结果"""

        # 从结果中提取补丁数据
        patch_data = None
        strategy = "EXACT_TEMPLATE_EDIT"
        for r in reversed(results):
            if r.is_pass and r.data and "patch_text" in r.data:
                patch_data = r.data
                strategy = r.context.get("strategy", strategy)
                break

        if patch_data:
            # 有预生成的补丁数据（来自动态模板门控）
            return self._build_patch_from_data(patch_data, ctx, strategy)

        # 回退到默认处理（由调用方处理）
        # 这里返回一个待处理的标记
        return {
            "sqlKey": ctx.sql_key,
            "statementKey": ctx.statement_key,
            "status": "NEED_DEFAULT_BUILD",
            "selectionEvidence": {
                "acceptanceStatus": ctx.acceptance.get("status"),
                "semanticGateStatus": ctx.selection.semantic_gate_status,
                "semanticGateConfidence": ctx.selection.semantic_gate_confidence,
            },
        }

    def _build_patch_from_data(
        self,
        patch_data: dict,
        ctx: GateContext,
        strategy: str = "EXACT_TEMPLATE_EDIT"
    ) -> dict:
        """从门控数据构建补丁结果"""
        patch_text = patch_data.get("patch_text", "")
        changed_lines = patch_data.get("changed_lines", 0)
        artifact_kind = patch_data.get("artifact_kind", "STATEMENT")

        # 创建补丁文件
        patch_file = Path(patch_data.get("patch_file", ""))
        patch_file.parent.mkdir(parents=True, exist_ok=True)

        # 写入补丁文件
        if patch_text:
            patch_file.write_text(patch_text, encoding="utf-8")

        return {
            "sqlKey": ctx.sql_key,
            "statementKey": ctx.statement_key,
            "patchFiles": [str(patch_file)] if patch_file.exists() else [],
            "diffSummary": {"lines": changed_lines, "changed": True if patch_text else False},
            "applyMode": "PATCH_ONLY",
            "rollback": "delete_patch_file" if patch_text else "not_applied",
            "selectedCandidateId": ctx.selection.selected_candidate_id,
            "candidatesEvaluated": len(ctx.acceptance_rows) or 1,
            "selectionReason": {
                "code": "PATCH_SELECTED_SINGLE_PASS",
                "message": "single pass variant",
            },
            "rejectedCandidates": [],
            "applicable": True,
            "applyCheckError": None,
            "deliveryOutcome": {
                "tier": DeliveryTier.READY_TO_APPLY.value,
                "reasonCodes": ["PATCH_SELECTED_SINGLE_PASS"],
                "summary": "patch is ready to apply",
            },
            "repairHints": [],
            "patchability": {
                "applyCheckPassed": True,
                "templateSafePath": artifact_kind == "TEMPLATE",
                "locatorStable": True,
                "structuralBlockers": [],
            },
            "gates": {
                "semanticEquivalenceStatus": "PASS",
                "semanticEquivalenceBlocking": False,
                "semanticConfidence": ctx.selection.semantic_gate_confidence,
            },
            "strategyType": strategy,
            "fallbackApplied": False,
        }

    def _build_context(self, ctx: GateContext, results: list[GateResult]) -> PatchDecisionContext:
        """构建决策上下文（向后兼容）"""
        statement_key = ctx.statement_key

        # 查找同一 statement 的所有接受结果
        same_statement = [
            row for row in ctx.acceptance_rows
            if ctx.statement_key_fn(str(row.get("sqlKey", ""))) == statement_key
        ]

        # 查找 PASS 的候选
        pass_rows = [row for row in same_statement if row.get("status") == "PASS"]

        return PatchDecisionContext(
            status=ctx.acceptance.get("status"),
            semantic_gate_status=ctx.selection.semantic_gate_status,
            semantic_gate_confidence=ctx.selection.semantic_gate_confidence,
            sql_key=ctx.sql_key,
            statement_key=statement_key,
            same_statement=same_statement,
            pass_rows=pass_rows,
            candidates_evaluated=len(same_statement) or 1,
        )


def create_engine(
    build_template_fn: Callable,
    format_template_ops_fn: Callable,
    detect_duplicate_fn: Callable,
    normalize_sql_fn: Callable,
    format_sql_fn: Callable,
    build_unified_fn: Callable,
) -> PatchDecisionEngine:
    """
    创建默认配置的决策引擎

    Args:
        build_template_fn: build_template_plan_patch
        format_template_ops_fn: format_template_ops_for_patch
        detect_duplicate_fn: detect_duplicate_clause_in_template_ops
        normalize_sql_fn: normalize_sql_text
        format_sql_fn: format_sql_for_patch
        build_unified_fn: build_unified_patch

    Returns:
        配置好的 PatchDecisionEngine
    """
    from .gate_locator import LocatorGate
    from .gate_acceptance import AcceptanceGate
    from .gate_semantic import SemanticGate
    from .gate_candidate import CandidateGate
    from .gate_change import ChangeGate
    from .gate_template import TemplateGate
    from .gate_dynamic import DynamicTemplateGate
    from .gate_placeholder import PlaceholderGate
    from .gate_build import BuildGate

    engine = PatchDecisionEngine()

    # 注册所有门控（按 order 排序）
    engine.register(LocatorGate())
    engine.register(AcceptanceGate())
    engine.register(SemanticGate())
    engine.register(CandidateGate())
    engine.register(ChangeGate(normalize_sql_fn))
    engine.register(TemplateGate(detect_duplicate_fn))
    engine.register(DynamicTemplateGate(
        build_template_fn,
        format_template_ops_fn,
        detect_duplicate_fn,
    ))
    engine.register(PlaceholderGate())
    engine.register(BuildGate(build_unified_fn, format_sql_fn))

    return engine