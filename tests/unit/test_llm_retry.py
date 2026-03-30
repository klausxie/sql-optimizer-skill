"""Tests for LLM retry mechanism"""

import pytest
from sqlopt.llm.retry_context import (
    RetryContext,
    build_retry_context,
    build_retry_prompt,
    should_retry,
    collect_validation_errors,
)


class TestBuildRetryContext:
    """测试重试上下文构建"""

    def test_build_with_validation_errors(self):
        validation_errors = [
            {
                "candidate_id": "test#c1",
                "check_type": "syntax",
                "rejected_reason": "Syntax error: unmatched parentheses",
            }
        ]
        ctx = build_retry_context(
            attempt=1,
            max_retries=2,
            validation_errors=validation_errors,
        )

        assert ctx.attempt == 1
        assert ctx.max_retries == 2
        assert len(ctx.errors) == 1
        assert ctx.errors[0]["type"] == "validation"
        assert "syntax" in ctx.feedback_prompt.lower()

    def test_build_with_execution_error(self):
        ctx = build_retry_context(
            attempt=2,
            max_retries=3,
            execution_error="Connection timeout",
        )

        assert ctx.attempt == 2
        assert ctx.max_retries == 3
        assert len(ctx.errors) == 1
        assert ctx.errors[0]["type"] == "execution"
        assert "Connection timeout" in ctx.feedback_prompt

    def test_build_with_both_errors(self):
        validation_errors = [
            {
                "candidate_id": "test#c1",
                "check_type": "heuristic",
                "rejected_reason": "WHERE clause removed",
            }
        ]
        ctx = build_retry_context(
            attempt=1,
            max_retries=2,
            validation_errors=validation_errors,
            execution_error="API error",
        )

        assert len(ctx.errors) == 2
        assert any(e["type"] == "validation" for e in ctx.errors)
        assert any(e["type"] == "execution" for e in ctx.errors)

    def test_build_with_no_errors(self):
        ctx = build_retry_context(
            attempt=1,
            max_retries=2,
        )

        assert ctx.attempt == 1
        assert len(ctx.errors) == 0
        assert ctx.feedback_prompt == ""


class TestBuildRetryPrompt:
    """测试重试 prompt 构建"""

    def test_build_retry_prompt(self):
        original_prompt = {
            "task": "sql_optimize_candidate_generation",
            "requiredContext": {
                "sql": "SELECT * FROM users",
            }
        }
        ctx = build_retry_context(
            attempt=1,
            max_retries=2,
            validation_errors=[
                {
                    "candidate_id": "test#c1",
                    "check_type": "syntax",
                    "rejected_reason": "Syntax error",
                }
            ],
        )

        enhanced = build_retry_prompt(original_prompt, ctx)

        # 检查 task 包含反馈信息
        assert "第 1 次重试" in enhanced["task"]
        assert "Syntax error" in enhanced["task"]

        # 检查 requiredContext 包含 retryContext
        assert "retryContext" in enhanced["requiredContext"]
        retry_ctx = enhanced["requiredContext"]["retryContext"]
        assert retry_ctx["attempt"] == 1
        assert retry_ctx["maxRetries"] == 2


class TestShouldRetry:
    """测试重试决策逻辑"""

    def test_should_retry_no_valid_candidates(self):
        do_retry, reason = should_retry(
            valid_candidates=[],
            current_attempt=1,
            max_retries=2,
        )
        assert do_retry is True
        assert "没有生成有效候选" in reason

    def test_should_not_retry_no_valid_candidates_max_reached(self):
        do_retry, reason = should_retry(
            valid_candidates=[],
            current_attempt=3,
            max_retries=2,
        )
        assert do_retry is False
        assert "已达最大重试次数" in reason

    def test_should_not_retry_has_valid_candidates(self):
        do_retry, reason = should_retry(
            valid_candidates=[{"id": "test#c1", "rewrittenSql": "SELECT 1"}],
            current_attempt=1,
            max_retries=2,
        )
        assert do_retry is False
        assert reason is None

    def test_should_retry_force_reason(self):
        do_retry, reason = should_retry(
            valid_candidates=[],
            current_attempt=1,
            max_retries=2,
            force_retry_reason="执行错误：timeout",
        )
        assert do_retry is True
        assert "执行错误" in reason

    def test_should_not_retry_force_reason_max_reached(self):
        do_retry, reason = should_retry(
            valid_candidates=[],
            current_attempt=3,
            max_retries=2,
            force_retry_reason="执行错误：timeout",
        )
        assert do_retry is False
        assert "已达最大重试次数" in reason


class TestCollectValidationErrors:
    """测试验证错误收集"""

    def test_collect_errors(self):
        validation_results = [
            {
                "candidate_id": "test#c1",
                "passed": False,
                "rejected_reason": "Syntax error",
                "check_type": "syntax",
                "checks": [{"type": "syntax", "passed": False}],
            },
            {
                "candidate_id": "test#c2",
                "passed": True,
            }
        ]
        candidates = [
            {"id": "test#c1"},
            {"id": "test#c2"},
        ]

        errors = collect_validation_errors(validation_results, candidates)

        assert len(errors) == 1
        assert errors[0]["candidate_id"] == "test#c1"
        assert errors[0]["rejected_reason"] == "Syntax error"

    def test_collect_no_errors(self):
        validation_results = [
            {"candidate_id": "test#c1", "passed": True},
            {"candidate_id": "test#c2", "passed": True},
        ]
        candidates = [
            {"id": "test#c1"},
            {"id": "test#c2"},
        ]

        errors = collect_validation_errors(validation_results, candidates)

        assert len(errors) == 0


class TestRetryContextDataclass:
    """测试 RetryContext 数据类"""

    def test_retry_context_creation(self):
        ctx = RetryContext(
            attempt=1,
            max_retries=2,
            errors=[{"type": "validation", "message": "test"}],
            feedback_prompt="Test prompt",
        )

        assert ctx.attempt == 1
        assert ctx.max_retries == 2
        assert len(ctx.errors) == 1
        assert ctx.feedback_prompt == "Test prompt"

    def test_retry_context_default_values(self):
        ctx = RetryContext(
            attempt=1,
            max_retries=2,
            errors=[],
            feedback_prompt="",
        )

        assert ctx.attempt == 1
        assert ctx.max_retries == 2
        assert len(ctx.errors) == 0
        assert ctx.feedback_prompt == ""
