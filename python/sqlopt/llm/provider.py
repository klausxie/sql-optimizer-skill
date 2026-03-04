from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..subprocess_utils import run_capture_text
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


def _opencode_builtin_candidate(sql_key: str, sql: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # No external network calls: keep candidate generation fully local/deterministic.
    candidate = _heuristic_candidate(sql_key, sql)
    if " where " not in sql.lower() and sql.strip().upper().startswith("SELECT"):
        candidate["semanticRisk"] = "medium"
        candidate["confidence"] = "low"
        candidate["rewriteStrategy"] = "opencode_builtin_guarded"
    else:
        candidate["rewriteStrategy"] = "opencode_builtin"
    return [candidate], {"fallback_used": False, "mode": "local_builtin"}


def _extract_json_events(stdout: str) -> tuple[list[str], str | None]:
    texts: list[str] = []
    error_message: str | None = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        event_type = payload.get("type")
        if event_type == "error":
            error = payload.get("error")
            if isinstance(error, dict):
                data = error.get("data")
                if isinstance(data, dict) and data.get("message"):
                    error_message = str(data.get("message"))
                else:
                    error_message = str(error)
            else:
                error_message = str(payload.get("error"))
        if event_type == "text":
            part = payload.get("part")
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    return texts, error_message


def _parse_text_json(text: str) -> dict[str, Any]:
    candidates: list[str] = []
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)
    if "```" in stripped:
        parts = stripped.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 1:
                part = part.strip()
                if part.lower().startswith("json"):
                    part = part[4:].strip()
                if part:
                    candidates.append(part)
    start_obj, end_obj = stripped.find("{"), stripped.rfind("}")
    if start_obj >= 0 and end_obj > start_obj:
        candidates.append(stripped[start_obj : end_obj + 1])
    start_arr, end_arr = stripped.find("["), stripped.rfind("]")
    if start_arr >= 0 and end_arr > start_arr:
        candidates.append(stripped[start_arr : end_arr + 1])

    for raw in candidates:
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list):
            return {"candidates": payload}
    # Last fallback: treat output as a single rewritten SQL string.
    if stripped and ("\n" not in stripped or len(stripped.splitlines()) <= 3):
        return {
            "candidates": [
                {
                    "id": "fallback:text",
                    "source": "llm",
                    "rewrittenSql": stripped,
                    "rewriteStrategy": "opencode_text_fallback",
                    "semanticRisk": "medium",
                    "confidence": "low",
                }
            ]
        }
    raise ValueError("unexpected llm output")


def _run_opencode(sql_key: str, prompt: dict[str, Any], llm_cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not shutil.which("opencode"):
        raise RuntimeError("opencode command not found")
    opencode_model = str(llm_cfg.get("opencode_model") or "").strip()
    timeout_ms = int(llm_cfg.get("timeout_ms", 15000))
    cmd = ["opencode", "run", "--format", "json"]
    opencode_workdir = str(llm_cfg.get("opencode_workdir") or "").strip()
    if opencode_workdir:
        cmd.extend(["--dir", opencode_workdir])
    if opencode_model:
        cmd.extend(["-m", opencode_model])
    variant = str(llm_cfg.get("variant", "minimal")).strip()
    if variant:
        cmd.extend(["--variant", variant])
    compact_prompt = {
        "sqlKey": prompt.get("sqlKey"),
        "sql": ((prompt.get("requiredContext") or {}).get("sql")),
        "riskFlags": ((prompt.get("requiredContext") or {}).get("riskFlags")),
        "issues": ((prompt.get("requiredContext") or {}).get("issues")),
        "tables": ((prompt.get("requiredContext") or {}).get("tables")),
        "indexes": ((prompt.get("requiredContext") or {}).get("indexes")),
        "planSummary": ((prompt.get("optionalContext") or {}).get("planSummary")),
    }
    user_prompt = (
        "Generate concise SQL optimize candidates.\n"
        "Return JSON only: {\"candidates\": [{\"id\":...,\"source\":\"llm\",\"rewrittenSql\":...,\"rewriteStrategy\":...,\"semanticRisk\":...,\"confidence\":...}]}\n"
        f"Input:\n{json.dumps(compact_prompt, ensure_ascii=False)}"
    )
    cmd.append(user_prompt)
    proc = run_capture_text(
        cmd,
        timeout_s=max(1000, timeout_ms) / 1000.0,
        env=_opencode_env(),
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"opencode run failed: {detail}")
    texts, err = _extract_json_events(proc.stdout)
    if err:
        raise RuntimeError(f"opencode error: {err}")
    if not texts:
        raise RuntimeError("opencode no text payload")
    payload = _parse_text_json(texts[-1])
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise RuntimeError("opencode bad response: missing candidates")
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        rewritten = str(row.get("rewrittenSql") or "").strip()
        if not rewritten:
            continue
        out.append(
            {
                "id": str(row.get("id") or f"{sql_key}:llm:c{i}"),
                "source": "llm",
                "rewrittenSql": rewritten,
                "rewriteStrategy": str(row.get("rewriteStrategy") or "opencode_run"),
                "semanticRisk": str(row.get("semanticRisk") or "medium").lower(),
                "confidence": str(row.get("confidence") or "low").lower(),
            }
        )
    if not out:
        raise RuntimeError("opencode produced no valid candidates")
    return out, {"fallback_used": False, "mode": "opencode_run"}


def _direct_openai_request(payload: dict[str, Any], llm_cfg: dict[str, Any]) -> dict[str, Any]:
    api_base = str(llm_cfg.get("api_base") or "").strip().rstrip("/")
    api_key = str(llm_cfg.get("api_key") or "").strip()
    model = str(llm_cfg.get("api_model") or "").strip()
    if not api_base or not api_key or not model:
        raise RuntimeError("direct_openai_compatible requires api_base/api_key/api_model")
    timeout_ms = int(llm_cfg.get("api_timeout_ms") or llm_cfg.get("timeout_ms", 15000))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    extra_headers = llm_cfg.get("api_headers") or {}
    if isinstance(extra_headers, dict):
        for k, v in extra_headers.items():
            if isinstance(k, str) and isinstance(v, str):
                headers[k] = v
    req = urllib.request.Request(
        url=f"{api_base}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(1000, timeout_ms) / 1000.0) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = (exc.read() or b"").decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"direct_openai_compatible http_error={exc.code} detail={detail[:300]}") from exc
    except Exception as exc:
        raise RuntimeError(f"direct_openai_compatible request failed: {exc}") from exc
    try:
        row = json.loads(body.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise RuntimeError("direct_openai_compatible bad json response") from exc
    if not isinstance(row, dict):
        raise RuntimeError("direct_openai_compatible invalid response payload")
    return row


def _extract_openai_message_content(row: dict[str, Any]) -> str:
    choices = row.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("direct_openai_compatible missing choices")
    message = (choices[0] or {}).get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise RuntimeError("direct_openai_compatible missing message")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts)
    raise RuntimeError("direct_openai_compatible missing message content")


def _run_direct_openai_compatible(sql_key: str, prompt: dict[str, Any], llm_cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model = str(llm_cfg.get("api_model") or "").strip()
    compact_prompt = {
        "sqlKey": prompt.get("sqlKey"),
        "sql": ((prompt.get("requiredContext") or {}).get("sql")),
        "riskFlags": ((prompt.get("requiredContext") or {}).get("riskFlags")),
        "issues": ((prompt.get("requiredContext") or {}).get("issues")),
        "tables": ((prompt.get("requiredContext") or {}).get("tables")),
        "indexes": ((prompt.get("requiredContext") or {}).get("indexes")),
        "planSummary": ((prompt.get("optionalContext") or {}).get("planSummary")),
    }
    user_prompt = (
        "Generate concise SQL optimize candidates.\n"
        "Return JSON only: {\"candidates\": [{\"id\":...,\"source\":\"llm\",\"rewrittenSql\":...,\"rewriteStrategy\":...,\"semanticRisk\":...,\"confidence\":...}]}\n"
        f"Input:\n{json.dumps(compact_prompt, ensure_ascii=False)}"
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": user_prompt},
        ],
    }
    row = _direct_openai_request(payload, llm_cfg)
    content = _extract_openai_message_content(row)
    parsed = _parse_text_json(content)
    candidates = parsed.get("candidates")
    if not isinstance(candidates, list):
        raise RuntimeError("direct_openai_compatible missing candidates")
    out: list[dict[str, Any]] = []
    for i, cand in enumerate(candidates, start=1):
        if not isinstance(cand, dict):
            continue
        rewritten = str(cand.get("rewrittenSql") or "").strip()
        if not rewritten:
            continue
        out.append(
            {
                "id": str(cand.get("id") or f"{sql_key}:llm:c{i}"),
                "source": "llm",
                "rewrittenSql": rewritten,
                "rewriteStrategy": str(cand.get("rewriteStrategy") or "direct_openai_compatible"),
                "semanticRisk": str(cand.get("semanticRisk") or "medium").lower(),
                "confidence": str(cand.get("confidence") or "low").lower(),
            }
        )
    if not out:
        raise RuntimeError("direct_openai_compatible produced no valid candidates")
    return out, {"fallback_used": False, "mode": "direct_openai_compatible"}


def _opencode_env() -> dict[str, str]:
    env = os.environ.copy()
    cwd = Path.cwd()
    if not env.get("XDG_DATA_HOME"):
        env["XDG_DATA_HOME"] = str((cwd / ".opencode-data").resolve())
    data_home = Path(env["XDG_DATA_HOME"])
    data_home.mkdir(parents=True, exist_ok=True)
    if not env.get("XDG_CONFIG_HOME"):
        home = Path(env.get("HOME") or str(Path.home()))
        opencode_cfg = home / ".opencode"
        if opencode_cfg.exists():
            env["XDG_CONFIG_HOME"] = str(opencode_cfg)
    return env


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
            "opencode_model": llm_cfg.get("opencode_model"),
            "api_model": llm_cfg.get("api_model"),
        }
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
        elif provider == "opencode_run":
            candidates, response = _run_opencode(sql_key, full_prompt, llm_cfg)
        elif provider == "direct_openai_compatible":
            candidates, response = _run_direct_openai_compatible(sql_key, full_prompt, llm_cfg)
        else:
            candidates, response = _opencode_builtin_candidate(sql_key, sql)

        trace["response"] = response
        trace["degrade_reason"] = None
    except Exception as exc:
        if provider in {"opencode_run", "direct_openai_compatible"}:
            # 严格模式：直接抛出
            trace["response"] = {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
            trace["degrade_reason"] = "EXECUTION_ERROR"
            raise
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
                "sql_preview": str(c.get("rewrittenSql", ""))[:100] if c.get("rewrittenSql") else None
            }
            for c in candidates
        ]
    }

    return candidates, trace
