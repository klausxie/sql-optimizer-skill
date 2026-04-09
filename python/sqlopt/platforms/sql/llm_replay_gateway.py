from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .llm_cassette import (
    CassetteMiss,
    build_optimize_cassette_fingerprint_input,
    fingerprint_optimize_cassette_input,
    load_optimize_cassette,
    optimize_normalized_cassette_path,
    optimize_raw_cassette_path,
    save_optimize_cassette,
)
from ...llm.provider import generate_llm_candidates as _provider_generate_llm_candidates


# Re-export the live provider entry point so tests can monkeypatch the module boundary.
generate_llm_candidates = _provider_generate_llm_candidates


def _resolve_mode(llm_cfg: Mapping[str, Any]) -> str:
    mode = str(llm_cfg.get("mode") or "live").strip().lower() or "live"
    if mode not in {"live", "record", "replay"}:
        raise RuntimeError(f"unsupported llm replay mode: {mode}")
    return mode


def _resolve_model(llm_cfg: Mapping[str, Any], provider: str) -> str:
    if provider == "direct_openai_compatible":
        return str(llm_cfg.get("api_model") or "").strip()
    if provider == "opencode_run":
        return str(llm_cfg.get("opencode_model") or "").strip()
    return str(llm_cfg.get("model") or llm_cfg.get("opencode_model") or llm_cfg.get("api_model") or provider or "").strip()


def _build_replay_request(
    sql_key: str,
    sql: str,
    llm_cfg: Mapping[str, Any],
    prompt: Mapping[str, Any] | None,
    retry_context: Any | None,
    replay_request: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if replay_request is not None:
        request = dict(replay_request)
        if retry_context is not None and "retryContext" not in request:
            request["retryContext"] = _build_retry_request_context(retry_context)
        return request
    full_prompt = dict(prompt or {})
    required_context = dict(full_prompt.get("requiredContext") or {})
    optional_context = dict(full_prompt.get("optionalContext") or {})
    provider = str(llm_cfg.get("provider") or full_prompt.get("provider") or "opencode_builtin").strip()
    if not required_context:
        required_context = {
            "sql": full_prompt.get("sql") or sql or "",
            "templateSql": full_prompt.get("templateSql") or "",
            "dynamicFeatures": full_prompt.get("dynamicFeatures") or [],
            "tables": full_prompt.get("tables") or [],
            "indexes": full_prompt.get("indexes") or [],
        }
    if not optional_context and isinstance(full_prompt.get("planSummary"), dict):
        optional_context = {"planSummary": deepcopy(full_prompt.get("planSummary") or {})}
    return {
        "sqlKey": str(full_prompt.get("sqlKey") or sql_key),
        "sql": str(required_context.get("sql") or sql or ""),
        "templateSql": str(required_context.get("templateSql") or ""),
        "dynamicFeatures": list(required_context.get("dynamicFeatures") or []),
        "stableDbEvidence": {
            "tables": list(required_context.get("tables") or []),
            "indexes": list(required_context.get("indexes") or []),
            "planSummary": optional_context.get("planSummary") or {},
        },
        "retryContext": _build_retry_request_context(retry_context),
        "promptVersion": str(llm_cfg.get("prompt_version") or llm_cfg.get("promptVersion") or "v1"),
        "provider": provider,
        "model": _resolve_model(llm_cfg, provider),
    }


def _build_retry_request_context(retry_context: Any | None) -> dict[str, Any]:
    if retry_context is None:
        return {}
    return {
        "attempt": int(getattr(retry_context, "attempt", 0) or 0),
        "maxRetries": int(getattr(retry_context, "max_retries", 0) or 0),
        "errors": deepcopy(list(getattr(retry_context, "errors", []) or [])),
    }


def _replay_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    replayed = dict(trace)
    replayed["replaySourceExecutor"] = str(trace.get("executor") or "")
    replayed["replaySourceProvider"] = str(trace.get("provider") or "")
    replayed["executor"] = "replay"
    replayed["provider"] = "cassette"
    replayed["mode"] = "replay"
    return replayed


def _build_missing_replay_error(sql_key: str, fingerprint: str, cassette_root: Path) -> RuntimeError:
    normalized_path = optimize_normalized_cassette_path(cassette_root, fingerprint)
    raw_path = optimize_raw_cassette_path(cassette_root, fingerprint)
    return RuntimeError(
        "missing optimize replay cassette "
        f"sqlKey={sql_key} fingerprint={fingerprint} "
        f"normalizedPath={normalized_path} rawPath={raw_path}"
    )


def generate_optimize_candidates_with_replay(
    sql_key: str,
    sql: str,
    llm_cfg: dict[str, Any],
    *,
    prompt: dict[str, Any] | None = None,
    retry_context: Any | None = None,
    cassette_root: Path | None = None,
    replay_request: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    mode = _resolve_mode(llm_cfg)
    cassette_root = Path(cassette_root or llm_cfg.get("cassette_root") or "tests/fixtures/llm_cassettes")

    if not bool(llm_cfg.get("enabled", False)):
        return [], {"enabled": False, "mode": mode}

    request = _build_replay_request(sql_key, sql, llm_cfg, prompt, retry_context, replay_request)
    fingerprint = fingerprint_optimize_cassette_input(build_optimize_cassette_fingerprint_input(request))

    if mode == "replay":
        loaded = load_optimize_cassette(cassette_root, "normalized", fingerprint)
        if isinstance(loaded, CassetteMiss):
            raise _build_missing_replay_error(sql_key, fingerprint, cassette_root)
        candidates = loaded.get("validCandidates")
        trace = loaded.get("trace")
        if not isinstance(candidates, list) or not isinstance(trace, dict):
            raise RuntimeError(
                "invalid optimize replay cassette "
                f"sqlKey={sql_key} fingerprint={fingerprint} "
                f"path={optimize_normalized_cassette_path(cassette_root, fingerprint)}"
            )
        return candidates, _replay_trace(trace)

    candidates, trace = generate_llm_candidates(
        sql_key,
        sql,
        llm_cfg,
        prompt=prompt,
        retry_context=retry_context,
    )

    if mode == "record":
        raw_payload = {
            "fingerprint": fingerprint,
            "provider": str(llm_cfg.get("provider") or "unknown"),
            "model": request["model"],
            "promptVersion": request["promptVersion"],
            "sqlKey": sql_key,
            "request": request,
            "response": deepcopy((trace or {}).get("response") or {}),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        normalized_payload = {
            "fingerprint": fingerprint,
            "sqlKey": sql_key,
            "rawCandidateCount": len(candidates),
            "validCandidates": candidates,
            "trace": trace,
        }
        save_optimize_cassette(cassette_root, "raw", fingerprint, raw_payload)
        save_optimize_cassette(cassette_root, "normalized", fingerprint, normalized_payload)

    return candidates, trace
