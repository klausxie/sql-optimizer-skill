from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, write_json
from ..llm.output_validator import validate_candidates
from ..llm.retry_context import build_retry_context, should_retry, collect_validation_errors
from ..manifest import log_event
from ..platforms.sql.candidate_generation_engine import evaluate_candidate_generation
from ..platforms.sql.llm_replay_gateway import generate_optimize_candidates_with_replay
from ..platforms.sql.optimizer_sql import build_optimize_prompt, build_optimize_replay_request, generate_proposal
from ..run_paths import canonical_paths
from ..utils import statement_key, statement_key_from_row, is_sql_syntax_error
from ..verification.models import VerificationCheck, VerificationRecord
from ..verification.writer import append_verification_record
from .llm_feedback import collect_llm_feedback, save_feedback_record
from .proposal_models import (
    CANDIDATE_GENERATION_DIAGNOSTICS_KEY,
    LlmCandidate,
    LLM_CANDIDATES_KEY,
    LLM_RETRY_STATS_KEY,
    LLM_RETRY_TRACES_KEY,
    LLM_TRACE_REFS_KEY,
    LLM_VALIDATION_RESULTS_KEY,
)


@dataclass
class LlmExecutionResult:
    """LLM 执行结果"""
    raw_candidates: list[dict[str, Any]]
    valid_candidates: list[dict[str, Any]]
    trace: dict[str, Any]
    validation_results: list[dict[str, Any]]
    val_results: list[Any]
    retry_traces: list[dict[str, Any]]


def _execute_llm_with_retry(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    llm_cfg: dict[str, Any],
    config: dict[str, Any],
) -> LlmExecutionResult:
    """执行 LLM 候选生成，支持重试机制。

    Args:
        sql_unit: SQL 单元
        proposal: 优化建议
        llm_cfg: LLM 配置
        config: 全局配置

    Returns:
        LLM 执行结果
    """
    prompt = build_optimize_prompt(sql_unit, proposal, config)
    replay_request = build_optimize_replay_request(sql_unit, proposal, llm_cfg)

    retry_cfg = llm_cfg.get("retry", {}) or {}
    retry_enabled = bool(retry_cfg.get("enabled", False))
    max_retries = int(retry_cfg.get("max_retries", 2))

    raw_candidates: list[dict[str, Any]] = []
    valid_candidates: list[dict[str, Any]] = []
    trace: dict[str, Any] = {}
    validation_results: list[dict[str, Any]] = []
    val_results: list[Any] = []
    retry_traces: list[dict[str, Any]] = []

    current_attempt = 0
    last_validation_errors: list[dict[str, Any]] = []
    last_execution_error: str | None = None

    while True:
        current_attempt += 1

        # 构建重试上下文（如果是重试）
        retry_context = None
        if current_attempt > 1 and retry_enabled:
            retry_context = build_retry_context(
                attempt=current_attempt,
                max_retries=max_retries,
                validation_errors=last_validation_errors if last_validation_errors else None,
                execution_error=last_execution_error,
            )

        # 调用 LLM
        try:
            raw_candidates, trace = generate_optimize_candidates_with_replay(
                sql_unit["sqlKey"],
                sql_unit["sql"],
                llm_cfg,
                prompt=prompt,
                retry_context=retry_context,
                replay_request=replay_request,
            )
            last_execution_error = None
        except Exception as exc:
            trace = {
                "stage": "optimize",
                "mode": "candidate_generation",
                "sql_key": sql_unit["sqlKey"],
                "task_id": f"{sql_unit['sqlKey']}:opt",
                "executor": llm_cfg.get("provider", "unknown"),
                "error": str(exc),
            }
            last_execution_error = str(exc)
            raw_candidates = []

        # 记录重试 trace
        if retry_context is not None:
            retry_traces.append(trace)

        # Phase 1: LLM 输出质量控制
        validation_results = []
        valid_candidates = []
        if raw_candidates:
            valid_candidates, val_results = validate_candidates(
                candidates=raw_candidates,
                original_sql=sql_unit["sql"],
                sql_key=sql_unit["sqlKey"],
                config=config,
                sql_unit=sql_unit
            )
            validation_results = [
                {
                    "candidate_id": r.candidate_id,
                    "passed": r.passed,
                    "checks": [
                        {"type": c.check_type, "passed": c.passed, "message": c.message}
                        for c in r.checks
                    ],
                    "rejected_reason": r.rejected_reason
                }
                for r in val_results
            ]
            last_validation_errors = collect_validation_errors(val_results, raw_candidates) if not valid_candidates else []
        else:
            last_validation_errors = []

        # 判断是否重试
        force_retry_reason = None
        if last_execution_error:
            force_retry_reason = f"执行错误：{last_execution_error}"
        elif raw_candidates and not valid_candidates:
            force_retry_reason = "所有候选均未通过验证"

        do_retry, _ = should_retry(
            valid_candidates=valid_candidates,
            current_attempt=current_attempt,
            max_retries=max_retries if retry_enabled else 0,
            force_retry_reason=force_retry_reason,
        )

        if do_retry:
            continue
        else:
            break

    return LlmExecutionResult(
        raw_candidates=raw_candidates,
        valid_candidates=valid_candidates,
        trace=trace,
        validation_results=validation_results,
        val_results=val_results,
        retry_traces=retry_traces,
    )


def _build_dollar_skip_trace(sql_key: str) -> dict[str, Any]:
    """构建跳过生成时的 trace（含有 $ 占位符）。"""
    return {
        "stage": "optimize",
        "mode": "candidate_generation",
        "sql_key": sql_key,
        "task_id": f"{sql_key}:opt",
        "executor": "skip",
        "degrade_reason": "RISKY_DOLLAR_SUBSTITUTION",
        "response": {"fallback_used": True, "skip": True},
    }


def _collect_validation_errors_for_feedback(val_results: list[Any]) -> list[dict[str, str]] | None:
    """收集验证错误用于反馈。"""
    if not val_results:
        return None
    return [
        {"check_type": r.rejected_reason, "rejected_reason": r.rejected_reason}
        for r in val_results if not r.passed
    ]


def _validation_results_payload(val_results: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": r.candidate_id,
            "passed": r.passed,
            "checks": [
                {"type": c.check_type, "passed": c.passed, "message": c.message}
                for c in r.checks
            ],
            "rejected_reason": r.rejected_reason,
        }
        for r in val_results
    ]


def _init_diagnostics() -> tuple[dict[str, Any], dict[str, Any]]:
    """初始化候选生成诊断数据结构。

    Returns:
        (diagnostics, artifact): 诊断字典和诊断产物
    """
    diagnostics: dict[str, Any] = {
        "degradationKind": None,
        "recoveryAttempted": False,
        "recoveryStrategy": None,
        "recoverySucceeded": False,
        "recoveryReason": "NONE",
        "rawCandidateCount": 0,
        "validatedCandidateCount": 0,
        "acceptedCandidateCount": 0,
        "prunedLowValueCount": 0,
        "lowValueCandidateCount": 0,
        "recoveredCandidateCount": 0,
        "rawRewriteStrategies": [],
        "finalCandidateCount": 0,
    }
    return diagnostics, dict(diagnostics)


def _execute_or_skip(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    llm_cfg: dict[str, Any],
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    artifact: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """执行 LLM 候选生成或安全跳过。

    Args:
        sql_unit: SQL 单元
        proposal: 优化建议
        llm_cfg: LLM 配置
        config: 全局配置
        diagnostics: 诊断字典（会被修改）
        artifact: 诊断产物（会被修改）

    Returns:
        (trace, candidates, validation_results, val_results, retry_traces)
    """
    candidates: list[dict[str, Any]] = []

    # 判断是否需要跳过 LLM 生成
    if "${" in str(sql_unit.get("sql", "")):
        trace = _build_dollar_skip_trace(sql_unit["sqlKey"])
        validation_results: list[dict[str, Any]] = []
        val_results: list[Any] = []
        retry_traces: list[dict[str, Any]] = []
        diagnostics["recoveryReason"] = "SKIPPED_BY_SECURITY_BLOCK"
        artifact.update(diagnostics)
        return trace, candidates, validation_results, val_results, retry_traces

    result = _execute_llm_with_retry(sql_unit, proposal, llm_cfg, config)
    raw_candidates = list(result.raw_candidates)
    candidates = list(result.valid_candidates)
    trace = result.trace
    validation_results = list(result.validation_results)
    val_results = result.val_results
    retry_traces = result.retry_traces

    generation_outcome = evaluate_candidate_generation(
        sql_key=sql_unit["sqlKey"],
        original_sql=sql_unit["sql"],
        sql_unit=sql_unit,
        raw_candidates=raw_candidates,
        valid_candidates=candidates,
        trace=trace,
    )
    candidates = list(generation_outcome.accepted_candidates)
    diagnostics.update(generation_outcome.diagnostics.to_summary_dict())
    artifact.update(generation_outcome.diagnostics.to_artifact_dict())

    recovery_candidates = list(generation_outcome.recovery_candidates)
    if recovery_candidates:
        recovered_candidates, recovered_val_results = validate_candidates(
            candidates=recovery_candidates,
            original_sql=sql_unit["sql"],
            sql_key=sql_unit["sqlKey"],
            config=config,
            sql_unit=sql_unit,
        )
        if recovered_candidates:
            candidates = recovered_candidates
            val_results = recovered_val_results
            validation_results = _validation_results_payload(recovered_val_results)
            diagnostics["recoverySucceeded"] = True
            diagnostics["recoveredCandidateCount"] = len(recovered_candidates)
            diagnostics["finalCandidateCount"] = len(recovered_candidates)
            artifact["recoverySucceeded"] = True
            artifact["recoveredCandidateCount"] = len(recovered_candidates)
            artifact["finalCandidateCount"] = len(recovered_candidates)
        else:
            diagnostics["recoverySucceeded"] = False
            diagnostics["recoveryReason"] = "RECOVERY_VALIDATION_REJECTED"
            artifact["recoverySucceeded"] = False
            artifact["recoveryReason"] = "RECOVERY_VALIDATION_REJECTED"

    return trace, candidates, validation_results, val_results, retry_traces


def _save_artifacts(
    sql_unit: dict[str, Any],
    run_dir: Path,
    paths: Any,
    validator: ContractValidator,
    proposal: dict[str, Any],
    trace: dict[str, Any],
    candidate_generation_artifact: dict[str, Any],
    llm_feedback_enabled: bool,
    validation_errors_for_feedback: list[dict[str, str]] | None,
) -> None:
    """保存所有优化产物（proposal、trace、verification）。

    Args:
        sql_unit: SQL 单元
        run_dir: 运行目录
        paths: 路径对象
        validator: 合约验证器
        proposal: 优化建议
        trace: LLM 执行跟踪
        candidate_generation_artifact: 诊断产物
        llm_feedback_enabled: 是否启用 LLM 反馈
        validation_errors_for_feedback: 验证错误列表
    """
    verification_payload = _append_verification(
        run_dir,
        validator,
        sql_unit,
        sql_unit["sqlKey"],
        proposal,
        trace,
        llm_feedback_enabled,
        validation_errors_for_feedback,
    )
    proposal["verification"] = verification_payload

    # 保存 proposal
    validator.validate("optimization_proposal", proposal)
    append_jsonl(paths.proposals_path, proposal)

    # 保存 trace 和 diagnostics
    if proposal.get(LLM_TRACE_REFS_KEY):
        trace_path = run_dir / proposal[LLM_TRACE_REFS_KEY][0]
        write_json(
            trace_path,
            {
                **trace,
                "response": {**(trace.get("response") or {}), "candidates": proposal.get(LLM_CANDIDATES_KEY, [])},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        write_json(
            paths.sql_candidate_generation_diagnostics_path(sql_unit["sqlKey"]),
            candidate_generation_artifact,
        )

    # 记录完成事件
    log_event(paths.manifest_path, "optimize", "done", {"statement_key": sql_unit["sqlKey"]})


def execute_one(sql_unit: dict[str, Any], run_dir: Path, validator: ContractValidator, config: dict[str, Any]) -> dict[str, Any]:
    paths = canonical_paths(run_dir)
    llm_cfg = dict(config.get("llm", {}) or {})
    project_root = (config.get("project", {}) or {}).get("root_path")
    if isinstance(project_root, str) and project_root.strip():
        llm_cfg["opencode_workdir"] = project_root

    proposal = generate_proposal(sql_unit, config=config)

    llm_trace_ref = str(paths.sql_trace_path(str(sql_unit.get("sqlKey") or "")).relative_to(run_dir)).replace("\\", "/")
    candidate_generation_diagnostics, candidate_generation_artifact = _init_diagnostics()

    # 执行 LLM 候选生成或安全跳过
    trace, candidates, validation_results, val_results, retry_traces = _execute_or_skip(
        sql_unit, proposal, llm_cfg, config, candidate_generation_diagnostics, candidate_generation_artifact
    )

    proposal[LLM_CANDIDATES_KEY] = candidates
    proposal[CANDIDATE_GENERATION_DIAGNOSTICS_KEY] = candidate_generation_artifact
    if retry_traces:
        proposal[LLM_RETRY_TRACES_KEY] = retry_traces
        proposal[LLM_RETRY_STATS_KEY] = {
            "total_attempts": len(retry_traces) + 1,
            "successful_attempt": len(retry_traces) + 1,
        }

    # LLM trace should be persisted whenever an LLM/skip execution trace exists,
    # even if candidate validation filtered all candidates.
    if trace and any(trace.get(key) for key in ("executor", "provider", "task_id")):
        proposal[LLM_TRACE_REFS_KEY] = [llm_trace_ref]

    # 添加验证结果到 proposal
    if validation_results:
        proposal[LLM_VALIDATION_RESULTS_KEY] = validation_results

    # LLM 反馈收集配置
    diagnostics_cfg = config.get("diagnostics", {}) or {}
    llm_feedback_cfg = diagnostics_cfg.get("llm_feedback", {})
    llm_feedback_enabled = bool(llm_feedback_cfg.get("enabled", False))
    validation_errors_for_feedback = _collect_validation_errors_for_feedback(val_results) if llm_feedback_enabled else None

    # 保存产物
    _save_artifacts(
        sql_unit=sql_unit,
        run_dir=run_dir,
        paths=paths,
        validator=validator,
        proposal=proposal,
        trace=trace,
        candidate_generation_artifact=candidate_generation_artifact,
        llm_feedback_enabled=llm_feedback_enabled,
        validation_errors_for_feedback=validation_errors_for_feedback,
    )

    return proposal


def _append_verification(
    run_dir: Path,
    validator: ContractValidator,
    sql_unit: dict[str, Any],
    sql_key: str,
    proposal: dict[str, Any],
    trace: dict[str, Any],
    llm_feedback_enabled: bool,
    validation_errors_for_feedback: list[dict[str, str]] | None,
) -> dict[str, Any]:
    """追加验证记录。"""
    llm_trace_refs = [str(ref) for ref in (proposal.get(LLM_TRACE_REFS_KEY) or []) if str(ref).strip()]
    llm_candidate_count = len(proposal.get(LLM_CANDIDATES_KEY) or [])
    degrade_reason = str(trace.get("degrade_reason") or "").strip()
    actionability = dict(proposal.get("actionability") or {})
    triggered_rules = [str(row.get("ruleId") or "") for row in (proposal.get("triggeredRules") or []) if isinstance(row, dict) and str(row.get("ruleId") or "").strip()]
    db_explain_error = str(((proposal.get("dbEvidenceSummary") or {}).get("explainError")) or "").strip()
    db_explain_syntax_error = is_sql_syntax_error(db_explain_error)
    has_verdict = bool(str(proposal.get("verdict") or "").strip())
    has_analysis = bool(proposal.get("issues")) or bool(proposal.get("suggestions"))

    checks = [
        VerificationCheck("proposal_verdict_present", has_verdict, "error", None if has_verdict else "OPTIMIZE_VERDICT_MISSING"),
        VerificationCheck(
            "analysis_payload_present",
            has_analysis,
            "warn",
            None if has_analysis else "OPTIMIZE_ANALYSIS_MISSING",
        ),
        VerificationCheck(
            "llm_trace_present",
            (llm_candidate_count == 0) or bool(llm_trace_refs),
            "warn" if llm_candidate_count else "info",
            None if (llm_candidate_count == 0) or bool(llm_trace_refs) else "OPTIMIZE_LLM_TRACE_MISSING",
        ),
        VerificationCheck(
            "db_explain_syntax_ok",
            not db_explain_syntax_error,
            "warn",
            None if not db_explain_syntax_error else "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR",
            detail=db_explain_error or None,
        ),
    ]

    if not has_verdict:
        verification_status = "UNVERIFIED"
        verification_reason_code = "OPTIMIZE_PROPOSAL_UNVERIFIED"
        verification_reason_message = "optimization proposal is missing its verdict"
    elif llm_candidate_count > 0 and not llm_trace_refs:
        verification_status = "PARTIAL"
        verification_reason_code = "OPTIMIZE_LLM_TRACE_MISSING"
        verification_reason_message = "LLM candidates were generated without a corresponding trace reference"
    elif degrade_reason:
        verification_status = "PARTIAL"
        verification_reason_code = degrade_reason
        verification_reason_message = "optimization fell back to a degraded or skipped candidate generation path"
    elif db_explain_syntax_error:
        verification_status = "PARTIAL"
        verification_reason_code = "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR"
        verification_reason_message = "database EXPLAIN failed with a SQL syntax error during optimize evidence collection"
    elif not has_analysis:
        verification_status = "PARTIAL"
        verification_reason_code = "OPTIMIZE_ANALYSIS_PARTIAL"
        verification_reason_message = "proposal is structurally valid but has limited issue/suggestion evidence"
    else:
        verification_status = "VERIFIED"
        verification_reason_code = "OPTIMIZE_EVIDENCE_VERIFIED"
        verification_reason_message = "proposal includes source and candidate-generation evidence"

    payload = append_verification_record(
        run_dir,
        validator,
        VerificationRecord(
            run_id=run_dir.name,
            sql_key=sql_key,
            statement_key=statement_key(sql_key, statement_key_from_row(sql_unit)),
            phase="optimize",
            status=verification_status,
            reason_code=verification_reason_code,
            reason_message=verification_reason_message,
            evidence_refs=[str(canonical_paths(run_dir).proposals_path), *[str(run_dir / ref) for ref in llm_trace_refs]],
            inputs={
                "executor": str(trace.get("executor") or ("llm" if llm_candidate_count else "heuristic")),
                "llm_candidate_count": llm_candidate_count,
                "llm_trace_ref_count": len(llm_trace_refs),
                "degrade_reason": degrade_reason or None,
                "actionability_score": actionability.get("score"),
                "actionability_tier": actionability.get("tier"),
                "auto_patch_likelihood": actionability.get("autoPatchLikelihood"),
                "triggered_rule_count": len(triggered_rules),
                "triggered_rule_ids": triggered_rules,
                "db_explain_error": db_explain_error or None,
                "db_explain_syntax_error": db_explain_syntax_error,
            },
            checks=checks,
            verdict={
                "proposal_verdict": proposal.get("verdict"),
                "llm_candidates_present": llm_candidate_count > 0,
                "llm_trace_linked": bool(llm_trace_refs),
                "recommended_suggestion_index": proposal.get("recommendedSuggestionIndex"),
                "db_explain_error_present": bool(db_explain_error),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
    )

    # Phase 4: 保存 LLM 反馈记录（如果启用）
    if llm_feedback_enabled and validation_errors_for_feedback is not None:
        feedback_record = collect_llm_feedback(
            sql_key=sql_key,
            proposal=proposal,
            acceptance=None,
            run_id=run_dir.name,
            validation_errors=validation_errors_for_feedback,
        )
        save_feedback_record(run_dir, feedback_record)
    return payload
