from __future__ import annotations

CONTRACT_VERSION = "v1.0.0"
SKILL_VERSION = "v1.0.0"

ROOT_KEYS = {
    "project",
    "scan",
    "db",
    "llm",
    "report",
    "config_version",
    "rules",
    "prompt_injections",
}

RUNTIME_PROFILE_DEFAULTS = {
    "fast": {
        "stage_timeout_ms": {
            "scan": 30000,
            "optimize": 20000,
            "validate": 20000,
            "apply": 10000,
            "report": 10000,
        },
        "stage_retry_max": {
            "scan": 0,
            "optimize": 0,
            "validate": 0,
            "apply": 0,
            "report": 0,
        },
        "stage_retry_backoff_ms": 500,
    },
    "balanced": {
        "stage_timeout_ms": {
            "scan": 60000,
            "optimize": 60000,
            "validate": 60000,
            "apply": 15000,
            "report": 15000,
        },
        "stage_retry_max": {
            "scan": 1,
            "optimize": 1,
            "validate": 1,
            "apply": 1,
            "report": 1,
        },
        "stage_retry_backoff_ms": 1000,
    },
    "resilient": {
        "stage_timeout_ms": {
            "scan": 90000,
            "optimize": 90000,
            "validate": 90000,
            "apply": 20000,
            "report": 20000,
        },
        "stage_retry_max": {
            "scan": 2,
            "optimize": 2,
            "validate": 2,
            "apply": 2,
            "report": 2,
        },
        "stage_retry_backoff_ms": 1500,
    },
}

ALLOWED_VALIDATE_STATUS = {"PASS", "FAIL", "NEED_MORE_PARAMS"}
REASON_CODES = {
    "UNSUPPORTED_PLATFORM",
    "SCAN_CLASS_RESOLUTION_DEGRADED",
    "SCAN_CLASS_NOT_FOUND",
    "SCAN_TYPE_ATTR_SANITIZED",
    "SCAN_STATEMENT_PARSE_DEGRADED",
    "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD",
    "SCAN_XML_PARSE_FATAL",
    "SCAN_MAPPER_NOT_FOUND",
    "SCAN_UNKNOWN_EXIT",
    "VALIDATE_DB_UNREACHABLE",
    "VALIDATE_PARAM_INSUFFICIENT",
    "VALIDATE_EQUIVALENCE_MISMATCH",
    "VALIDATE_PERF_NOT_IMPROVED",
    "VALIDATE_PERF_NOT_IMPROVED_WARN",
    "VALIDATE_SEMANTIC_ERROR",
    "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION",
    "VALIDATE_TIMEOUT",
    "PATCH_CONFLICT_NO_CLEAR_WINNER",
    "PATCH_BLOCKED_BY_SEMANTIC_RISK",
    "PATCH_LOCATOR_AMBIGUOUS",
    "PATCH_VALIDATION_BLOCKED_SECURITY",
    "PATCH_GENERATION_ERROR",
    "PREFLIGHT_CHECK_FAILED",
    "PREFLIGHT_DB_UNREACHABLE",
    "PREFLIGHT_LLM_UNREACHABLE",
    "PREFLIGHT_SCANNER_MISSING",
    "RUNTIME_STAGE_TIMEOUT",
    "RUNTIME_RETRY_EXHAUSTED",
    "RUNTIME_SCHEMA_VALIDATION_FAILED",
    "VERIFICATION_GATE_FAILED",
}
