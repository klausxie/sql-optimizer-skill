# Output Validator Module
# Validates patch generation outputs

from __future__ import annotations

from typing import Any


class OutputValidator:
    """Validates patch generation outputs."""

    @staticmethod
    def validate_patch_result(result: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate a patch result.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check required fields
        required_fields = ["sqlKey", "statementKey", "deliveryOutcome"]
        for field in required_fields:
            if field not in result:
                errors.append(f"Missing required field: {field}")

        # Validate delivery outcome
        if "deliveryOutcome" in result:
            outcome = result["deliveryOutcome"]
            if "tier" not in outcome:
                errors.append("Missing deliveryOutcome.tier")
            else:
                valid_tiers = ["READY_TO_APPLY", "PATCHABLE_WITH_REWRITE", "BLOCKED", "MANUAL_REVIEW"]
                if outcome["tier"] not in valid_tiers:
                    errors.append(f"Invalid tier: {outcome['tier']}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_delivery_tier(result: dict[str, Any], expected_tier: str) -> tuple[bool, str]:
        """Validate delivery tier matches expected."""
        actual_tier = result.get("deliveryOutcome", {}).get("tier", "UNKNOWN")
        if actual_tier == expected_tier:
            return True, f"Tier matches: {expected_tier}"
        return False, f"Expected tier {expected_tier} but got {actual_tier}"

    @staticmethod
    def validate_patch_applicability(result: dict[str, Any]) -> tuple[bool, str]:
        """Validate patch is applicable if delivery tier is READY_TO_APPLY."""
        tier = result.get("deliveryOutcome", {}).get("tier", "UNKNOWN")
        if tier != "READY_TO_APPLY":
            return True, f"Not applicable for tier {tier}"

        applicable = result.get("applicable")
        if applicable is None:
            return False, "Missing applicable field for READY_TO_APPLY tier"

        if applicable:
            return True, "Patch is applicable"
        return False, f"Patch not applicable: {result.get('applyCheckError', 'unknown error')}"

    @staticmethod
    def validate_no_blocking_reasons(result: dict[str, Any]) -> tuple[bool, str]:
        """Validate there are no blocking reasons for delivery."""
        blockers = result.get("deliveryOutcome", {}).get("reasonCodes", [])
        if not blockers:
            return True, "No blocking reasons"
        return False, f"Has blocking reasons: {blockers}"

    @staticmethod
    def validate_semantic_equivalence(result: dict[str, Any]) -> tuple[bool, str]:
        """Validate semantic equivalence gate."""
        gates = result.get("gates", {})
        status = gates.get("semanticEquivalenceStatus", "UNKNOWN")
        blocking = gates.get("semanticEquivalenceBlocking", True)

        if status == "PASS" and not blocking:
            return True, "Semantic equivalence gate passed"
        return False, f"Semantic equivalence failed: status={status}, blocking={blocking}"


class SafetyValidator:
    """Validates patch safety."""

    @staticmethod
    def validate_no_dollar_substitution(result: dict[str, Any]) -> tuple[bool, str]:
        """Validate no unsafe ${} substitution in patches."""
        patch_files = result.get("patchFiles", [])
        if not patch_files:
            return True, "No patch files to validate"

        # Check if there were any dollar substitution issues
        reason_codes = result.get("deliveryOutcome", {}).get("reasonCodes", [])
        for code in reason_codes:
            if "DOLLAR" in code or "SECURITY" in code:
                return False, f"Security issue detected: {code}"

        return True, "No dollar substitution issues"

    @staticmethod
    def validate_template_stability(result: dict[str, Any]) -> tuple[bool, str]:
        """Validate template stability."""
        patchability = result.get("patchability", {})
        locator_stable = patchability.get("locatorStable", False)
        template_safe = patchability.get("templateSafePath", False)

        if locator_stable and template_safe:
            return True, "Template is stable"
        return False, f"Template instability: locatorStable={locator_stable}, templateSafePath={template_safe}"

    @staticmethod
    def validate_rewrite_safety(result: dict[str, Any]) -> tuple[bool, str]:
        """Validate rewrite safety level."""
        # Check for blocked or review status
        tier = result.get("deliveryOutcome", {}).get("tier", "UNKNOWN")
        if tier in ["BLOCKED", "PATCHABLE_WITH_REWRITE"]:
            return True, f"Rewrite safety handled: {tier}"

        # If READY_TO_APPLY, verify safety checks passed
        gates = result.get("gates", {})
        semantic_status = gates.get("semanticEquivalenceStatus")
        if semantic_status != "PASS":
            return False, f"Safety check failed: {semantic_status}"

        return True, "Rewrite safety verified"


def validate_all(result: dict[str, Any]) -> dict[str, tuple[bool, str]]:
    """Run all validations and return results."""
    return {
        "output": OutputValidator.validate_patch_result(result),
        "tier_ready": OutputValidator.validate_delivery_tier(result, "READY_TO_APPLY"),
        "applicability": OutputValidator.validate_patch_applicability(result),
        "no_blockers": OutputValidator.validate_no_blocking_reasons(result),
        "semantic_equivalence": OutputValidator.validate_semantic_equivalence(result),
        "dollar_substitution": SafetyValidator.validate_no_dollar_substitution(result),
        "template_stability": SafetyValidator.validate_template_stability(result),
        "rewrite_safety": SafetyValidator.validate_rewrite_safety(result),
    }