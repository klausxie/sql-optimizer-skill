from __future__ import annotations

GLOBAL_CLASSIFICATION = {
    "RUNTIME_STAGE_TIMEOUT": "retryable",
    "RUNTIME_RETRY_EXHAUSTED": "retryable",
    "UNSUPPORTED_PLATFORM": "fatal",
}

PHASE_CLASSIFICATION = {
    "scan": {
        "SCAN_CLASS_RESOLUTION_DEGRADED": "degradable",
        "SCAN_CLASS_NOT_FOUND": "degradable",
        "SCAN_TYPE_ATTR_SANITIZED": "degradable",
        "SCAN_STATEMENT_PARSE_DEGRADED": "degradable",
        "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD": "fatal",
        "SCAN_MAPPER_NOT_FOUND": "fatal",
        "SCAN_XML_PARSE_FATAL": "fatal",
        "SCAN_UNKNOWN_EXIT": "fatal",
    },
    "optimize": {},
    "validate": {
        "VALIDATE_DB_UNREACHABLE": "degradable",
        "VALIDATE_PARAM_INSUFFICIENT": "degradable",
        "VALIDATE_PERF_NOT_IMPROVED": "degradable",
        "VALIDATE_PERF_NOT_IMPROVED_WARN": "degradable",
        "VALIDATE_SEMANTIC_ERROR": "degradable",
        "VALIDATE_SEMANTIC_GATE_NOT_PASS": "degradable",
        "VALIDATE_SEMANTIC_CONFIDENCE_LOW": "degradable",
        "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION": "degradable",
        "VALIDATE_EQUIVALENCE_MISMATCH": "fatal",
        "VALIDATE_TIMEOUT": "retryable",
    },
    "patch_generate": {
        "PATCH_CONFLICT_NO_CLEAR_WINNER": "degradable",
        "PATCH_LOCATOR_AMBIGUOUS": "degradable",
        "PATCH_VALIDATION_BLOCKED_SECURITY": "degradable",
        "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS": "degradable",
        "PATCH_SEMANTIC_CONFIDENCE_LOW": "degradable",
        "PATCH_BLOCKED_BY_SEMANTIC_RISK": "fatal",
        "PATCH_GENERATION_ERROR": "retryable",
    },
    "report": {},
    "runtime": {
        "RUNTIME_SCHEMA_VALIDATION_FAILED": "fatal",
    },
}


def classify_reason_code(code: str | None, *, phase: str | None = None) -> str:
    key = str(code or "UNKNOWN")
    phase_key = str(phase or "").strip().lower()
    if phase_key and key in PHASE_CLASSIFICATION.get(phase_key, {}):
        return PHASE_CLASSIFICATION[phase_key][key]
    if key in GLOBAL_CLASSIFICATION:
        return GLOBAL_CLASSIFICATION[key]
    for mapping in PHASE_CLASSIFICATION.values():
        if key in mapping:
            return mapping[key]
    return "fatal"
