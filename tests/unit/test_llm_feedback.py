"""Tests for Phase 4 LLM feedback mechanism"""

import pytest
from sqlopt.stages.llm_feedback import (
    LlmFeedbackRecord,
    LlmIssuePattern,
    extract_llm_detected_issues,
    collect_llm_feedback,
    analyze_feedback_patterns,
    generate_feedback_summary,
)


class TestExtractLlmDetectedIssues:
    """测试 LLM 问题提取"""

    def test_extract_from_detected_issues_field(self):
        proposal = {
            "llmCandidates": [
                {
                    "id": "test#c1",
                    "rewrittenSql": "SELECT id FROM users",
                    "detectedIssues": [
                        {"type": "performance", "description": "Missing index on users.status"}
                    ]
                }
            ]
        }

        issues = extract_llm_detected_issues(proposal)

        assert len(issues) == 1
        assert issues[0]["type"] == "performance"
        assert "Missing index" in issues[0]["description"]

    def test_extract_from_rewrite_reasoning(self):
        proposal = {
            "llmCandidates": [
                {
                    "id": "test#c1",
                    "rewrittenSql": "SELECT id FROM users WHERE status = 1",
                    "rewriteReasoning": "Added index hint to improve performance by using idx_status"
                }
            ]
        }

        issues = extract_llm_detected_issues(proposal)

        assert len(issues) == 1
        assert issues[0]["type"] == "performance"

    def test_extract_security_issue(self):
        proposal = {
            "llmCandidates": [
                {
                    "id": "test#c1",
                    "rewrittenSql": "SELECT * FROM users",
                    "rewriteReasoning": "This query has potential SQL injection vulnerability"
                }
            ]
        }

        issues = extract_llm_detected_issues(proposal)

        assert len(issues) == 1
        assert issues[0]["type"] == "security"

    def test_no_candidates(self):
        proposal = {"llmCandidates": []}
        issues = extract_llm_detected_issues(proposal)
        assert issues == []

    def test_no_issues_field(self):
        proposal = {
            "llmCandidates": [
                {"id": "test#c1", "rewrittenSql": "SELECT 1"}
            ]
        }
        issues = extract_llm_detected_issues(proposal)
        assert issues == []


class TestLlmFeedbackRecord:
    """测试 LLM 反馈记录数据类"""

    def test_creation(self):
        record = LlmFeedbackRecord(
            sql_key="test.mapper.selectUser",
            run_id="run-123",
            llm_detected_issues=[{"type": "performance", "description": "Missing index"}],
            triggered_rules=["SELECT_STAR"],
            acceptance_status="PASS",
        )

        assert record.sql_key == "test.mapper.selectUser"
        assert record.run_id == "run-123"
        assert len(record.llm_detected_issues) == 1
        assert record.triggered_rules == ["SELECT_STAR"]
        assert record.acceptance_status == "PASS"

    def test_to_dict(self):
        record = LlmFeedbackRecord(
            sql_key="test#c1",
            run_id="run-123",
            llm_detected_issues=[],
            triggered_rules=[],
            acceptance_status="PASS",
        )

        result = record.to_dict()

        assert result["sql_key"] == "test#c1"
        assert result["run_id"] == "run-123"
        assert "created_at" in result


class TestCollectLlmFeedback:
    """测试反馈收集"""

    def test_collect_basic_feedback(self):
        proposal = {
            "llmCandidates": [{"id": "c1", "rewrittenSql": "SELECT 1"}],
            "triggeredRules": [{"ruleId": "SELECT_STAR"}],
        }
        acceptance = {"status": "PASS"}

        record = collect_llm_feedback(
            sql_key="test#c1",
            proposal=proposal,
            acceptance=acceptance,
            run_id="run-123",
        )

        assert record.sql_key == "test#c1"
        assert record.run_id == "run-123"
        assert record.triggered_rules == ["SELECT_STAR"]
        assert record.acceptance_status == "PASS"
        assert record.llm_candidates_count == 1

    def test_collect_with_validation_errors(self):
        proposal = {
            "llmCandidates": [{"id": "c1", "rewrittenSql": "SELECT 1"}],
            "triggeredRules": [],
        }
        validation_errors = [
            {"check_type": "syntax", "rejected_reason": "Unmatched parenthesis"}
        ]

        record = collect_llm_feedback(
            sql_key="test#c1",
            proposal=proposal,
            acceptance=None,
            run_id="run-123",
            validation_errors=validation_errors,
        )

        assert len(record.validation_errors) == 1
        assert record.validation_errors[0]["check_type"] == "syntax"

    def test_collect_empty_candidates(self):
        proposal = {
            "llmCandidates": [],
            "triggeredRules": [],
        }

        record = collect_llm_feedback(
            sql_key="test#c1",
            proposal=proposal,
            acceptance=None,
            run_id="run-123",
        )

        assert record.llm_candidates_count == 0
        assert record.valid_candidates_count == 0


class TestAnalyzeFeedbackPatterns:
    """测试反馈模式分析"""

    def test_analyze_simple_patterns(self):
        records = [
            LlmFeedbackRecord(
                sql_key="test#c1",
                run_id="run-123",
                llm_detected_issues=[{"type": "performance", "description": "Missing index"}],
                triggered_rules=[],
                acceptance_status="PASS",
            ),
            LlmFeedbackRecord(
                sql_key="test#c2",
                run_id="run-123",
                llm_detected_issues=[{"type": "performance", "description": "Missing index"}],
                triggered_rules=[],
                acceptance_status="PASS",
            ),
        ]

        patterns = analyze_feedback_patterns(records)

        assert len(patterns) == 1
        assert patterns[0].pattern_type == "performance"
        assert patterns[0].frequency == 2
        assert len(patterns[0].sample_sql_keys) == 2

    def test_analyze_multiple_issue_types(self):
        records = [
            LlmFeedbackRecord(
                sql_key="test#c1",
                run_id="run-123",
                llm_detected_issues=[
                    {"type": "performance", "description": "Missing index"},
                    {"type": "security", "description": "SQL injection risk"},
                ],
                triggered_rules=[],
                acceptance_status="PASS",
            ),
        ]

        patterns = analyze_feedback_patterns(records)

        assert len(patterns) == 2
        pattern_types = [p.pattern_type for p in patterns]
        assert "performance" in pattern_types
        assert "security" in pattern_types

    def test_analyze_sorts_by_frequency(self):
        records = [
            LlmFeedbackRecord(
                sql_key="test#c1",
                run_id="run-123",
                llm_detected_issues=[{"type": "performance", "description": "Issue A"}],
                triggered_rules=[],
                acceptance_status="PASS",
            ),
            LlmFeedbackRecord(
                sql_key="test#c2",
                run_id="run-123",
                llm_detected_issues=[
                    {"type": "performance", "description": "Issue A"},
                    {"type": "security", "description": "Issue B"},
                ],
                triggered_rules=[],
                acceptance_status="PASS",
            ),
        ]

        patterns = analyze_feedback_patterns(records)

        # performance 出现 2 次，security 出现 1 次
        assert patterns[0].pattern_type == "performance"
        assert patterns[0].frequency == 2


class TestGenerateFeedbackSummary:
    """测试反馈摘要生成"""

    def test_generate_summary_basic(self):
        records = [
            LlmFeedbackRecord(
                sql_key="test#c1",
                run_id="run-123",
                llm_detected_issues=[{"type": "performance", "description": "Issue"}],
                triggered_rules=["SELECT_STAR"],
                acceptance_status="PASS",
            ),
            LlmFeedbackRecord(
                sql_key="test#c2",
                run_id="run-123",
                llm_detected_issues=[],
                triggered_rules=[],
                acceptance_status="SKIP",
            ),
        ]

        summary = generate_feedback_summary(records)

        assert summary["total_records"] == 2
        assert summary["records_with_llm_issues"] == 1
        assert summary["records_with_triggered_rules"] == 1
        assert "performance" in summary["issue_type_distribution"]
        assert "SELECT_STAR" in summary["rule_trigger_distribution"]

    def test_generate_summary_empty(self):
        records = []
        summary = generate_feedback_summary(records)

        assert summary["total_records"] == 0
        assert summary["records_with_llm_issues"] == 0
        assert summary["llm_issue_rate"] == 0.0

    def test_generate_summary_distribution(self):
        records = [
            LlmFeedbackRecord(
                sql_key="test#c1",
                run_id="run-123",
                llm_detected_issues=[{"type": "performance", "description": "Issue"}],
                triggered_rules=["SELECT_STAR"],
                acceptance_status="PASS",
            ),
            LlmFeedbackRecord(
                sql_key="test#c2",
                run_id="run-123",
                llm_detected_issues=[{"type": "security", "description": "Risk"}],
                triggered_rules=["DOLLAR_SUBSTITUTION"],
                acceptance_status="PASS",
            ),
        ]

        summary = generate_feedback_summary(records)

        assert summary["issue_type_distribution"]["performance"] == 1
        assert summary["issue_type_distribution"]["security"] == 1
        assert summary["rule_trigger_distribution"]["SELECT_STAR"] == 1
        assert summary["rule_trigger_distribution"]["DOLLAR_SUBSTITUTION"] == 1


class TestLlmIssuePatternDataclass:
    """测试 LlmIssuePattern 数据类"""

    def test_creation(self):
        pattern = LlmIssuePattern(
            pattern_type="performance",
            description="Missing index on frequently queried column",
            frequency=5,
            sample_sql_keys=["test#c1", "test#c2"],
        )

        assert pattern.pattern_type == "performance"
        assert pattern.frequency == 5
        assert len(pattern.sample_sql_keys) == 2

    def test_to_dict(self):
        pattern = LlmIssuePattern(
            pattern_type="security",
            description="SQL injection risk",
        )

        result = pattern.to_dict()

        assert result["pattern_type"] == "security"
        assert result["description"] == "SQL injection risk"
        assert result["frequency"] == 1
        assert result["sample_sql_keys"] == []
