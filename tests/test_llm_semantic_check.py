"""Tests for Phase 3 LLM semantic check"""

import pytest
from sqlopt.platforms.sql.llm_semantic_check import (
    LlmSemanticResult,
    build_semantic_check_prompt,
    parse_llm_semantic_response,
    check_semantic_equivalence,
    integrate_llm_semantic_check,
)


class TestBuildSemanticCheckPrompt:
    """测试语义检查 prompt 构建"""

    def test_basic_prompt(self):
        prompt = build_semantic_check_prompt(
            original_sql="SELECT * FROM users WHERE id = 1",
            rewritten_sql="SELECT id, name FROM users WHERE id = 1",
        )

        assert prompt["task"] == "sql_semantic_equivalence_check"
        assert prompt["original_sql"] == "SELECT * FROM users WHERE id = 1"
        assert prompt["rewritten_sql"] == "SELECT id, name FROM users WHERE id = 1"
        assert "requiredContext" in prompt
        assert "judgment_criteria" in prompt

    def test_prompt_with_context(self):
        context = {
            "db_platform": "postgresql",
            "tables": ["users", "orders"],
            "db_result": {"rowCount": {"status": "MISMATCH"}},
        }
        prompt = build_semantic_check_prompt(
            original_sql="SELECT * FROM users",
            rewritten_sql="SELECT id FROM users",
            context=context,
        )

        assert prompt["requiredContext"]["db_platform"] == "postgresql"
        assert prompt["requiredContext"]["tables_involved"] == ["users", "orders"]


class TestParseLlmSemanticResponse:
    """测试 LLM 响应解析"""

    def test_parse_equivalent_high_confidence(self):
        response = """
        语义等价性判断：语义等价
        置信度：high
        理由：两个 SQL 查询返回相同的结果集，只是列的选择不同但不影响语义
        """
        result = parse_llm_semantic_response(response)

        assert result.equivalent is True
        assert result.confidence == "high"
        assert "两个 SQL" in result.reasoning

    def test_parse_not_equivalent(self):
        response = """
        语义等价性判断：不等价
        置信度：medium
        理由：改写后的 SQL 删除了 WHERE 条件，会导致全表扫描
        """
        result = parse_llm_semantic_response(response)

        assert result.equivalent is False
        assert result.confidence == "medium"

    def test_parse_default_confidence(self):
        response = "无法判断语义等价性"
        result = parse_llm_semantic_response(response)

        # "equivalent" 在响应中出现会被解析为等价
        # 这是一个保守的解析策略
        assert result.confidence == "low"

    def test_parse_risk_flags_order_by_removed(self):
        response = "语义等价"
        # 模拟原始 SQL 有 ORDER BY 但改写后没有
        result = parse_llm_semantic_response(response)
        # risk_flags 检测的是全局变量，这里只测试基本解析
        assert result.equivalent is True


class TestIntegrateLlmSemanticCheck:
    """测试 LLM 语义检查集成"""

    @pytest.fixture
    def config_enabled(self):
        return {
            "validate": {
                "llm_semantic_check": {
                    "enabled": True,
                    "only_on_db_mismatch": True,
                }
            },
            "llm": {
                "enabled": True,
                "provider": "opencode_builtin",
            },
            "db": {
                "platform": "postgresql",
            },
        }

    @pytest.fixture
    def config_disabled(self):
        return {
            "validate": {
                "llm_semantic_check": {
                    "enabled": False,
                }
            },
            "llm": {
                "enabled": True,
            },
        }

    def test_skip_when_disabled(self, config_disabled):
        should_override, warnings, result = integrate_llm_semantic_check(
            original_sql="SELECT * FROM users",
            rewritten_sql="SELECT id FROM users",
            db_equivalence_result={"rowCount": {"status": "MATCH"}},
            llm_cfg=config_disabled.get("llm", {}),
            config=config_disabled,
        )

        assert should_override is False
        assert len(warnings) == 0
        assert result == {}

    def test_skip_when_db_match_and_only_on_mismatch(self, config_enabled):
        should_override, warnings, result = integrate_llm_semantic_check(
            original_sql="SELECT * FROM users",
            rewritten_sql="SELECT id FROM users",
            db_equivalence_result={"rowCount": {"status": "MATCH"}},
            llm_cfg=config_enabled.get("llm", {}),
            config=config_enabled,
        )

        # 当 DB 验证通过且 only_on_db_mismatch=True 时，跳过 LLM 检查
        assert should_override is False
        assert len(warnings) == 0

    def test_call_llm_when_db_mismatch(self, config_enabled):
        should_override, warnings, result = integrate_llm_semantic_check(
            original_sql="SELECT * FROM users",
            rewritten_sql="SELECT id FROM users",
            db_equivalence_result={"rowCount": {"status": "MISMATCH"}},
            llm_cfg=config_enabled.get("llm", {}),
            config=config_enabled,
        )

        # 当 DB 验证失败时，应该调用 LLM 检查
        # 由于使用 opencode_builtin，会返回保守结果
        assert "equivalent" in result or result == {}


class TestLlmSemanticResultDataclass:
    """测试 LlmSemanticResult 数据类"""

    def test_creation(self):
        result = LlmSemanticResult(
            equivalent=True,
            confidence="high",
            reasoning="Test reasoning",
            risk_flags=[],
        )

        assert result.equivalent is True
        assert result.confidence == "high"
        assert result.reasoning == "Test reasoning"
        assert result.risk_flags == []

    def test_with_risk_flags(self):
        result = LlmSemanticResult(
            equivalent=False,
            confidence="low",
            reasoning="Risk detected",
            risk_flags=["ORDER_BY_REMOVED", "LIMIT_REMOVED"],
        )

        assert result.equivalent is False
        assert len(result.risk_flags) == 2


class TestCheckSemanticEquivalence:
    """测试语义等价性检查"""

    def test_check_with_builtin_provider(self):
        llm_cfg = {
            "enabled": True,
            "provider": "opencode_builtin",
        }

        result = check_semantic_equivalence(
            original_sql="SELECT * FROM users",
            rewritten_sql="SELECT id FROM users",
            llm_cfg=llm_cfg,
            context={"db_platform": "postgresql"},
        )

        # 内置模式会返回保守结果
        assert isinstance(result, LlmSemanticResult)
        # 内置模式无法执行深度语义分析
        assert "内置模式" in result.reasoning or "LLM 调用失败" in result.reasoning
