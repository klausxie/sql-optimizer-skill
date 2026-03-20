"""LLM-assisted patch generation for complex dynamic SQL.

This module provides LLM-assisted template-level rewriting suggestions
for cases where automatic patch generation fails.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...io_utils import write_json
from ...run_paths import canonical_paths


@dataclass
class TemplatePatchSuggestion:
    """Template patch suggestion from LLM."""

    suggestion_type: str  # "TEMPLATE_MODIFY" | "FRAGMENT_EXPAND" | "MANUAL_REVIEW"
    template_diff: str | None  # Template diff
    manual_guidance: str | None  # Manual guidance
    confidence: str = "medium"  # Confidence level
    reasoning: str | None = None  # Reasoning explanation
    referenced_fragments: list[str] = field(
        default_factory=list
    )  # Referenced fragments

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_template_patch_prompt(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    patch_result: dict[str, Any],
) -> dict[str, Any]:
    """Build prompt for template patch suggestion.

    Args:
        sql_unit: SQL unit
        proposal: Validated optimization proposal
        patch_result: Patch generation result

    Returns:
        Prompt dictionary for LLM call
    """
    original_template = str(sql_unit.get("templateSql") or "")
    rewritten_sql = str(
        proposal.get("optimizedSql") or proposal.get("rewrittenSql") or ""
    )
    dynamic_features = list(sql_unit.get("dynamicFeatures") or [])
    include_trace = sql_unit.get("includeTrace") or []
    dynamic_trace = sql_unit.get("dynamicTrace") or {}
    include_fragments = dynamic_trace.get("includeFragments") or []

    # Collect skip reason
    selection_reason = patch_result.get("selectionReason") or {}
    reason_code = str(selection_reason.get("code") or "")
    reason_message = str(selection_reason.get("message") or "")

    return {
        "task": "mybatis_template_patch_suggestion",
        "original_template": original_template,
        "rewritten_sql": rewritten_sql,
        "dynamic_features": dynamic_features,
        "include_fragments": [
            {
                "fragmentId": f.get("fragmentId"),
                "fragmentSql": f.get("fragmentSql"),
                "dynamicFeatures": f.get("dynamicFeatures"),
            }
            for f in include_fragments
            if isinstance(f, dict)
        ],
        "patch_skip_reason": {
            "code": reason_code,
            "message": reason_message,
        },
        "guidance_request": "请分析如何将改写的 SQL 适配回原始模板结构，提供具体的修改建议",
    }


def _parse_llm_template_suggestion(
    response_text: str, prompt: dict[str, Any]
) -> TemplatePatchSuggestion:
    """Parse LLM response into TemplatePatchSuggestion.

    Args:
        response_text: LLM response text
        prompt: Original prompt

    Returns:
        TemplatePatchSuggestion object
    """
    response_lower = response_text.lower()

    # Determine suggestion type
    suggestion_type = "MANUAL_REVIEW"  # Default
    if "template" in response_lower and "modify" in response_lower:
        suggestion_type = "TEMPLATE_MODIFY"
    elif "fragment" in response_lower and "expand" in response_lower:
        suggestion_type = "FRAGMENT_EXPAND"
    elif "manual" in response_lower or "review" in response_lower:
        suggestion_type = "MANUAL_REVIEW"

    # Extract confidence
    confidence = "medium"
    if "high" in response_lower or "高置信度" in response_lower:
        confidence = "high"
    elif "low" in response_lower or "低置信度" in response_lower:
        confidence = "low"

    # Extract reasoning
    reasoning = response_text.strip()[:500]  # Limit length

    # Extract template diff (if any)
    template_diff = None
    diff_markers = ["```diff", "```patch", "```xml"]
    for marker in diff_markers:
        if marker in response_text:
            start = response_text.find(marker) + len(marker)
            end = response_text.find("```", start)
            if end > start:
                template_diff = response_text[start:end].strip()
                break

    # Extract manual guidance
    manual_guidance = None
    guidance_markers = ["建议：", "建议:", "guidance:", "recommendation:", "指导："]
    for marker in guidance_markers:
        if marker in response_lower:
            start = response_lower.find(marker) + len(marker)
            end = response_text.find("\n", start)
            if end > start:
                manual_guidance = response_text[start:end].strip()
                break

    # Extract referenced fragments
    referenced_fragments: list[str] = []
    if "fragment" in response_lower:
        import re

        fragment_refs = re.findall(r"ref\.(\w+)", response_text, re.IGNORECASE)
        referenced_fragments = list(set(fragment_refs))[:5]  # Max 5

    return TemplatePatchSuggestion(
        suggestion_type=suggestion_type,
        template_diff=template_diff,
        manual_guidance=manual_guidance or reasoning,
        confidence=confidence,
        reasoning=reasoning,
        referenced_fragments=referenced_fragments,
    )


def generate_template_patch_suggestion(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    patch_result: dict[str, Any],
    llm_cfg: dict[str, Any],
) -> TemplatePatchSuggestion | None:
    """Generate template patch suggestion using LLM.

    Args:
        sql_unit: SQL unit
        proposal: Validated optimization proposal
        patch_result: Patch generation result
        llm_cfg: LLM configuration

    Returns:
        TemplatePatchSuggestion or None if LLM not enabled
    """
    if not llm_cfg.get("enabled", False):
        return None

    prompt = build_template_patch_prompt(sql_unit, proposal, patch_result)
    response_text = "建议使用模板级改写；CLI 内置模式无法执行深度分析"
    return _parse_llm_template_suggestion(response_text, prompt)


def save_template_suggestion(
    run_dir: Path,
    sql_key: str,
    suggestion: TemplatePatchSuggestion,
) -> None:
    """Save template suggestion to file.

    Args:
        run_dir: Run directory
        sql_key: SQL identifier
        suggestion: Template suggestion
    """
    suggestions_dir = canonical_paths(run_dir).ops_dir / "template_suggestions"
    suggestions_dir.mkdir(parents=True, exist_ok=True)

    suggestion_file = suggestions_dir / f"{sql_key.replace('/', '_')}.suggestion.json"

    suggestion_data = {
        **suggestion.to_dict(),
        "sql_key": sql_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    write_json(suggestion_file, suggestion_data)


def attach_llm_suggestion_to_patch(
    patch_result: dict[str, Any],
    suggestion: TemplatePatchSuggestion | None,
) -> dict[str, Any]:
    """Attach LLM suggestion to patch result.

    Args:
        patch_result: Patch generation result
        suggestion: LLM template suggestion

    Returns:
        Updated patch result
    """
    if suggestion is None:
        return patch_result

    patch_result["llmTemplateSuggestion"] = {
        "suggestionType": suggestion.suggestion_type,
        "confidence": suggestion.confidence,
        "manualGuidance": suggestion.manual_guidance,
        "reasoning": suggestion.reasoning,
        "referencedFragments": suggestion.referenced_fragments,
    }

    if suggestion.template_diff:
        patch_result["llmTemplateSuggestion"]["templateDiff"] = suggestion.template_diff

    # Update repair hints
    if "repairHints" not in patch_result:
        patch_result["repairHints"] = []

    if suggestion.suggestion_type != "MANUAL_REVIEW":
        patch_result["repairHints"].append(
            {
                "hintId": "llm-template-suggestion",
                "title": f"LLM suggested {suggestion.suggestion_type}",
                "detail": suggestion.reasoning[:200]
                if suggestion.reasoning
                else "LLM provided template modification guidance",
                "actionType": "LLM_ASSISTED",
                "command": None,
            }
        )

    return patch_result


def collect_template_suggestions(run_dir: Path) -> list[dict[str, Any]]:
    """Collect all template suggestions.

    Args:
        run_dir: Run directory

    Returns:
        List of template suggestions
    """
    suggestions_dir = canonical_paths(run_dir).ops_dir / "template_suggestions"
    if not suggestions_dir.exists():
        return []

    suggestions: list[dict[str, Any]] = []
    for suggestion_file in suggestions_dir.glob("*.suggestion.json"):
        try:
            with open(suggestion_file, "r", encoding="utf-8") as f:
                suggestion = json.load(f)
                suggestions.append(suggestion)
        except (json.JSONDecodeError, Exception):
            continue

    return suggestions


def generate_template_suggestion_summary(
    suggestions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate summary of template suggestions.

    Args:
        suggestions: List of template suggestions

    Returns:
        Summary statistics dictionary
    """
    total = len(suggestions)

    # Count by type and confidence
    type_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}

    for suggestion in suggestions:
        suggestion_type = str(suggestion.get("suggestionType", "UNKNOWN"))
        confidence = str(suggestion.get("confidence", "unknown"))

        type_counts[suggestion_type] = type_counts.get(suggestion_type, 0) + 1
        confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

    return {
        "total_suggestions": total,
        "suggestion_type_distribution": type_counts,
        "confidence_distribution": confidence_counts,
        "high_confidence_suggestions": sum(
            1 for s in suggestions if s.get("confidence") == "high"
        ),
    }
