"""Tests for Phase 5 patch_generate LLM assistance"""

import pytest
from sqlopt.stages.patch.llm_assist import (
    TemplatePatchSuggestion,
    build_template_patch_prompt,
    generate_template_patch_suggestion,
    attach_llm_suggestion_to_patch,
    _parse_llm_template_suggestion,
    collect_template_suggestions,
    generate_template_suggestion_summary,
)


class TestBuildTemplatePatchPrompt:
    """测试模板补丁 prompt 构建"""

    def test_basic_prompt(self):
        sql_unit = {
            "sqlKey": "test.mapper.selectUser",
            "templateSql": "SELECT * FROM users WHERE id = #{id}",
            "dynamicFeatures": ["IF", "WHERE"],
            "dynamicTrace": {"includeFragments": []},
        }
        acceptance = {
            "rewrittenSql": "SELECT id, name FROM users WHERE id = ?",
        }
        patch_result = {
            "selectionReason": {
                "code": "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE",
                "message": "dynamic mapper statement cannot be replaced by flattened SQL",
            }
        }

        prompt = build_template_patch_prompt(sql_unit, acceptance, patch_result)

        assert prompt["task"] == "mybatis_template_patch_suggestion"
        assert prompt["original_template"] == "SELECT * FROM users WHERE id = #{id}"
        assert prompt["rewritten_sql"] == "SELECT id, name FROM users WHERE id = ?"
        assert prompt["dynamic_features"] == ["IF", "WHERE"]
        assert (
            prompt["patch_skip_reason"]["code"]
            == "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE"
        )

    def test_prompt_with_include_fragments(self):
        sql_unit = {
            "sqlKey": "test.mapper.withInclude",
            "templateSql": "<include refid='common.where'/>",
            "dynamicFeatures": ["INCLUDE"],
            "dynamicTrace": {
                "includeFragments": [
                    {
                        "fragmentId": "common.where",
                        "fragmentSql": "WHERE status = 1",
                        "dynamicFeatures": [],
                    }
                ]
            },
        }
        acceptance = {"rewrittenSql": "SELECT * FROM table WHERE status = 1"}
        patch_result = {"selectionReason": {}}

        prompt = build_template_patch_prompt(sql_unit, acceptance, patch_result)

        assert len(prompt["include_fragments"]) == 1
        assert prompt["include_fragments"][0]["fragmentId"] == "common.where"


class TestParseLlmTemplateSuggestion:
    """测试 LLM 模板建议解析"""

    def test_parse_template_modify_suggestion(self):
        response = """
        建议类型：TEMPLATE_MODIFY
        置信度：high
        推理：可以通过修改 template 结构来适配改写的 SQL

        ```diff
        - SELECT * FROM users
        + SELECT id, name FROM users
        ```

        建议：修改模板中的 SELECT 列列表
        """
        prompt = {"original_template": "SELECT * FROM users"}

        suggestion = _parse_llm_template_suggestion(response, prompt)

        assert suggestion.suggestion_type == "TEMPLATE_MODIFY"
        assert suggestion.confidence == "high"
        assert suggestion.template_diff is not None
        assert "SELECT" in suggestion.template_diff

    def test_parse_fragment_expand_suggestion(self):
        response = """
        建议类型：FRAGMENT_EXPAND
        置信度：medium
        推理：需要展开 include 片段

        建议：将 include 引用展开为内联 SQL
        ref.common_where
        """
        prompt = {}

        suggestion = _parse_llm_template_suggestion(response, prompt)

        assert suggestion.suggestion_type == "FRAGMENT_EXPAND"
        assert suggestion.confidence == "medium"
        assert "common_where" in suggestion.referenced_fragments

    def test_parse_manual_review_default(self):
        response = "这个 SQL 太复杂，建议人工审查"
        prompt = {}

        suggestion = _parse_llm_template_suggestion(response, prompt)

        # 默认类型
        assert suggestion.suggestion_type in [
            "TEMPLATE_MODIFY",
            "FRAGMENT_EXPAND",
            "MANUAL_REVIEW",
        ]
        assert "复杂" in suggestion.reasoning or "人工" in suggestion.reasoning

    def test_parse_no_diff(self):
        response = """
        建议类型：MANUAL_REVIEW
        置信度：low
        推理：无法确定最佳改写方式
        """
        prompt = {}

        suggestion = _parse_llm_template_suggestion(response, prompt)

        assert suggestion.template_diff is None
        assert suggestion.confidence == "low"


class TestTemplatePatchSuggestionDataclass:
    """测试 TemplatePatchSuggestion 数据类"""

    def test_creation(self):
        suggestion = TemplatePatchSuggestion(
            suggestion_type="TEMPLATE_MODIFY",
            template_diff="- old\n+ new",
            manual_guidance="Modify the SELECT clause",
            confidence="high",
            reasoning="LLM analysis",
        )

        assert suggestion.suggestion_type == "TEMPLATE_MODIFY"
        assert suggestion.template_diff == "- old\n+ new"
        assert suggestion.manual_guidance == "Modify the SELECT clause"
        assert suggestion.confidence == "high"

    def test_to_dict(self):
        suggestion = TemplatePatchSuggestion(
            suggestion_type="FRAGMENT_EXPAND",
            template_diff=None,
            manual_guidance=None,
        )

        result = suggestion.to_dict()

        assert result["suggestion_type"] == "FRAGMENT_EXPAND"
        assert result["template_diff"] is None
        assert result["manual_guidance"] is None
        assert result["confidence"] == "medium"  # 默认值


class TestAttachLlmSuggestionToPatch:
    """测试 LLM 建议附加到补丁结果"""

    def test_attach_suggestion(self):
        patch_result = {
            "sqlKey": "test#c1",
            "applicable": False,
            "selectionReason": {
                "code": "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE"
            },
        }
        suggestion = TemplatePatchSuggestion(
            suggestion_type="TEMPLATE_MODIFY",
            template_diff="- old\n+ new",
            manual_guidance="Modify template",
            confidence="high",
            reasoning="LLM analysis",
        )

        result = attach_llm_suggestion_to_patch(patch_result, suggestion)

        assert "llmTemplateSuggestion" in result
        assert result["llmTemplateSuggestion"]["suggestionType"] == "TEMPLATE_MODIFY"
        assert result["llmTemplateSuggestion"]["confidence"] == "high"
        assert result["llmTemplateSuggestion"]["manualGuidance"] == "Modify template"

    def test_attach_with_template_diff(self):
        patch_result = {"applicable": False}
        suggestion = TemplatePatchSuggestion(
            suggestion_type="TEMPLATE_MODIFY",
            template_diff="diff content",
            manual_guidance="guidance",
        )

        result = attach_llm_suggestion_to_patch(patch_result, suggestion)

        assert result["llmTemplateSuggestion"]["templateDiff"] == "diff content"

    def test_attach_adds_repair_hint(self):
        patch_result = {"applicable": False}
        suggestion = TemplatePatchSuggestion(
            suggestion_type="TEMPLATE_MODIFY",
            template_diff=None,
            manual_guidance="guidance",
            reasoning="analysis",
        )

        result = attach_llm_suggestion_to_patch(patch_result, suggestion)

        assert "repairHints" in result
        assert len(result["repairHints"]) > 0
        assert result["repairHints"][0]["hintId"] == "llm-template-suggestion"

    def test_no_suggestion(self):
        patch_result = {"applicable": False}
        result = attach_llm_suggestion_to_patch(patch_result, None)
        assert result == patch_result


class TestGenerateTemplateSuggestionSummary:
    """测试模板建议摘要生成"""

    def test_summary_basic(self):
        suggestions = [
            {
                "suggestionType": "TEMPLATE_MODIFY",
                "confidence": "high",
            },
            {
                "suggestionType": "FRAGMENT_EXPAND",
                "confidence": "medium",
            },
            {
                "suggestionType": "TEMPLATE_MODIFY",
                "confidence": "high",
            },
        ]

        summary = generate_template_suggestion_summary(suggestions)

        assert summary["total_suggestions"] == 3
        assert summary["suggestion_type_distribution"]["TEMPLATE_MODIFY"] == 2
        assert summary["suggestion_type_distribution"]["FRAGMENT_EXPAND"] == 1
        assert summary["confidence_distribution"]["high"] == 2
        assert summary["high_confidence_suggestions"] == 2

    def test_summary_empty(self):
        suggestions = []
        summary = generate_template_suggestion_summary(suggestions)

        assert summary["total_suggestions"] == 0
        assert summary["suggestion_type_distribution"] == {}
        assert summary["confidence_distribution"] == {}


class TestCollectTemplateSuggestions:
    """测试模板建议收集"""

    def test_collect_no_directory(self, tmp_path):
        suggestions = collect_template_suggestions(tmp_path)
        assert suggestions == []

    def test_collect_empty_directory(self, tmp_path):
        suggestions_dir = tmp_path / "ops" / "template_suggestions"
        suggestions_dir.mkdir(parents=True)

        suggestions = collect_template_suggestions(tmp_path)
        assert suggestions == []


class TestGenerateTemplatePatchSuggestion:
    """测试模板补丁建议生成（集成测试）"""

    def test_llm_disabled(self):
        sql_unit = {"sqlKey": "test#c1", "templateSql": "SELECT 1"}
        acceptance = {"rewrittenSql": "SELECT 2"}
        patch_result = {"applicable": False}
        llm_cfg = {"enabled": False}

        result = generate_template_patch_suggestion(
            sql_unit, acceptance, patch_result, llm_cfg
        )
        assert result is None

    def test_builtin_provider(self):
        sql_unit = {
            "sqlKey": "test#c1",
            "templateSql": "SELECT * FROM users",
            "dynamicFeatures": ["IF"],
            "dynamicTrace": {"includeFragments": []},
        }
        acceptance = {"rewrittenSql": "SELECT id FROM users"}
        patch_result = {
            "selectionReason": {
                "code": "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE",
                "message": "test",
            }
        }
        llm_cfg = {
            "enabled": True,
            "provider": "opencode_builtin",
        }

        # 内置模式会返回保守结果
        result = generate_template_patch_suggestion(
            sql_unit, acceptance, patch_result, llm_cfg
        )

        # 内置模式可能返回 None 或保守建议
        assert result is None or isinstance(result, TemplatePatchSuggestion)
