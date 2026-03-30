"""Configuration defaults and two-tier configuration system.

SQL Optimizer uses a two-tier configuration system to separate user-facing
configuration from internal implementation details:

Configuration Flow:
┌─────────────────────────────────────────────────────────────────────┐
│                         User Config File                            │
│                      (sqlopt.yml / sqlopt.json)                     │
│                                                                      │
│  User-Facing Main Sections (6 root keys):                           │
│    • config_version: Schema version marker                          │
│    • project:  Project root path                                    │
│    • scan:     Mapper file patterns                                 │
│    • db:       Database connection                                  │
│    • llm:      LLM provider settings                                │
│    • report:   Report generation                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
                    load_config() + validation
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    apply_minimal_defaults()                         │
│                                                                      │
│  Injects Internal Sections (7 additional keys):                     │
│    • apply:        Patch application mode                           │
│    • policy:       Optimization policies                            │
│    • validate:     Validation strategies                            │
│    • patch:        Patch generation settings                        │
│    • diagnostics:  Rule packs and severity                          │
│    • runtime:      Stage timeouts and retries                       │
│    • verification: Output verification policy                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      Resolved Config                                │
│              (saved to config.resolved.json)                        │
│                                                                      │
│  Complete configuration with all defaults applied                   │
│  Used by all stages during execution                                │
└─────────────────────────────────────────────────────────────────────┘

Key Design Principles:
1. User config keeps a stable main surface (6 root keys)
2. Internal config is comprehensive and flexible (7 additional keys)
3. Users never need to specify internal sections
4. Internal sections are auto-injected with sensible defaults
5. This allows internal behavior to evolve without breaking user configs
"""

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
    """Apply default values and inject internal configuration sections.

    This function transforms user-facing configuration into a complete resolved
    configuration by:
    1. Applying defaults to user-facing sections (project, scan, db, llm, report)
    2. Injecting internal sections (apply, policy, validate, patch, diagnostics, runtime, verification)

    User-Facing Sections (with defaults):
    - config_version: Optional schema version marker (defaults handled by migration)
    - project.root_path: Resolved to absolute path
    - scan.mapper_globs: Defaults to ["**/*Mapper.xml", "**/*.xml"]
    - db.schema: Defaults to None
    - db.statement_timeout_ms: Defaults to 3000ms
    - db.allow_explain_analyze: Defaults to False
    - llm.enabled: Defaults to True
    - llm.provider: Defaults to "opencode_builtin"
    - llm.timeout_ms: Defaults to 15000ms
    - report.enabled: Defaults to True

    Internal Sections (auto-injected):
    - apply: Patch application mode (PATCH_ONLY)
    - policy: Optimization policies (performance thresholds, semantic strictness)
    - validate: Validation strategies (DB reachability, semantic matching, LLM fallback)
    - patch: Patch generation settings (LLM assist for dynamic SQL)
    - diagnostics: Rule packs and severity overrides
    - runtime: Stage timeouts and retry configuration
    - verification: Output verification policy

    Args:
        cfg: Configuration dictionary to modify in-place
        config_path: Path to the configuration file (used to resolve relative paths)

    Note:
        This function modifies cfg in-place. The resulting configuration is
        saved to runs/<run-id>/config.resolved.json for reference.

    Example:
        >>> cfg = {
        ...     "project": {"root_path": "."},
        ...     "scan": {"mapper_globs": ["src/**/*.xml"]},
        ...     "db": {"platform": "postgresql", "dsn": "postgresql://localhost/db"},
        ...     "llm": {"provider": "opencode_run"}
        ... }
        >>> apply_minimal_defaults(cfg, config_path=Path("sqlopt.yml"))
        >>> # cfg now contains resolved keys (main user keys + optional extensions + 7 internal)
        >>> assert "apply" in cfg
        >>> assert "policy" in cfg
        >>> assert "runtime" in cfg
    """
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
    cfg["diagnostics"] = {}
    cfg["runtime"] = deepcopy(DEFAULT_RUNTIME)
    cfg["report"] = {"enabled": bool((cfg.get("report") or {}).get("enabled", True))}
    cfg["verification"] = {"enforce_verified_outputs": False, "critical_output_policy": "warn"}
