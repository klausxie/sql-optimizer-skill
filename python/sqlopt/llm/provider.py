from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from .retry_context import RetryContext, build_retry_prompt


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _heuristic_candidate(sql_key: str, sql: str) -> dict[str, Any]:
    rewrite = sql.replace("SELECT *", "SELECT id") if "SELECT *" in sql.upper() else sql
    return {
        "id": f"{sql_key}:llm:c1",
        "source": "llm",
        "rewrittenSql": rewrite,
        "rewriteStrategy": "projection_minimization",
        "semanticRisk": "low",
        "confidence": "medium",
    }


def _opencode_builtin_candidate(
    sql_key: str, sql: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # No external network calls: keep candidate generation fully local/deterministic.
    candidate = _heuristic_candidate(sql_key, sql)
    if " where " not in sql.lower() and sql.strip().upper().startswith("SELECT"):
        candidate["semanticRisk"] = "medium"
        candidate["confidence"] = "low"
        candidate["rewriteStrategy"] = "opencode_builtin_guarded"
    else:
        candidate["rewriteStrategy"] = "opencode_builtin"
    return [candidate], {"fallback_used": False, "mode": "local_builtin"}


# 预编译正则表达式
_DISTINCT_SQL_RE = re.compile(r"\bselect\s+distinct\b", flags=re.IGNORECASE)


def _build_llm_user_prompt(prompt: dict[str, Any]) -> str:
    """构建 LLM 的 user_prompt，用于外部调用（保留供 skill 使用）。"""
    compact_prompt = {
        "sqlKey": prompt.get("sqlKey"),
        "sql": ((prompt.get("requiredContext") or {}).get("sql")),
        "riskFlags": ((prompt.get("requiredContext") or {}).get("riskFlags")),
        "issues": ((prompt.get("requiredContext") or {}).get("issues")),
        "tables": ((prompt.get("requiredContext") or {}).get("tables")),
        "indexes": ((prompt.get("requiredContext") or {}).get("indexes")),
        "planSummary": ((prompt.get("optionalContext") or {}).get("planSummary")),
    }
    sql_text = str(compact_prompt.get("sql") or "")
    guardrails = ""
    if re.search(
        r"\bgroup\s+by\b|\bhaving\b|\bover\s*\(|\bunion\b|^\s*with\b|\bselect\b.+\bfrom\s*\(\s*select\b",
        sql_text,
        flags=re.IGNORECASE | re.DOTALL,
    ) or _DISTINCT_SQL_RE.search(sql_text):
        guardrails = (
            "\nAdditional constraints for complex SQL:\n"
            "- Prefer structure-preserving rewrites such as removing redundant subquery wrappers or inlining a simple unnecessary CTE.\n"
            "- Preserve DISTINCT, GROUP BY, HAVING, WINDOW, and UNION semantics exactly.\n"
            "- Do not invent new WHERE predicates, time filters, or LIMIT clauses unless they already exist in the original SQL.\n"
        )
    return (
        "Generate concise SQL optimize candidates.\n"
        'Return JSON only: {"candidates": [{"id":...,"source":"llm","rewrittenSql":...,"rewriteStrategy":...,"semanticRisk":...,"confidence":...}]}\n'
        f"{guardrails}"
        f"Input:\n{json.dumps(compact_prompt, ensure_ascii=False)}"
    )


def generate_llm_candidates(
    sql_key: str,
    sql: str,
    llm_cfg: dict[str, Any],
    *,
    prompt: dict[str, Any] | None = None,
    retry_context: RetryContext | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import time

    start_time = time.time()

    enabled = bool(llm_cfg.get("enabled", False))
    if not enabled:
        return [], {"enabled": False}
    provider = llm_cfg.get("provider", "opencode_builtin")

    # 完整记录 prompt 内容
    full_prompt = prompt or {"sql": sql, "provider": provider}

    # 如果有重试上下文，构建增强的 prompt
    if retry_context is not None:
        full_prompt = build_retry_prompt(full_prompt, retry_context)

    trace: dict[str, Any] = {
        "stage": "optimize",
        "mode": "candidate_generation",
        "sql_key": sql_key,
        "task_id": f"{sql_key}:opt",
        "executor": provider,
        "task": "rewrite_sql",
        "provider": provider,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt": full_prompt,  # 完整 prompt
        "config_snapshot": {
            "provider": provider,
            "timeout_ms": llm_cfg.get("timeout_ms"),
        },
    }

    # 记录重试信息
    if retry_context is not None:
        trace["retry"] = {
            "attempt": retry_context.attempt,
            "max_retries": retry_context.max_retries,
            "error_count": len(retry_context.errors),
        }

    candidates: list[dict[str, Any]] = []
    response: dict[str, Any] = {}

    try:
        if provider == "heuristic":
            candidates = [_heuristic_candidate(sql_key, sql)]
            response = {"fallback_used": False, "mode": "local_heuristic"}
        else:
            # 默认使用本地内置模式
            candidates, response = _opencode_builtin_candidate(sql_key, sql)

        trace["response"] = response
        trace["degrade_reason"] = None
    except Exception as exc:
        # 降级模式：使用 heuristic
        candidates = [_heuristic_candidate(sql_key, sql)]
        trace["response"] = {
            "fallback_used": True,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        trace["degrade_reason"] = "EXECUTION_ERROR"

    # 增强 trace：添加完整响应和统计信息
    elapsed_ms = int((time.time() - start_time) * 1000)
    trace["elapsed_ms"] = elapsed_ms
    trace["input_hash"] = _hash_payload(trace["prompt"])
    trace["output_hash"] = _hash_payload({"candidates": candidates})

    # 添加候选方案摘要到 trace
    trace["candidate_summary"] = {
        "count": len(candidates),
        "candidates": [
            {
                "id": c.get("id"),
                "source": c.get("source"),
                "rewriteStrategy": c.get("rewriteStrategy"),
                "semanticRisk": c.get("semanticRisk"),
                "confidence": c.get("confidence"),
                # 不记录完整 rewrittenSql，避免 trace 文件过大
                "sql_preview": str(c.get("rewrittenSql", ""))[:100]
                if c.get("rewrittenSql")
                else None,
            }
            for c in candidates
        ],
    }

    return candidates, trace
