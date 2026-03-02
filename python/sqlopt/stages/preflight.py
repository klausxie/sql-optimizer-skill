from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..errors import StageError
from ..io_utils import write_json
from ..llm.provider import _extract_json_events, _opencode_env
from ..platforms.dispatch import check_db_connectivity
from .preflight_strategy import DbCheckPolicy, LlmCheckPolicy, ScannerCheckPolicy, build_preflight_policy
from ..subprocess_utils import run_capture_text


def _check_db(config: dict[str, Any], policy: DbCheckPolicy | None = None) -> dict[str, Any]:
    resolved = policy or build_preflight_policy(config).db
    if not resolved.enabled:
        return {"name": "db", "enabled": False, "ok": True, "reason": resolved.reason}
    return check_db_connectivity(config)


def _check_opencode(config: dict[str, Any], policy: LlmCheckPolicy | None = None) -> dict[str, Any]:
    resolved = policy or build_preflight_policy(config).llm
    if not resolved.enabled:
        return {"name": "llm", "enabled": False, "ok": True, "reason": resolved.reason}
    if not shutil.which("opencode"):
        return {"name": "llm", "enabled": True, "ok": False, "error": "opencode command not found", "reason_code": "PREFLIGHT_LLM_UNREACHABLE"}
    llm_cfg = (config.get("llm", {}) or {}) if isinstance(config, dict) else {}
    cmd = ["opencode", "run", "--format", "json", "--variant", "minimal"]
    opencode_model = str(llm_cfg.get("opencode_model") or "").strip()
    if opencode_model:
        cmd.extend(["-m", opencode_model])
    cmd.append("ping")
    timeout_ms = int(llm_cfg.get("timeout_ms", 15000))
    try:
        proc = run_capture_text(
            cmd,
            timeout_s=max(1000, timeout_ms) / 1000.0,
            env=_opencode_env(),
        )
    except Exception as exc:
        return {"name": "llm", "enabled": True, "ok": False, "error": str(exc), "reason_code": "PREFLIGHT_LLM_UNREACHABLE"}
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}"
        return {"name": "llm", "enabled": True, "ok": False, "error": detail, "reason_code": "PREFLIGHT_LLM_UNREACHABLE"}
    _, err = _extract_json_events(proc.stdout)
    if err:
        return {"name": "llm", "enabled": True, "ok": False, "error": err, "reason_code": "PREFLIGHT_LLM_UNREACHABLE"}
    return {"name": "llm", "enabled": True, "ok": True}


def _check_direct_openai(config: dict[str, Any], policy: LlmCheckPolicy | None = None) -> dict[str, Any]:
    resolved = policy or build_preflight_policy(config).llm
    if not resolved.enabled:
        return {"name": "llm", "enabled": False, "ok": True, "reason": resolved.reason}
    llm_cfg = (config.get("llm", {}) or {}) if isinstance(config, dict) else {}
    api_base = str(llm_cfg.get("api_base") or "").strip().rstrip("/")
    api_key = str(llm_cfg.get("api_key") or "").strip()
    api_model = str(llm_cfg.get("api_model") or "").strip()
    if not api_base or not api_key or not api_model:
        return {
            "name": "llm",
            "enabled": True,
            "ok": False,
            "error": "direct_openai_compatible requires api_base/api_key/api_model",
            "reason_code": "PREFLIGHT_LLM_UNREACHABLE",
        }
    timeout_ms = int(llm_cfg.get("api_timeout_ms") or llm_cfg.get("timeout_ms", 15000))
    payload = {
        "model": api_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "{\"ping\":true}"},
        ],
    }
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
            body = (resp.read() or b"").decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = (exc.read() or b"").decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        return {
            "name": "llm",
            "enabled": True,
            "ok": False,
            "error": f"http_error={exc.code} detail={detail[:200]}",
            "reason_code": "PREFLIGHT_LLM_UNREACHABLE",
        }
    except Exception as exc:
        return {"name": "llm", "enabled": True, "ok": False, "error": str(exc), "reason_code": "PREFLIGHT_LLM_UNREACHABLE"}
    if not body.strip():
        return {"name": "llm", "enabled": True, "ok": False, "error": "empty response body", "reason_code": "PREFLIGHT_LLM_UNREACHABLE"}
    return {"name": "llm", "enabled": True, "ok": True}


def _check_scanner(config: dict[str, Any], policy: ScannerCheckPolicy | None = None) -> dict[str, Any]:
    resolved = policy or build_preflight_policy(config).scanner
    if not resolved.enabled:
        return {"name": "scanner", "enabled": False, "ok": True, "reason": resolved.reason}
    java_cfg = ((config.get("scan", {}) or {}).get("java_scanner", {}) or {})
    jar_path = str(java_cfg.get("jar_path") or "").strip()
    p = Path(jar_path)
    if not p.is_absolute():
        project_root = Path(str((config.get("project", {}) or {}).get("root_path") or ".")).resolve()
        p = (project_root / p).resolve()
    if not p.exists():
        return {
            "name": "scanner",
            "enabled": True,
            "ok": False,
            "error": f"jar not found: {p}",
            "reason_code": "PREFLIGHT_SCANNER_MISSING",
        }
    return {"name": "scanner", "enabled": True, "ok": True, "jar_path": str(p)}


def execute(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    policy = build_preflight_policy(config)
    if policy.llm.mode == "direct_openai_compatible":
        llm_check = _check_direct_openai(config, policy.llm)
    elif policy.llm.mode == "opencode_run":
        llm_check = _check_opencode(config, policy.llm)
    else:
        llm_check = {"name": "llm", "enabled": False, "ok": True, "reason": policy.llm.reason}
    checks = [
        _check_db(config, policy.db),
        llm_check,
        _check_scanner(config, policy.scanner),
    ]
    ok = all(bool(x.get("ok")) for x in checks)
    result = {
        "run_id": run_dir.name,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "checks": checks,
    }
    write_json(run_dir / "ops" / "preflight.json", result)
    if not ok:
        failed = [row for row in checks if not row.get("ok")]
        details = []
        for row in failed:
            details.append(f"{row.get('name')}: {row.get('error')}")
        reason_code = "PREFLIGHT_CHECK_FAILED"
        if len(failed) == 1 and failed[0].get("reason_code"):
            reason_code = str(failed[0]["reason_code"])
        raise StageError(f"preflight failed: {'; '.join(details)}", reason_code=reason_code)
    return result
