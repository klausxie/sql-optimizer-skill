"""Error message mappings with detailed explanations and suggestions."""

from __future__ import annotations

ERROR_MESSAGES = {
    "RUN_NOT_FOUND": {
        "title": "Run ID Not Found",
        "description": "The specified run ID does not exist in the run index.",
        "causes": [
            "The run ID was typed incorrectly",
            "The run was created in a different project directory",
            "The run index file is corrupted or missing"
        ],
        "suggestions": [
            "Check the run ID for typos",
            "Use 'status' command to list available runs",
            "Verify you're in the correct project directory",
            "Check if runs/ directory exists in your project"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#run-not-found"
    },
    "CONFIG_NOT_FOUND": {
        "title": "Configuration File Not Found",
        "description": "The specified configuration file does not exist.",
        "causes": [
            "The config file path is incorrect",
            "The config file has not been created yet",
            "Insufficient permissions to read the file"
        ],
        "suggestions": [
            "Verify the --config path is correct",
            "Create sqlopt.yml from the template: cp templates/sqlopt.example.yml sqlopt.yml",
            "Check file permissions",
            "Use absolute path if relative path doesn't work"
        ],
        "doc_link": "docs/INSTALL.md#configuration"
    },
    "CONFIG_INVALID": {
        "title": "Invalid Configuration",
        "description": "The configuration file contains invalid or missing required fields.",
        "causes": [
            "Required fields are missing",
            "Field values are invalid",
            "YAML syntax errors"
        ],
        "suggestions": [
            "Compare your config with templates/sqlopt.example.yml",
            "Check for YAML syntax errors (indentation, colons, quotes)",
            "Ensure all required fields are present: project.root_path, db.dsn, scan.mapper_globs",
            "Run: python3 install/doctor.py --project <path> to validate config"
        ],
        "doc_link": "docs/INSTALL.md#configuration"
    },
    "SCANNER_JAR_NOT_FOUND": {
        "title": "Java Scanner JAR Not Found",
        "description": "The Java scanner JAR file is missing or not accessible.",
        "causes": [
            "The JAR file was not built",
            "The path in config is incorrect",
            "The skill was not installed properly"
        ],
        "suggestions": [
            "Check scan.java_scanner.jar_path in your config",
            "Reinstall the skill: python3 install/install_skill.py --project <path>",
            "Verify the JAR exists at the specified path",
            "Build the JAR manually if needed: cd java/scan-agent && mvn package"
        ],
        "doc_link": "docs/INSTALL.md#java-scanner"
    },
    "DB_CONNECTION_FAILED": {
        "title": "Database Connection Failed",
        "description": "Unable to connect to the database.",
        "causes": [
            "Database is not running",
            "Connection string (DSN) is incorrect",
            "Network connectivity issues",
            "Authentication failed"
        ],
        "suggestions": [
            "Verify database is running",
            "Check db.dsn in your config file",
            "Test connection manually: psql <connection_string>",
            "Verify username, password, host, port, and database name",
            "Check firewall and network settings",
            "If DB is optional, set validate.allow_db_unreachable_fallback=true"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#database-connection"
    },
    "SCHEMA_VALIDATION_FAILED": {
        "title": "Schema Validation Failed",
        "description": "Output data does not conform to the expected JSON schema.",
        "causes": [
            "Stage output is malformed",
            "Schema version mismatch",
            "Bug in stage implementation"
        ],
        "suggestions": [
            "Check the error details for which field failed validation",
            "Verify contract_version in runs/<run_id>/supervisor/meta.json",
            "Review the stage output file mentioned in the error",
            "Report this issue if it persists: https://github.com/your-org/sql-optimizer/issues"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#schema-validation"
    },
    "RUNTIME_RETRY_EXHAUSTED": {
        "title": "Runtime Retry Exhausted",
        "description": "The operation failed after multiple retry attempts.",
        "causes": [
            "Persistent external service failure (LLM, database)",
            "Resource constraints (timeout, memory)",
            "Unrecoverable error in stage logic"
        ],
        "suggestions": [
            "Check the detailed error in runs/<run_id>/manifest.jsonl",
            "Verify external services (LLM provider, database) are accessible",
            "Increase timeout: runtime.stage_timeout_ms in config",
            "Increase retry attempts: runtime.stage_retry_max in config",
            "Use 'resume' command to retry from the failed point"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#retry-exhausted"
    },
    "LLM_TIMEOUT": {
        "title": "LLM Request Timeout",
        "description": "The LLM request exceeded the timeout limit.",
        "causes": [
            "LLM service is slow or overloaded",
            "Network latency",
            "Request is too complex"
        ],
        "suggestions": [
            "Increase llm.timeout_ms in config",
            "Check LLM service status",
            "Try a different LLM provider",
            "Use runtime.profile=fast for simpler prompts",
            "Check network connectivity to LLM endpoint"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#llm-timeout"
    },
    "LLM_PROVIDER_ERROR": {
        "title": "LLM Provider Error",
        "description": "The LLM provider returned an error.",
        "causes": [
            "Invalid API key or credentials",
            "Rate limit exceeded",
            "Service unavailable",
            "Invalid request format"
        ],
        "suggestions": [
            "Verify llm.api_key in config (if using direct_openai_compatible)",
            "Check LLM provider service status",
            "Wait and retry if rate limited",
            "Switch to a different provider: llm.provider=heuristic (no LLM needed)",
            "Check llm.api_base URL is correct"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#llm-provider"
    },
    "PATCH_CONFLICT": {
        "title": "Patch Conflict Detected",
        "description": "The generated patch conflicts with existing code.",
        "causes": [
            "Source file was modified after scan",
            "Multiple patches target the same location",
            "Template structure changed"
        ],
        "suggestions": [
            "Review the conflict details in the patch result",
            "Manually resolve conflicts in the source file",
            "Re-run scan if source files changed significantly",
            "Use 'apply' command with caution and review changes"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#patch-conflicts"
    },
    "VERIFICATION_GATE_FAILED": {
        "title": "Verification Gate Failed",
        "description": "A critical output was produced without complete verification evidence.",
        "causes": [
            "A PASS acceptance result is marked UNVERIFIED in the verification ledger",
            "An applicable patch is marked UNVERIFIED in the verification ledger",
            "Verification evidence is incomplete for a critical output"
        ],
        "suggestions": [
            "Inspect runs/<run_id>/verification/ledger.jsonl for the failing phase evidence",
            "Review report.json validation_warnings and evidence_confidence",
            "Set verification.critical_output_policy=warn (or legacy verification.enforce_verified_outputs=false) only if you accept the risk",
            "Fix the missing evidence path before re-running release acceptance"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#verification"
    },
    "INSUFFICIENT_PERMISSIONS": {
        "title": "Insufficient Permissions",
        "description": "Unable to read or write required files.",
        "causes": [
            "File or directory permissions are too restrictive",
            "Running as wrong user",
            "Files are locked by another process"
        ],
        "suggestions": [
            "Check file and directory permissions",
            "Ensure you have read access to mapper XML files",
            "Ensure you have write access to runs/ directory",
            "Run with appropriate user permissions"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md#permissions"
    }
}


def get_error_details(reason_code: str) -> dict[str, any]:
    """Get detailed error information for a reason code.

    Args:
        reason_code: The error reason code

    Returns:
        Dictionary with error details including title, description, causes, suggestions, and doc_link
    """
    return ERROR_MESSAGES.get(reason_code, {
        "title": "Unknown Error",
        "description": f"An error occurred with code: {reason_code}",
        "causes": ["Unknown cause"],
        "suggestions": [
            "Check the error message for more details",
            "Review runs/<run_id>/manifest.jsonl for detailed logs",
            "Report this issue: https://github.com/your-org/sql-optimizer/issues"
        ],
        "doc_link": "docs/TROUBLESHOOTING.md"
    })


def format_error_message(reason_code: str, original_message: str) -> dict[str, any]:
    """Format an error message with detailed information.

    Args:
        reason_code: The error reason code
        original_message: The original error message

    Returns:
        Dictionary with formatted error information
    """
    details = get_error_details(reason_code)
    return {
        "reason_code": reason_code,
        "message": original_message,
        "title": details["title"],
        "description": details["description"],
        "possible_causes": details["causes"],
        "suggestions": details["suggestions"],
        "doc_link": details["doc_link"]
    }
