from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_RUNTIME = {
    "stage_timeout_ms": {
        "preflight": 12000,
        "scan": 60000,
        "optimize": 60000,
        "validate": 60000,
        "apply": 15000,
        "report": 15000,
    },
    "stage_retry_max": {
        "preflight": 1,
        "scan": 1,
        "optimize": 1,
        "validate": 1,
        "apply": 1,
        "report": 1,
    },
    "stage_retry_backoff_ms": 1000,
}


def _resolve_project_root(cfg: dict[str, Any], *, config_path: Path) -> None:
    project_cfg = cfg.setdefault("project", {})
    root_path = project_cfg.get("root_path")
    if isinstance(root_path, str) and root_path:
        root = Path(root_path)
        if not root.is_absolute():
            project_cfg["root_path"] = str((config_path.parent / root).resolve())


def apply_minimal_defaults(cfg: dict[str, Any], *, config_path: Path) -> None:
    _resolve_project_root(cfg, config_path=config_path)

    scan_cfg = cfg.setdefault("scan", {})
    scan_cfg.setdefault("mapper_globs", ["**/*Mapper.xml", "**/*.xml"])

    db_cfg = cfg.setdefault("db", {})
    db_cfg.setdefault("schema", None)
    db_cfg.setdefault("statement_timeout_ms", 3000)
    db_cfg.setdefault("allow_explain_analyze", False)

    llm_cfg = cfg.setdefault("llm", {})
    llm_cfg.setdefault("enabled", True)
    llm_cfg.setdefault("provider", "opencode_builtin")
    llm_cfg.setdefault("timeout_ms", 15000)
    llm_cfg.setdefault("opencode_model", None)
    llm_cfg.setdefault("api_base", None)
    llm_cfg.setdefault("api_key", None)
    llm_cfg.setdefault("api_model", None)
    llm_cfg.setdefault("api_timeout_ms", None)
    llm_cfg.setdefault("api_headers", None)

    cfg["apply"] = {"mode": "PATCH_ONLY"}
    cfg["policy"] = {
        "require_perf_improvement": False,
        "cost_threshold_pct": 0,
        "allow_seq_scan_if_rows_below": 0,
        "semantic_strict_mode": True,
    }
    cfg["validate"] = {
        "db_reachable": True,
        "plan_compare_enabled": False,
        "allow_db_unreachable_fallback": True,
        "validation_profile": "balanced",
        "selection_mode": "patchability_first",
        "require_semantic_match": True,
        "require_perf_evidence_for_pass": False,
        "require_verified_evidence_for_pass": False,
        "delivery_bias": "conservative",
        "llm_semantic_check": {
            "enabled": False,
            "only_on_db_mismatch": True,
        },
    }
    cfg["patch"] = {
        "llm_assist": {
            "enabled": False,
            "only_for_dynamic_sql": True,
            "generate_template_suggestions": True,
        }
    }
    cfg["diagnostics"] = {
        "rulepacks": [{"builtin": "core"}, {"builtin": "performance"}],
        "loaded_rulepacks": [],
        "severity_overrides": {},
        "disabled_rules": [],
        "llm_feedback": {
            "enabled": False,
            "log_detected_issues": True,
            "auto_learn_patterns": False,
        },
    }
    cfg["runtime"] = deepcopy(DEFAULT_RUNTIME)
    cfg["report"] = {"enabled": bool((cfg.get("report") or {}).get("enabled", True))}
    cfg["verification"] = {"enforce_verified_outputs": False, "critical_output_policy": "warn"}
