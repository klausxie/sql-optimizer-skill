"""Centralized registry of error reason codes.

This module provides a centralized registry of all error reason codes used
throughout the SQL Optimizer system, with categorization, severity levels,
and user-friendly messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReasonCode:
    """Represents an error reason code with metadata.

    Attributes:
        code: Unique identifier for the reason code
        category: Category of the error (runtime, validation, database, llm, scan, patch)
        severity: Severity level (fatal, retryable, degradable)
        description: Technical description of what this code means
        user_message: User-friendly message explaining the issue
    """

    code: str
    category: str
    severity: str
    description: str
    user_message: str


# Registry of all reason codes
REASON_CODES = {
    # Runtime errors
    "RUNTIME_STAGE_TIMEOUT": ReasonCode(
        code="RUNTIME_STAGE_TIMEOUT",
        category="runtime",
        severity="retryable",
        description="Stage execution exceeded timeout limit",
        user_message="The operation timed out. This may be due to slow database or LLM responses.",
    ),
    "RUNTIME_RETRY_EXHAUSTED": ReasonCode(
        code="RUNTIME_RETRY_EXHAUSTED",
        category="runtime",
        severity="fatal",
        description="Maximum retry attempts exhausted",
        user_message="The operation failed after multiple retry attempts.",
    ),
    "RUNTIME_STAGE_RETRY_EXHAUSTED": ReasonCode(
        code="RUNTIME_STAGE_RETRY_EXHAUSTED",
        category="runtime",
        severity="fatal",
        description="Stage retry attempts exhausted",
        user_message="The stage failed after multiple retry attempts.",
    ),
    # Scan errors
    "SCAN_MAPPER_NOT_FOUND": ReasonCode(
        code="SCAN_MAPPER_NOT_FOUND",
        category="scan",
        severity="fatal",
        description="No MyBatis mapper files found",
        user_message="No mapper files found matching your glob patterns. Check scan.mapper_globs configuration.",
    ),
    "SCAN_XML_PARSE_FATAL": ReasonCode(
        code="SCAN_XML_PARSE_FATAL",
        category="scan",
        severity="fatal",
        description="XML parsing failed",
        user_message="Failed to parse mapper XML files. Check for XML syntax errors.",
    ),
    "SCAN_UNKNOWN_EXIT": ReasonCode(
        code="SCAN_UNKNOWN_EXIT",
        category="scan",
        severity="fatal",
        description="Scanner exited with unknown error",
        user_message="Scanner encountered an unexpected error. Check scanner logs for details.",
    ),
    "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD": ReasonCode(
        code="SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD",
        category="scan",
        severity="degradable",
        description="Scanner coverage below acceptable threshold",
        user_message="Scanner could not fully analyze all SQL statements. Some statements may be skipped.",
    ),
    "SCAN_SELECTION_SQL_KEY_NOT_FOUND": ReasonCode(
        code="SCAN_SELECTION_SQL_KEY_NOT_FOUND",
        category="scan",
        severity="fatal",
        description="Requested SQL key does not match any scanned SQL",
        user_message="The requested SQL key did not match the scanned SQL statements. Use a more specific key or rescan the correct mapper.",
    ),
    "SCAN_SELECTION_SQL_KEY_AMBIGUOUS": ReasonCode(
        code="SCAN_SELECTION_SQL_KEY_AMBIGUOUS",
        category="scan",
        severity="fatal",
        description="Requested SQL key matched multiple scanned SQL statements",
        user_message="The requested SQL key matched multiple SQL statements. Use a namespace-qualified key or the full sqlKey.",
    ),
    "SCAN_CLASS_RESOLUTION_DEGRADED": ReasonCode(
        code="SCAN_CLASS_RESOLUTION_DEGRADED",
        category="scan",
        severity="degradable",
        description="Class resolution failed for some types",
        user_message="Could not resolve all Java class types. This may affect analysis accuracy.",
    ),
    "SCAN_DYNAMIC_EVIDENCE_PARTIAL": ReasonCode(
        code="SCAN_DYNAMIC_EVIDENCE_PARTIAL",
        category="scan",
        severity="degradable",
        description="Dynamic SQL evidence incomplete",
        user_message="Could not fully analyze dynamic SQL templates. Some optimizations may be limited.",
    ),
    "SCAN_INCLUDE_TRACE_PARTIAL": ReasonCode(
        code="SCAN_INCLUDE_TRACE_PARTIAL",
        category="scan",
        severity="degradable",
        description="Include tag tracing incomplete",
        user_message="Could not fully trace SQL fragment includes. Template analysis may be limited.",
    ),
    "SCAN_CRITICAL_EVIDENCE_MISSING": ReasonCode(
        code="SCAN_CRITICAL_EVIDENCE_MISSING",
        category="scan",
        severity="fatal",
        description="Critical scan evidence missing",
        user_message="Scanner failed to collect required information. Cannot proceed with optimization.",
    ),
    "SCAN_EVIDENCE_VERIFIED": ReasonCode(
        code="SCAN_EVIDENCE_VERIFIED",
        category="scan",
        severity="degradable",
        description="Scan evidence verified successfully",
        user_message="Scanner completed successfully with verified evidence.",
    ),
    # Optimize errors
    "OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR": ReasonCode(
        code="OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR",
        category="optimize",
        severity="degradable",
        description="SQL syntax error during EXPLAIN",
        user_message="SQL syntax error detected. The query may not be compatible with your database.",
    ),
    "OPTIMIZE_ANALYSIS_PARTIAL": ReasonCode(
        code="OPTIMIZE_ANALYSIS_PARTIAL",
        category="optimize",
        severity="degradable",
        description="Optimization analysis incomplete",
        user_message="Could not fully analyze the query. Some optimization opportunities may be missed.",
    ),
    "OPTIMIZE_PROPOSAL_UNVERIFIED": ReasonCode(
        code="OPTIMIZE_PROPOSAL_UNVERIFIED",
        category="optimize",
        severity="degradable",
        description="Optimization proposal not verified",
        user_message="Generated optimization proposal but could not verify it against the database.",
    ),
    "OPTIMIZE_EVIDENCE_VERIFIED": ReasonCode(
        code="OPTIMIZE_EVIDENCE_VERIFIED",
        category="optimize",
        severity="degradable",
        description="Optimization evidence verified",
        user_message="Optimization analysis completed with verified evidence.",
    ),
    "OPTIMIZE_LLM_TRACE_MISSING": ReasonCode(
        code="OPTIMIZE_LLM_TRACE_MISSING",
        category="optimize",
        severity="degradable",
        description="LLM trace information missing",
        user_message="LLM interaction trace is incomplete. This may affect debugging.",
    ),
    "OPTIMIZE_LLM_TIMEOUT": ReasonCode(
        code="OPTIMIZE_LLM_TIMEOUT",
        category="optimize",
        severity="degradable",
        description="LLM request timed out during optimization",
        user_message="LLM request timed out. Try increasing llm.timeout_ms in your configuration.",
    ),
    # Validate errors
    "VALIDATE_DB_UNREACHABLE": ReasonCode(
        code="VALIDATE_DB_UNREACHABLE",
        category="validate",
        severity="degradable",
        description="Database unreachable during validation",
        user_message="Cannot connect to database for validation. Using fallback validation methods.",
    ),
    "VALIDATE_EQUIVALENCE_MISMATCH": ReasonCode(
        code="VALIDATE_EQUIVALENCE_MISMATCH",
        category="validate",
        severity="fatal",
        description="Semantic equivalence check failed",
        user_message="The optimized query produces different results than the original. Cannot apply.",
    ),
    "VALIDATE_PERF_NOT_IMPROVED": ReasonCode(
        code="VALIDATE_PERF_NOT_IMPROVED",
        category="validate",
        severity="degradable",
        description="Performance not improved",
        user_message="The optimized query does not show performance improvement. Skipping.",
    ),
    "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION": ReasonCode(
        code="VALIDATE_SECURITY_DOLLAR_SUBSTITUTION",
        category="validate",
        severity="fatal",
        description="Security risk: dollar substitution removed",
        user_message="The optimization removes MyBatis dollar substitution, which may introduce SQL injection risk.",
    ),
    "VALIDATE_SEMANTIC_ERROR": ReasonCode(
        code="VALIDATE_SEMANTIC_ERROR",
        category="validate",
        severity="fatal",
        description="Semantic validation error",
        user_message="The optimized query has semantic errors. Cannot apply.",
    ),
    "VALIDATE_PARAM_INSUFFICIENT": ReasonCode(
        code="VALIDATE_PARAM_INSUFFICIENT",
        category="validate",
        severity="degradable",
        description="Insufficient parameters for validation",
        user_message="Not enough parameter information to fully validate the query.",
    ),
    "VALIDATE_CHECKS_PARTIAL": ReasonCode(
        code="VALIDATE_CHECKS_PARTIAL",
        category="validate",
        severity="degradable",
        description="Validation checks incomplete",
        user_message="Some validation checks could not be completed. Proceeding with caution.",
    ),
    "VALIDATE_PASS_SELECTION_INCOMPLETE": ReasonCode(
        code="VALIDATE_PASS_SELECTION_INCOMPLETE",
        category="validate",
        severity="degradable",
        description="Pass selection incomplete",
        user_message="Could not select the best optimization candidate. Using heuristics.",
    ),
    "VALIDATE_TEMPLATE_REPLAY_MISSING": ReasonCode(
        code="VALIDATE_TEMPLATE_REPLAY_MISSING",
        category="validate",
        severity="degradable",
        description="Template replay verification missing",
        user_message="Could not verify template rewrite by replaying. Proceeding with caution.",
    ),
    "VALIDATE_SEMANTIC_GATE_NOT_PASS": ReasonCode(
        code="VALIDATE_SEMANTIC_GATE_NOT_PASS",
        category="validate",
        severity="degradable",
        description="Semantic equivalence gate is not PASS",
        user_message="Semantic checks are not yet conclusive. Manual review is required before delivery.",
    ),
    "VALIDATE_SEMANTIC_CONFIDENCE_LOW": ReasonCode(
        code="VALIDATE_SEMANTIC_CONFIDENCE_LOW",
        category="validate",
        severity="degradable",
        description="Semantic equivalence confidence is LOW",
        user_message="Semantic confidence is low. Collect stronger evidence before delivery.",
    ),
    "VALIDATE_EVIDENCE_VERIFIED": ReasonCode(
        code="VALIDATE_EVIDENCE_VERIFIED",
        category="validate",
        severity="degradable",
        description="Validation evidence verified",
        user_message="Validation completed successfully with verified evidence.",
    ),
    # Patch errors
    "PATCH_NOT_APPLICABLE": ReasonCode(
        code="PATCH_NOT_APPLICABLE",
        category="patch",
        severity="degradable",
        description="Patch cannot be applied",
        user_message="The optimization cannot be applied to this query. Skipping.",
    ),
    "PATCH_NO_EFFECTIVE_CHANGE": ReasonCode(
        code="PATCH_NO_EFFECTIVE_CHANGE",
        category="patch",
        severity="degradable",
        description="Patch produces no effective change",
        user_message="The optimization produces no meaningful change. Skipping.",
    ),
    "PATCH_LOCATOR_AMBIGUOUS": ReasonCode(
        code="PATCH_LOCATOR_AMBIGUOUS",
        category="patch",
        severity="degradable",
        description="Patch location ambiguous",
        user_message="Cannot determine exact location to apply the patch. Manual review required.",
    ),
    "PATCH_CONFLICT_NO_CLEAR_WINNER": ReasonCode(
        code="PATCH_CONFLICT_NO_CLEAR_WINNER",
        category="patch",
        severity="degradable",
        description="Multiple conflicting patches with no clear winner",
        user_message="Multiple optimization options available with no clear best choice. Manual review required.",
    ),
    "PATCH_DECISION_EVIDENCE_INCOMPLETE": ReasonCode(
        code="PATCH_DECISION_EVIDENCE_INCOMPLETE",
        category="patch",
        severity="degradable",
        description="Patch decision evidence incomplete",
        user_message="Not enough evidence to confidently choose the best optimization. Manual review recommended.",
    ),
    "PATCH_TEMPLATE_REPLAY_NOT_VERIFIED": ReasonCode(
        code="PATCH_TEMPLATE_REPLAY_NOT_VERIFIED",
        category="patch",
        severity="degradable",
        description="Template patch replay not verified",
        user_message="Could not verify that the template patch produces the expected SQL. Manual review required.",
    ),
    "PATCH_TEMPLATE_REWRITE_UNSAFE": ReasonCode(
        code="PATCH_TEMPLATE_REWRITE_UNSAFE",
        category="patch",
        severity="degradable",
        description="Template rewrite is unsafe",
        user_message="The template rewrite may not be safe to apply. Manual review required.",
    ),
    "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS": ReasonCode(
        code="PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS",
        category="patch",
        severity="degradable",
        description="Patch generation blocked by semantic equivalence gate",
        user_message="The rewrite did not pass semantic gate checks, so patch generation is blocked.",
    ),
    "PATCH_SEMANTIC_CONFIDENCE_LOW": ReasonCode(
        code="PATCH_SEMANTIC_CONFIDENCE_LOW",
        category="patch",
        severity="degradable",
        description="Patch generation blocked by low semantic confidence",
        user_message="Semantic confidence is low, so patch generation is blocked until stronger evidence is available.",
    ),
    "PATCH_VALIDATION_BLOCKED_SECURITY": ReasonCode(
        code="PATCH_VALIDATION_BLOCKED_SECURITY",
        category="patch",
        severity="degradable",
        description="Patch generation blocked by validation security guard",
        user_message="Validation blocked automatic patch generation due unsafe ${} usage. Rewrite the mapper template safely, then retry.",
    ),
    # Platform errors
    "UNSUPPORTED_PLATFORM": ReasonCode(
        code="UNSUPPORTED_PLATFORM",
        category="platform",
        severity="fatal",
        description="Database platform not supported",
        user_message="The specified database platform is not supported. Use postgresql or mysql.",
    ),
    "INVALID_PLATFORM_ADAPTER": ReasonCode(
        code="INVALID_PLATFORM_ADAPTER",
        category="platform",
        severity="fatal",
        description="Platform adapter invalid or missing",
        user_message="The database platform adapter is not properly configured.",
    ),
    # Verification errors
    "VERIFICATION_GATE_FAILED": ReasonCode(
        code="VERIFICATION_GATE_FAILED",
        category="verification",
        severity="fatal",
        description="Verification gate check failed",
        user_message="Output verification failed. The results do not meet quality requirements.",
    ),
}


def get_reason_code(code: str) -> ReasonCode | None:
    """Get reason code metadata by code string.

    Args:
        code: Reason code string

    Returns:
        ReasonCode object if found, None otherwise
    """
    return REASON_CODES.get(code)


def format_error_message(code: str, context: dict[str, Any] | None = None) -> str:
    """Format a user-friendly error message for a reason code.

    Args:
        code: Reason code string
        context: Optional context dictionary with additional information

    Returns:
        Formatted error message
    """
    reason = get_reason_code(code)
    if not reason:
        return f"Unknown error: {code}"

    message = f"{code}: [{reason.severity.upper()}] {reason.user_message}"

    if context:
        # Add context information if available
        if "sql_key" in context:
            message += f"\nSQL: {context['sql_key']}"
        if "phase" in context:
            message += f"\nPhase: {context['phase']}"
        if "details" in context:
            message += f"\nDetails: {context['details']}"

    return message


def get_codes_by_category(category: str) -> list[ReasonCode]:
    """Get all reason codes in a specific category.

    Args:
        category: Category name (runtime, validation, database, llm, scan, patch)

    Returns:
        List of ReasonCode objects in the category
    """
    return [rc for rc in REASON_CODES.values() if rc.category == category]


def get_codes_by_severity(severity: str) -> list[ReasonCode]:
    """Get all reason codes with a specific severity.

    Args:
        severity: Severity level (fatal, retryable, degradable)

    Returns:
        List of ReasonCode objects with the severity
    """
    return [rc for rc in REASON_CODES.values() if rc.severity == severity]
