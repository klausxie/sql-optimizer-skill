from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..io_utils import append_jsonl, write_json
from ..llm.provider import generate_llm_candidates
from ..manifest import log_event
from ..platforms.sql.optimizer_sql import build_optimize_prompt, generate_proposal
from ..verification.models import VerificationCheck, VerificationRecord
from ..verification.writer import append_verification_record


def _statement_key(sql_key: str) -> str:
    return sql_key.split("#", 1)[0]


def _is_sql_syntax_error(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    markers = [
        "syntax error",
        "you have an error in your sql syntax",
        "parse error",
        "(1064,",
    ]
    return any(marker in text for marker in markers)


def execute_one(sql_unit: dict[str, Any], run_dir: Path, validator: ContractValidator, config: dict[str, Any]) -> dict[str, Any]:
    llm_cfg = dict(config.get("llm", {}) or {})
    project_root = (config.get("project", {}) or {}).get("root_path")
    if isinstance(project_root, str) and project_root.strip():
        llm_cfg["opencode_workdir"] = project_root
    proposal = generate_proposal(sql_unit, config=config)
    candidates: list[dict[str, Any]] = []
    trace: dict[str, Any] = {}
    if "${" in str(sql_unit.get("sql", "")):
        trace = {
            "stage": "optimize",
            "mode": "candidate_generation",
            "sql_key": sql_unit["sqlKey"],
            "task_id": f"{sql_unit['sqlKey']}:opt",
            "executor": "skip",
            "degrade_reason": "RISKY_DOLLAR_SUBSTITUTION",
            "response": {"fallback_used": True, "skip": True},
        }
    else:
        prompt = build_optimize_prompt(sql_unit, proposal)
        candidates, trace = generate_llm_candidates(sql_unit["sqlKey"], sql_unit["sql"], llm_cfg, prompt=prompt)
        if candidates:
            proposal["llmCandidates"] = candidates
            proposal["llmTraceRefs"] = [f"traces/{sql_unit['sqlKey']}.optimize.llm.json"]
    validator.validate("optimization_proposal", proposal)
    append_jsonl(run_dir / "proposals" / "optimization.proposals.jsonl", proposal)
    if proposal.get("llmTraceRefs"):
        trace_path = run_dir / proposal["llmTraceRefs"][0]
        write_json(
            trace_path,
            {
                **trace,
                "response": {**(trace.get("response") or {}), "candidates": proposal.get("llmCandidates", [])},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    sql_key = str(sql_unit["sqlKey"])
    llm_trace_refs = [str(ref) for ref in (proposal.get("llmTraceRefs") or []) if str(ref).strip()]
    llm_candidate_count = len(proposal.get("llmCandidates") or [])
    degrade_reason = str(trace.get("degrade_reason") or "").strip()
    actionability = dict(proposal.get("actionability") or {})
    triggered_rules = [str(row.get("ruleId") or "") for row in (proposal.get("triggeredRules") or []) if isinstance(row, dict) and str(row.get("ruleId") or "").strip()]
    db_explain_error = str(((proposal.get("dbEvidenceSummary") or {}).get("explainError")) or "").strip()
    db_explain_syntax_error = _is_sql_syntax_error(db_explain_error)
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
    append_verification_record(
        run_dir,
        validator,
        VerificationRecord(
            run_id=run_dir.name,
            sql_key=sql_key,
            statement_key=_statement_key(sql_key),
            phase="optimize",
            status=verification_status,
            reason_code=verification_reason_code,
            reason_message=verification_reason_message,
            evidence_refs=[str(run_dir / "proposals" / "optimization.proposals.jsonl"), *[str(run_dir / ref) for ref in llm_trace_refs]],
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
    log_event(run_dir / "manifest.jsonl", "optimize", "done", {"statement_key": sql_unit["sqlKey"]})
    return proposal
