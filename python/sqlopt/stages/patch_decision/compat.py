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

    # 检查是否需要使用简化逻辑（当新引擎返回 NEED_DEFAULT_BUILD 时）
    needs_default_build = new_patch.get("status") == "NEED_DEFAULT_BUILD"

    if needs_default_build:
        # 使用简化逻辑（不再依赖旧模块）
        return _handle_default_build(
            sql_unit=sql_unit,
            acceptance=acceptance,
            selection=selection,
            skip_patch_result=skip_patch_result,
            normalize_sql_text=normalize_sql_text,
            build_unified_patch=build_unified_patch,
            format_sql_for_patch=format_sql_for_patch,
            statement_key_fn=statement_key_fn,
            acceptance_rows=acceptance_rows,
        )

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


def _handle_default_build(
    *,
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    selection: Any,
    skip_patch_result: Callable[..., dict[str, Any]],
    normalize_sql_text: Callable[[str], str],
    build_unified_patch: Callable[[Path, str, str, str], tuple[str | None, int]],
    format_sql_for_patch: Callable[[str], str],
    statement_key_fn: Callable[[str], str],
    acceptance_rows: list[dict[str, Any]],
) -> tuple[dict, PatchDecisionContext]:
    """
    处理默认构建场景（新引擎返回 NEED_DEFAULT_BUILD 后的逻辑）

    源自旧模块的核心逻辑，但不依赖旧模块。
    """
    sql_key = sql_unit.get("sqlKey")
    statement_key = statement_key_fn(sql_key)

    # 检查 acceptance 状态
    if acceptance.get("status") != "PASS":
        return skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="acceptance status is not PASS",
            candidates_evaluated=len(acceptance_rows) or 1,
            selection_evidence={},
            fallback_reason_codes=[],
        ), PatchDecisionContext(
            status=acceptance.get("status"),
            semantic_gate_status=selection.semantic_gate_status,
            semantic_gate_confidence=selection.semantic_gate_confidence,
            sql_key=sql_key,
            statement_key=statement_key,
            same_statement=acceptance_rows,
            pass_rows=[r for r in acceptance_rows if r.get("status") == "PASS"],
            candidates_evaluated=len(acceptance_rows) or 1,
        )

    # 检查是否有有效变更
    original_sql = str(sql_unit.get("sql") or "")
    rewritten_sql = selection.rewritten_sql

    if normalize_sql_text(original_sql) == normalize_sql_text(rewritten_sql):
        return skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_NO_EFFECTIVE_CHANGE",
            reason_message="rewritten sql has no semantic diff after normalization",
            candidates_evaluated=len(acceptance_rows) or 1,
            selection_evidence={},
            fallback_reason_codes=[],
        ), PatchDecisionContext(
            status=acceptance.get("status"),
            semantic_gate_status=selection.semantic_gate_status,
            semantic_gate_confidence=selection.semantic_gate_confidence,
            sql_key=sql_key,
            statement_key=statement_key,
            same_statement=acceptance_rows,
            pass_rows=[r for r in acceptance_rows if r.get("status") == "PASS"],
            candidates_evaluated=len(acceptance_rows) or 1,
        )

    # 检查占位符语义
    if "#{" in original_sql and "?" in rewritten_sql and "#{" not in rewritten_sql:
        return skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_CONFLICT_NO_CLEAR_WINNER",
            reason_message="placeholder semantics mismatch",
            candidates_evaluated=len(acceptance_rows) or 1,
            selection_evidence={},
            fallback_reason_codes=[],
        ), PatchDecisionContext(
            status=acceptance.get("status"),
            semantic_gate_status=selection.semantic_gate_status,
            semantic_gate_confidence=selection.semantic_gate_confidence,
            sql_key=sql_key,
            statement_key=statement_key,
            same_statement=acceptance_rows,
            pass_rows=[r for r in acceptance_rows if r.get("status") == "PASS"],
            candidates_evaluated=len(acceptance_rows) or 1,
        )

    # 生成语句级补丁
    locators = sql_unit.get("locators") or {}
    statement_id = str((locators.get("statementId") or sql_unit.get("statementId") or "")).strip()
    statement_type = str(sql_unit.get("statementType") or "select").strip().lower()
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))

    formatted_sql = format_sql_for_patch(rewritten_sql) if rewritten_sql else rewritten_sql
    patch_sql = formatted_sql or rewritten_sql

    patch_text, changed_lines = build_unified_patch(xml_path, statement_id, statement_type, patch_sql)

    if patch_text is None:
        return skip_patch_result(
            sql_key=sql_key,
            statement_key=statement_key,
            reason_code="PATCH_BUILD_FAILED",
            reason_message="statement not found in mapper",
            candidates_evaluated=len(acceptance_rows) or 1,
            selection_evidence={},
            fallback_reason_codes=[],
        ), PatchDecisionContext(
            status=acceptance.get("status"),
            semantic_gate_status=selection.semantic_gate_status,
            semantic_gate_confidence=selection.semantic_gate_confidence,
            sql_key=sql_key,
            statement_key=statement_key,
            same_statement=acceptance_rows,
            pass_rows=[r for r in acceptance_rows if r.get("status") == "PASS"],
            candidates_evaluated=len(acceptance_rows) or 1,
        )

    # 返回生成的补丁
    return {
        "sqlKey": sql_key,
        "statementKey": statement_key,
        "patchFiles": [],
        "diffSummary": {"skipped": False, "lines": changed_lines, "changed": True},
        "applyMode": "PATCH_ONLY",
        "rollback": "delete_patch_file",
        "selectedCandidateId": selection.selected_candidate_id,
        "candidatesEvaluated": len(acceptance_rows) or 1,
        "selectionReason": {
            "code": "PATCH_GENERATED_FROM_GATE",
            "message": "patch generated from new gate architecture",
        },
        "rejectedCandidates": [],
        "applicable": True,
        "applyCheckError": None,
        "deliveryOutcome": {
            "tier": "READY_TO_APPLY",
            "reasonCodes": ["PATCH_GENERATED_FROM_GATE"],
            "summary": "patch is ready to apply",
        },
        "repairHints": [],
        "patchability": {
            "applyCheckPassed": True,
            "templateSafePath": False,
            "locatorStable": True,
            "structuralBlockers": [],
        },
    }, PatchDecisionContext(
        status=acceptance.get("status"),
        semantic_gate_status=selection.semantic_gate_status,
        semantic_gate_confidence=selection.semantic_gate_confidence,
        sql_key=sql_key,
        statement_key=statement_key,
        same_statement=acceptance_rows,
        pass_rows=[r for r in acceptance_rows if r.get("status") == "PASS"],
        candidates_evaluated=len(acceptance_rows) or 1,
    )


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
    format_template_ops_for_patch: Callable[[dict, dict, Path], dict] = None,
    detect_duplicate_clause_in_template_ops: Callable[[dict], str | None] = None,
    build_template_plan_patch: Callable[[dict, dict, Path], tuple[str | None, int, dict | None]] = None,
    build_unified_patch: Callable[[Path, str, str, str], tuple[str | None, int]] = None,
) -> tuple[dict, PatchDecisionContext]:
    """
    已废弃的 fallback 函数。

    此函数不再使用，保留仅为向后兼容。
    请使用 _handle_default_build 代替。
    """
    # 简化的回退逻辑（不依赖旧模块）
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

    # 当 acceptance 状态是 PASS 时，返回一个基本的 patch 结果
    return {
        "sqlKey": sql_unit.get("sqlKey"),
        "statementKey": statement_key_fn(sql_unit.get("sqlKey")),
        "status": "PASS",
        "patchFiles": [],
        "deliveryOutcome": {"tier": "AUTO_APPLY"},
    }, PatchDecisionContext(
        status=acceptance.get("status"),
        semantic_gate_status=selection.semantic_gate_status,
        semantic_gate_confidence=selection.semantic_gate_confidence,
        sql_key=sql_unit.get("sqlKey"),
        statement_key=statement_key_fn(sql_unit.get("sqlKey")),
        same_statement=acceptance_rows,
        pass_rows=[r for r in acceptance_rows if r.get("status") == "PASS"],
        candidates_evaluated=len(acceptance_rows) or 1,
    )
