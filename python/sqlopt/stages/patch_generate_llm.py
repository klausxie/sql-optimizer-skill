"""patch_generate 阶段 LLM 辅助功能

对于复杂动态 SQL，引入 LLM 生成模板级改写建议。
主要用于：
1. 当自动 patch 生成失败时，提供 LLM 辅助建议
2. 为动态 SQL 模板提供改写指导
3. 生成人工审查所需的上下文信息
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..io_utils import write_json


@dataclass
class TemplatePatchSuggestion:
    """模板补丁建议"""
    suggestion_type: str  # "TEMPLATE_MODIFY" | "FRAGMENT_EXPAND" | "MANUAL_REVIEW"
    template_diff: str | None  # 模板差异
    manual_guidance: str | None  # 人工指导
    confidence: str = "medium"  # 置信度
    reasoning: str | None = None  # 推理说明
    referenced_fragments: list[str] = field(default_factory=list)  # 引用的片段

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_template_patch_prompt(
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    patch_result: dict[str, Any],
) -> dict[str, Any]:
    """构建模板补丁建议的 prompt

    Args:
        sql_unit: SQL 单元
        acceptance: 验证接受结果
        patch_result: 补丁生成结果

    Returns:
        用于 LLM 调用的 prompt 字典
    """
    original_template = str(sql_unit.get("templateSql") or "")
    rewritten_sql = str(acceptance.get("rewrittenSql") or "")
    dynamic_features = list(sql_unit.get("dynamicFeatures") or [])
    include_trace = sql_unit.get("includeTrace") or []
    dynamic_trace = sql_unit.get("dynamicTrace") or {}
    include_fragments = dynamic_trace.get("includeFragments") or []

    # 收集跳过的原因
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
            for f in include_fragments if isinstance(f, dict)
        ],
        "patch_skip_reason": {
            "code": reason_code,
            "message": reason_message,
        },
        "guidance_request": "请分析如何将改写的 SQL 适配回原始模板结构，提供具体的修改建议",
    }


def _parse_llm_template_suggestion(response_text: str, prompt: dict[str, Any]) -> TemplatePatchSuggestion:
    """解析 LLM 返回的模板建议

    Args:
        response_text: LLM 响应文本
        prompt: 原始 prompt

    Returns:
        TemplatePatchSuggestion 对象
    """
    response_lower = response_text.lower()

    # 判断建议类型
    suggestion_type = "MANUAL_REVIEW"  # 默认
    if "template" in response_lower and "modify" in response_lower:
        suggestion_type = "TEMPLATE_MODIFY"
    elif "fragment" in response_lower and "expand" in response_lower:
        suggestion_type = "FRAGMENT_EXPAND"
    elif "manual" in response_lower or "review" in response_lower:
        suggestion_type = "MANUAL_REVIEW"

    # 提取置信度
    confidence = "medium"
    if "high" in response_lower or "高置信度" in response_lower:
        confidence = "high"
    elif "low" in response_lower or "低置信度" in response_lower:
        confidence = "low"

    # 提取推理说明
    reasoning = response_text.strip()[:500]  # 限制长度

    # 提取模板差异（如果有）
    template_diff = None
    diff_markers = ["```diff", "```patch", "```xml"]
    for marker in diff_markers:
        if marker in response_text:
            start = response_text.find(marker) + len(marker)
            end = response_text.find("```", start)
            if end > start:
                template_diff = response_text[start:end].strip()
                break

    # 提取人工指导
    manual_guidance = None
    guidance_markers = ["建议：", "建议:", "guidance:", "recommendation:", "指导："]
    for marker in guidance_markers:
        if marker in response_lower:
            start = response_lower.find(marker) + len(marker)
            end = response_text.find("\n", start)
            if end > start:
                manual_guidance = response_text[start:end].strip()
                break

    # 提取引用的片段
    referenced_fragments: list[str] = []
    if "fragment" in response_lower:
        # 简单提取 fragment 引用
        import re
        fragment_refs = re.findall(r'ref\.(\w+)', response_text, re.IGNORECASE)
        referenced_fragments = list(set(fragment_refs))[:5]  # 最多 5 个

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
    acceptance: dict[str, Any],
    patch_result: dict[str, Any],
    llm_cfg: dict[str, Any],
) -> TemplatePatchSuggestion | None:
    """为动态 SQL 生成模板级 patch 建议

    Args:
        sql_unit: SQL 单元
        acceptance: 验证接受结果
        patch_result: 补丁生成结果
        llm_cfg: LLM 配置

    Returns:
        TemplatePatchSuggestion 对象，如果 LLM 不可用则返回 None
    """
    # 检查 LLM 是否启用
    if not llm_cfg.get("enabled", False):
        return None

    # 构建 prompt
    prompt = build_template_patch_prompt(sql_unit, acceptance, patch_result)

    # 调用 LLM
    from ..llm.provider import _run_opencode

    provider = llm_cfg.get("provider", "opencode_builtin")

    try:
        if provider == "opencode_run":
            candidates, _ = _run_opencode(
                sql_key="template_patch_suggestion",
                prompt=prompt,
                llm_cfg=llm_cfg,
            )
            response_text = candidates[0].get("rewrittenSql", "") if candidates else ""
        else:
            # 内置模式返回保守响应
            response_text = "建议使用模板级改写；内置模式无法执行深度分析"

        # 解析响应
        suggestion = _parse_llm_template_suggestion(response_text, prompt)
        return suggestion

    except Exception:
        # LLM 调用失败，返回 None
        return None


def save_template_suggestion(
    run_dir: Path,
    sql_key: str,
    suggestion: TemplatePatchSuggestion,
) -> None:
    """保存模板建议到文件

    Args:
        run_dir: 运行目录
        sql_key: SQL 标识符
        suggestion: 模板建议
    """
    suggestions_dir = run_dir / "ops" / "template_suggestions"
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
    """将 LLM 建议附加到补丁结果

    Args:
        patch_result: 补丁生成结果
        suggestion: LLM 模板建议

    Returns:
        更新后的补丁结果
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

    # 更新 repair hints
    if "repairHints" not in patch_result:
        patch_result["repairHints"] = []

    if suggestion.suggestion_type != "MANUAL_REVIEW":
        patch_result["repairHints"].append({
            "hintId": "llm-template-suggestion",
            "title": f"LLM suggested {suggestion.suggestion_type}",
            "detail": suggestion.reasoning[:200] if suggestion.reasoning else "LLM provided template modification guidance",
            "actionType": "LLM_ASSISTED",
            "command": None,
        })

    return patch_result


def collect_template_suggestions(run_dir: Path) -> list[dict[str, Any]]:
    """收集所有模板建议

    Args:
        run_dir: 运行目录

    Returns:
        模板建议列表
    """
    suggestions_dir = run_dir / "ops" / "template_suggestions"
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
    """生成模板建议摘要

    Args:
        suggestions: 模板建议列表

    Returns:
        摘要统计字典
    """
    total = len(suggestions)

    # 统计建议类型分布
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
        "high_confidence_suggestions": sum(1 for s in suggestions if s.get("confidence") == "high"),
    }
