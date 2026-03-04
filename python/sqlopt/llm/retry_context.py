"""LLM 重试反馈上下文

支持在 LLM 调用失败或生成无效候选时，将错误信息反馈给 LLM 请求修正。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetryContext:
    """重试上下文"""
    attempt: int  # 当前重试次数（从 1 开始）
    max_retries: int  # 最大重试次数
    errors: list[dict[str, Any]]  # 错误列表
    feedback_prompt: str  # 格式化后的反馈提示


def build_retry_context(
    attempt: int,
    max_retries: int,
    validation_errors: list[dict[str, Any]] | None = None,
    execution_error: str | None = None,
) -> RetryContext:
    """构建重试上下文

    Args:
        attempt: 当前重试次数（从 1 开始）
        max_retries: 最大重试次数
        validation_errors: 验证错误列表（来自 output_validator）
        execution_error: 执行错误信息（来自 LLM 调用失败）

    Returns:
        RetryContext 对象
    """
    errors: list[dict[str, Any]] = []
    feedback_parts: list[str] = []

    # 收集验证错误
    if validation_errors:
        for err in validation_errors:
            error_info = {
                "type": "validation",
                "candidate_id": err.get("candidate_id"),
                "check_type": err.get("check_type"),
                "reason": err.get("rejected_reason") or err.get("message"),
            }
            errors.append(error_info)
            feedback_parts.append(f"- [{err.get('check_type', 'unknown')}] {err.get('rejected_reason', '验证失败')}")

    # 收集执行错误
    if execution_error:
        error_info = {
            "type": "execution",
            "message": execution_error,
        }
        errors.append(error_info)
        feedback_parts.append(f"- [execution] {execution_error}")

    # 构建反馈提示
    feedback_prompt = _format_feedback_prompt(attempt, feedback_parts)

    return RetryContext(
        attempt=attempt,
        max_retries=max_retries,
        errors=errors,
        feedback_prompt=feedback_prompt,
    )


def _format_feedback_prompt(attempt: int, feedback_parts: list[str]) -> str:
    """格式化反馈提示

    Args:
        attempt: 当前重试次数
        feedback_parts: 错误描述列表

    Returns:
        格式化的反馈提示字符串
    """
    if not feedback_parts:
        return ""

    header = f"【第 {attempt} 次重试】上次生成的 SQL 有以下问题，请修正后重新生成：\n"
    return header + "\n".join(feedback_parts)


def build_retry_prompt(
    original_prompt: dict[str, Any],
    retry_context: RetryContext,
) -> dict[str, Any]:
    """构建带重试上下文的 prompt

    Args:
        original_prompt: 原始 prompt
        retry_context: 重试上下文

    Returns:
        包含重试信息的增强 prompt
    """
    # 复制原始 prompt
    enhanced_prompt = dict(original_prompt)

    # 添加重试信息到 requiredContext
    required_context = enhanced_prompt.get("requiredContext", {})
    required_context["retryContext"] = {
        "attempt": retry_context.attempt,
        "maxRetries": retry_context.max_retries,
        "feedback": retry_context.feedback_prompt,
    }
    enhanced_prompt["requiredContext"] = required_context

    # 如果有反馈提示，添加到 prompt 开头
    if retry_context.feedback_prompt:
        original_task = enhanced_prompt.get("task", "")
        enhanced_prompt["task"] = f"{retry_context.feedback_prompt}\n\n{original_task}"

    return enhanced_prompt


def should_retry(
    valid_candidates: list[dict[str, Any]],
    current_attempt: int,
    max_retries: int,
    force_retry_reason: str | None = None,
) -> tuple[bool, str | None]:
    """判断是否应该重试

    Args:
        valid_candidates: 当前有效候选列表
        current_attempt: 当前重试次数
        max_retries: 最大重试次数
        force_retry_reason: 强制重试原因（可选）

    Returns:
        (should_retry, reason) 元组
    """
    # 如果有强制重试原因，优先检查
    if force_retry_reason:
        if current_attempt < max_retries:
            return True, force_retry_reason
        return False, f"已达最大重试次数 ({max_retries})，但仍有：{force_retry_reason}"

    # 没有有效候选时需要重试
    if not valid_candidates:
        if current_attempt < max_retries:
            return True, "没有生成有效候选"
        return False, "已达最大重试次数，仍无有效候选"

    # 有有效候选，不需要重试
    return False, None


def collect_validation_errors(
    validation_results: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """收集验证错误用于重试反馈

    Args:
        validation_results: 验证结果列表
        candidates: 候选列表

    Returns:
        错误信息列表
    """
    errors: list[dict[str, Any]] = []

    for result in validation_results:
        if not result.get("passed", True):
            errors.append({
                "candidate_id": result.get("candidate_id"),
                "check_type": "validation",
                "rejected_reason": result.get("rejected_reason"),
                "checks": result.get("checks", []),
            })

    return errors
