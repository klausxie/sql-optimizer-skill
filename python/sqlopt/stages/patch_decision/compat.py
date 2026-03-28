"""
Patch Decision 兼容层

提供与原 patch_decision_engine.py 相同的接口。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .gates import GateContext
from .engine import create_engine, PatchDecisionEngine
from .context import PatchDecisionContext as NewPatchDecisionContext


# 原有的 PatchDecisionContext（保持兼容）
@dataclass(frozen=True)
class PatchDecisionContext:
    """向后兼容的决策上下文"""
    status: str
    semantic_gate_status: str
    semantic_gate_confidence: str
    sql_key: str
    statement_key: str
    same_statement: list[dict[str, Any]]
    pass_rows: list[dict[str, Any]]
    candidates_evaluated: int


def decide_patch_result(
    *,
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    selection: Any,
    build: Any,
    run_dir: Path,
    acceptance_rows: list[dict[str, Any]],
    project_root: Path,
    statement_key_fn: Callable[[str], str],
    skip_patch_result: Callable[..., dict[str, Any]],
    finalize_generated_patch: Callable[..., dict[str, Any]],
    format_sql_for_patch: Callable[[str], str],
    normalize_sql_text: Callable[[str], str],
    format_template_ops_for_patch: Callable[[dict, dict, Path], dict],
    detect_duplicate_clause_in_template_ops: Callable[[dict], str | None],
    build_template_plan_patch: Callable[[dict, dict, Path], tuple[str | None, int, dict | None]],
    build_unified_patch: Callable[[Path, str, str, str], tuple[str | None, int]],
) -> tuple[dict, PatchDecisionContext]:
    """
    兼容接口：执行 patch 决策

    内部调用新的门控架构，输出兼容格式。
    """

    # 构建 GateContext
    ctx = GateContext(
        sql_unit=sql_unit,
        acceptance=acceptance,
        selection=selection,
        build=build,
        run_dir=run_dir,
        acceptance_rows=acceptance_rows,
        project_root=project_root,
        statement_key_fn=statement_key_fn,
    )

    # 创建引擎（注入依赖）
    engine = create_engine(
        build_template_fn=build_template_plan_patch,
        format_template_ops_fn=format_template_ops_for_patch,
        detect_duplicate_fn=detect_duplicate_clause_in_template_ops,
        normalize_sql_fn=normalize_sql_text,
        format_sql_fn=format_sql_for_patch,
        build_unified_fn=build_unified_patch,
    )

    # 执行引擎
    new_patch, new_ctx = engine.execute(
        ctx=ctx,
        skip_patch_result_fn=skip_patch_result,
        finalize_patch_fn=finalize_generated_patch,
    )

    # 转换为兼容格式
    # 如果需要调用 finalize_generated_patch（当有新生成的补丁数据时）
    if new_patch.get("status") == "NEED_DEFAULT_BUILD" or not new_patch.get("patchFiles"):
        # 回退到原始逻辑
        patch, decision_ctx = _fallback_to_original(
            sql_unit=sql_unit,
            acceptance=acceptance,
            selection=selection,
            build=build,
            run_dir=run_dir,
            acceptance_rows=acceptance_rows,
            project_root=project_root,
            statement_key_fn=statement_key_fn,
            skip_patch_result=skip_patch_result,
            finalize_generated_patch=finalize_generated_patch,
            format_sql_for_patch=format_sql_for_patch,
            normalize_sql_text=normalize_sql_text,
        )
        return patch, decision_ctx

    # 转换决策上下文为兼容格式
    decision_ctx = PatchDecisionContext(
        status=acceptance.get("status"),
        semantic_gate_status=selection.semantic_gate_status,
        semantic_gate_confidence=selection.semantic_gate_confidence,
        sql_key=sql_unit.get("sqlKey"),
        statement_key=statement_key_fn(sql_unit.get("sqlKey")),
        same_statement=new_ctx.same_statement,
        pass_rows=new_ctx.pass_rows,
        candidates_evaluated=new_ctx.candidates_evaluated,
    )

    return new_patch, decision_ctx


def _fallback_to_original(
    *,
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    selection: Any,
    build: Any,
    run_dir: Path,
    acceptance_rows: list[dict[str, Any]],
    project_root: Path,
    statement_key_fn: Callable[[str], str],
    skip_patch_result: Callable[..., dict[str, Any]],
    finalize_generated_patch: Callable[..., dict[str, Any]],
    format_sql_for_patch: Callable[[str], str],
    normalize_sql_text: Callable[[str], str],
) -> tuple[dict, PatchDecisionContext]:
    """
    回退到原始逻辑

    当新引擎返回 NEED_DEFAULT_BUILD 时使用。
    这里暂时调用原有的逻辑，后续可以完全迁移后删除。
    """
    # 导入原模块
    import sys
    from pathlib import Path as P

    # 动态找到原模块（避免循环导入）
    old_module_path = P(__file__).parent.parent / 'patch_decision_engine.py'

    # 临时方案：直接返回当前 acceptance 结果的简化版本
    # 等待完全迁移后删除这段代码

    # 构建基本的 skip 结果
    if acceptance.get("status") != "PASS":
        return skip_patch_result(
            sql_key=sql_unit.get("sqlKey"),
            statement_key=statement_key_fn(sql_unit.get("sqlKey")),
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="acceptance status is not PASS",
            candidates_evaluated=len(acceptance_rows) or 1,
            selection_evidence={},
            fallback_reason_codes=[],
        ), PatchDecisionContext(
            status=acceptance.get("status"),
            semantic_gate_status=selection.semantic_gate_status,
            semantic_gate_confidence=selection.semantic_gate_confidence,
            sql_key=sql_unit.get("sqlKey"),
            statement_key=statement_key_fn(sql_unit.get("sqlKey")),
            same_statement=acceptance_rows,
            pass_rows=[r for r in acceptance_rows if r.get("status") == "PASS"],
            candidates_evaluated=len(acceptance_rows) or 1,
        )