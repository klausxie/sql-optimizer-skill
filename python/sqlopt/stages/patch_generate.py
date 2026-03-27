from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, read_jsonl
from ..manifest import log_event
from ..run_paths import canonical_paths
from ..verification.patch_artifact import materialize_patch_artifact as _materialize_patch_artifact
from ..verification.patch_replay import replay_patch_target as _replay_patch_target
from ..verification.patch_syntax import verify_patch_syntax as _verify_patch_syntax
from .patching_render import (
    build_unified_patch as _build_unified_patch,
    normalize_sql_text as _normalize_sql_text,
    statement_key as _statement_key,
)
from .patching_results import selected_patch_result as _selected_patch_result
from .patching_results import skip_patch_result as _skip_patch_result
from .patching_templates import build_template_plan_patch as _build_template_plan_patch
from .patch_decision import attach_patch_diagnostics as _attach_patch_diagnostics_impl
from .patch_decision import build_patch_repair_hints as _build_patch_repair_hints_impl
from .patch_decision import should_call_llm_assist as _should_call_llm_assist_impl
from .patch_decision_engine import decide_patch_result as _decide_patch_result
from .patch_finalize import finalize_generated_patch as _finalize_generated_patch_impl
from .patch_formatting import detect_duplicate_clause_in_template_ops as _detect_duplicate_clause_in_template_ops
from .patch_formatting import format_sql_for_patch as _format_sql_for_patch
from .patch_formatting import format_template_ops_for_patch as _format_template_ops_for_patch
from .patch_generate_llm import (
    generate_template_patch_suggestion as _generate_template_patch_suggestion,
    attach_llm_suggestion_to_patch as _attach_llm_suggestion,
    save_template_suggestion as _save_template_suggestion,
)
from .patch_verification import append_patch_verification as _append_patch_verification


def _check_patch_applicable(patch_file: Path, workdir: Path) -> tuple[bool, str | None]:
    try:
        proc = subprocess.run(
            ["git", "apply", "--check", str(patch_file)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, None
    detail = (proc.stderr or proc.stdout or "git apply --check failed").strip()
    return False, detail


def _build_patch_repair_hints(reason_code: str, apply_check_error: str | None, sql_unit: dict) -> list[dict]:
    return _build_patch_repair_hints_impl(reason_code, apply_check_error, sql_unit)


def _attach_patch_diagnostics(patch: dict, sql_unit: dict, acceptance: dict) -> dict:
    return _attach_patch_diagnostics_impl(patch, sql_unit, acceptance)


def _finalize_generated_patch(
    *,
    sql_key: str,
    statement_key: str,
    patch_file: Path,
    patch_text: str,
    changed_lines: int,
    candidates_evaluated: int,
    selected_candidate_id: str | None,
    patch_target: dict[str, Any] | None,
    no_effect_message: str,
    workdir: Path,
) -> dict:
    return _finalize_generated_patch_impl(
        sql_key=sql_key,
        statement_key=statement_key,
        patch_file=patch_file,
        patch_text=patch_text,
        changed_lines=changed_lines,
        candidates_evaluated=candidates_evaluated,
        selected_candidate_id=selected_candidate_id,
        patch_target=patch_target,
        no_effect_message=no_effect_message,
        workdir=workdir,
        check_patch_applicable=_check_patch_applicable,
        selected_patch_result=_selected_patch_result,
        skip_patch_result=_skip_patch_result,
    )


def execute_one(sql_unit: dict, acceptance: dict, run_dir: Path, validator: ContractValidator, config: dict[str, Any] | None = None) -> dict:
    paths = canonical_paths(run_dir)
    acceptance_rows = read_jsonl(paths.acceptance_path)
    fragment_rows = read_jsonl(paths.scan_fragments_path) if paths.scan_fragments_path.exists() else []
    fragment_catalog = {str(row.get("fragmentKey") or ""): row for row in fragment_rows if str(row.get("fragmentKey") or "").strip()}

    project_root = Path.cwd().resolve()
    configured_root = str((((config or {}).get("project", {}) or {}).get("root_path") or "")).strip()
    if configured_root:
        candidate_root = Path(configured_root).resolve()
        if candidate_root.exists():
            project_root = candidate_root

    patch, decision_ctx = _decide_patch_result(
        sql_unit=sql_unit,
        acceptance=acceptance,
        run_dir=run_dir,
        acceptance_rows=acceptance_rows,
        project_root=project_root,
        statement_key_fn=_statement_key,
        skip_patch_result=_skip_patch_result,
        finalize_generated_patch=_finalize_generated_patch,
        format_sql_for_patch=_format_sql_for_patch,
        normalize_sql_text=_normalize_sql_text,
        format_template_ops_for_patch=_format_template_ops_for_patch,
        detect_duplicate_clause_in_template_ops=_detect_duplicate_clause_in_template_ops,
        build_template_plan_patch=_build_template_plan_patch,
        build_unified_patch=_build_unified_patch,
    )
    sql_key = decision_ctx.sql_key
    patch_target = dict(acceptance.get("patchTarget") or {})

    if patch.get("applicable") is True and patch_target:
        selected_patch_file = next(iter(patch.get("patchFiles") or []), None)
        patch_text = Path(selected_patch_file).read_text(encoding="utf-8") if selected_patch_file and Path(selected_patch_file).exists() else ""
        artifact_result = _materialize_patch_artifact(sql_unit=sql_unit, patch_text=patch_text)
        replay_result = _replay_patch_target(
            sql_unit=sql_unit,
            patch_target=patch_target,
            fragment_catalog=fragment_catalog,
            patch_text=patch_text,
            artifact=artifact_result,
        )
        syntax_result = _verify_patch_syntax(
            sql_unit=sql_unit,
            patch_target=patch_target,
            patch_text=patch_text,
            replay_result=replay_result,
            artifact=artifact_result,
        )
        patch["patchTarget"] = patch_target
        patch["replayEvidence"] = {
            "matchesTarget": replay_result.matches_target,
            "renderedSql": replay_result.rendered_sql,
            "normalizedRenderedSql": replay_result.normalized_rendered_sql,
            "driftReason": replay_result.drift_reason,
        }
        patch["syntaxEvidence"] = syntax_result.to_dict()
        if replay_result.matches_target is not True or syntax_result.ok is not True:
            reason_code = replay_result.drift_reason or syntax_result.reason_code or "PATCH_TARGET_DRIFT"
            reason_message = "generated patch does not replay back to the persisted patch target"
            patch = _skip_patch_result(
                sql_key=decision_ctx.sql_key,
                statement_key=decision_ctx.statement_key,
                reason_code=reason_code,
                reason_message=reason_message,
                candidates_evaluated=decision_ctx.candidates_evaluated,
                selected_candidate_id=patch_target.get("selectedCandidateId"),
                patch_target=patch_target,
                replay_evidence=patch["replayEvidence"],
                syntax_evidence=patch["syntaxEvidence"],
            )

    patch = _attach_patch_diagnostics(patch, sql_unit, acceptance)

    # Phase 5: LLM 模板辅助（可选）
    patch_cfg = (config or {}).get("patch", {}) or {}
    llm_assist_cfg = patch_cfg.get("llm_assist", {})
    llm_assist_enabled = bool(llm_assist_cfg.get("enabled", False))
    only_for_dynamic_sql = bool(llm_assist_cfg.get("only_for_dynamic_sql", True))

    llm_suggestion = None
    if llm_assist_enabled:
        # 判断是否需要 LLM 辅助
        dynamic_features = [str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()]
        is_dynamic_sql = bool(dynamic_features)

        # 仅在动态 SQL 或配置允许时调用
        if not only_for_dynamic_sql or is_dynamic_sql:
            # 当 patch 被跳过或需要人工审查时，调用 LLM 辅助
            if _should_call_llm_assist_impl(patch):
                llm_cfg = (config or {}).get("llm", {}) or {}
                llm_suggestion = _generate_template_patch_suggestion(
                    sql_unit=sql_unit,
                    acceptance=acceptance,
                    patch_result=patch,
                    llm_cfg=llm_cfg,
                )

                if llm_suggestion:
                    # 保存建议到文件
                    _save_template_suggestion(run_dir, sql_key, llm_suggestion)
                    # 附加到 patch 结果
                    patch = _attach_llm_suggestion(patch, llm_suggestion)

    validator.validate("patch_result", patch)
    append_jsonl(paths.patches_path, patch)
    _append_patch_verification(
        run_dir=run_dir,
        validator=validator,
        patch=patch,
        acceptance=acceptance,
        status=decision_ctx.status,
        semantic_gate_status=decision_ctx.semantic_gate_status,
        semantic_gate_confidence=decision_ctx.semantic_gate_confidence,
        sql_key=decision_ctx.sql_key,
        statement_key=decision_ctx.statement_key,
        same_statement=decision_ctx.same_statement,
        pass_rows=decision_ctx.pass_rows,
    )
    log_event(
        paths.manifest_path,
        "patch_generate",
        "done",
        {"statement_key": decision_ctx.sql_key},
    )
    return patch
