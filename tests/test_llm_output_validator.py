"""Tests for LLM output validator"""

import pytest
from sqlopt.llm.output_validator import (
    _check_sql_syntax_basic,
    _check_heuristics,
    validate_candidate,
    validate_candidates,
    LlmOutputValidationResult,
    ValidationCheck,
)


class TestCheckSqlSyntaxBasic:
    """测试基础 SQL 语法检查"""

    def test_valid_select(self):
        ok, error = _check_sql_syntax_basic("SELECT * FROM users WHERE id = 1")
        assert ok is True
        assert error is None

    def test_valid_select_with_join(self):
        ok, error = _check_sql_syntax_basic(
            "SELECT u.*, o.id FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert ok is True
        assert error is None

    def test_valid_with_cte(self):
        ok, error = _check_sql_syntax_basic(
            "WITH cte AS (SELECT 1) SELECT * FROM cte"
        )
        assert ok is True
        assert error is None

    def test_empty_sql(self):
        ok, error = _check_sql_syntax_basic("")
        assert ok is False
        assert "empty" in error.lower()

    def test_only_comments(self):
        ok, error = _check_sql_syntax_basic("-- this is a comment")
        assert ok is False
        assert "only comments" in error.lower()

    def test_invalid_start(self):
        ok, error = _check_sql_syntax_basic("INVALID SQL STATEMENT")
        assert ok is False
        assert "valid keyword" in error.lower()

    def test_unmatched_paren_opening(self):
        ok, error = _check_sql_syntax_basic("SELECT * FROM (SELECT 1")
        assert ok is False
        assert "parenthes" in error.lower()

    def test_unmatched_paren_closing(self):
        ok, error = _check_sql_syntax_basic("SELECT * FROM SELECT 1))")
        assert ok is False
        assert "parenthes" in error.lower()

    def test_where_without_condition(self):
        ok, error = _check_sql_syntax_basic("SELECT * FROM users WHERE")
        assert ok is False
        assert "where" in error.lower()

    def test_in_empty_list(self):
        ok, error = _check_sql_syntax_basic("SELECT * FROM users WHERE id IN ()")
        assert ok is False
        assert "in with empty" in error.lower()


class TestCheckHeuristics:
    """测试启发式规则检查"""

    def test_no_warnings_for_same_sql(self):
        sql = "SELECT * FROM users WHERE id = 1"
        ok, warnings = _check_heuristics(sql, sql)
        assert ok is True
        assert len(warnings) == 0

    def test_column_increase_warning(self):
        original = "SELECT id FROM users"
        rewritten = "SELECT id, name, email, phone, address, city, country FROM users"
        ok, warnings = _check_heuristics(rewritten, original)
        assert ok is False
        assert any("column count increased" in w.lower() for w in warnings)

    def test_where_removed_warning(self):
        original = "SELECT * FROM users WHERE id = 1"
        rewritten = "SELECT * FROM users"
        ok, warnings = _check_heuristics(rewritten, original)
        assert ok is False
        assert any("where clause was removed" in w.lower() for w in warnings)

    def test_join_increase_warning(self):
        original = "SELECT * FROM users"
        rewritten = "SELECT * FROM users u JOIN orders o ON u.id = o.user_id JOIN products p ON o.product_id = p.id JOIN categories c ON p.category_id = c.id"
        ok, warnings = _check_heuristics(rewritten, original)
        assert ok is False
        assert any("join count increased" in w.lower() for w in warnings)

    def test_placeholder_removed_warning(self):
        original = "SELECT * FROM users WHERE id = #{id}"
        rewritten = "SELECT * FROM users WHERE id = 1"
        ok, warnings = _check_heuristics(rewritten, original)
        assert ok is False
        assert any("placeholder" in w.lower() for w in warnings)

    def test_tautology_detected(self):
        sql = "SELECT * FROM users WHERE 1 = 1"
        ok, warnings = _check_heuristics(sql, sql)
        assert ok is False
        assert any("tautology" in w.lower() for w in warnings)


class TestValidateCandidate:
    """测试完整的候选验证"""

    @pytest.fixture
    def config_enabled(self):
        return {
            "llm": {
                "output_validation": {
                    "enabled": True,
                    "syntax_check": True,
                    "heuristic_check": True,
                    "schema_check": False,
                }
            }
        }

    @pytest.fixture
    def config_disabled(self):
        return {
            "llm": {
                "output_validation": {
                    "enabled": False,
                }
            }
        }

    def test_valid_candidate(self, config_enabled):
        candidate = {
            "id": "test#c1",
            "rewrittenSql": "SELECT id FROM users WHERE id = 1",
            "source": "llm",
        }
        result = validate_candidate(
            candidate=candidate,
            original_sql="SELECT * FROM users WHERE id = 1",
            sql_key="test",
            config=config_enabled,
        )
        assert result.passed is True
        assert len(result.checks) > 0

    def test_syntax_error_rejected(self, config_enabled):
        candidate = {
            "id": "test#c1",
            "rewrittenSql": "SELECT * FROM users WHERE",
            "source": "llm",
        }
        result = validate_candidate(
            candidate=candidate,
            original_sql="SELECT * FROM users WHERE id = 1",
            sql_key="test",
            config=config_enabled,
        )
        assert result.passed is False
        assert result.rejected_reason is not None
        assert "syntax" in result.rejected_reason.lower()

    def test_validation_disabled(self, config_disabled):
        candidate = {
            "id": "test#c1",
            "rewrittenSql": "INVALID SQL",
            "source": "llm",
        }
        result = validate_candidate(
            candidate=candidate,
            original_sql="SELECT * FROM users",
            sql_key="test",
            config=config_disabled,
        )
        assert result.passed is True
        assert len(result.checks) == 0


class TestValidateCandidates:
    """测试批量验证"""

    @pytest.fixture
    def config_enabled(self):
        return {
            "llm": {
                "output_validation": {
                    "enabled": True,
                    "syntax_check": True,
                    "heuristic_check": True,
                    "schema_check": False,
                }
            }
        }

    def test_filter_invalid_candidates(self, config_enabled):
        candidates = [
            {
                "id": "test#c1",
                "rewrittenSql": "SELECT id FROM users WHERE id = 1",
                "source": "llm",
            },
            {
                "id": "test#c2",
                "rewrittenSql": "SELECT * FROM users WHERE",  # 语法错误
                "source": "llm",
            },
            {
                "id": "test#c3",
                "rewrittenSql": "SELECT name FROM users WHERE id = 1",
                "source": "llm",
            },
        ]
        valid, results = validate_candidates(
            candidates=candidates,
            original_sql="SELECT * FROM users WHERE id = 1",
            sql_key="test",
            config=config_enabled,
        )
        # 应该过滤掉语法错误的候选
        assert len(valid) == 2
        assert len(results) == 3
        assert results[0].passed is True
        assert results[1].passed is False
        assert results[2].passed is True

    def test_empty_candidates(self, config_enabled):
        valid, results = validate_candidates(
            candidates=[],
            original_sql="SELECT * FROM users",
            sql_key="test",
            config=config_enabled,
        )
        assert len(valid) == 0
        assert len(results) == 0
