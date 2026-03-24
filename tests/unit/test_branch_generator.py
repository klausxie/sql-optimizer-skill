from __future__ import annotations

import pytest

from sqlopt.stages.branching.branch_generator import BranchGenerator
from sqlopt.stages.branching.branch_validator import BranchValidator
from sqlopt.stages.branching.dimension_extractor import DimensionExtractor
from sqlopt.stages.branching.risk_scorer import SQLDeltaRiskScorer
from sqlopt.stages.branching.xml_language_driver import XMLLanguageDriver


class TestBranchGeneratorLadder:
    def test_ladder_does_not_require_full_combination_enumeration(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sql = """SELECT * FROM users <where>
        <if test="a != null">AND a = #{a}</if>
        <if test="b != null">AND b = #{b}</if>
        <if test="c != null">AND c = #{c}</if>
        </where>"""
        sql_node = XMLLanguageDriver.create_sql_source(sql)
        generator = BranchGenerator(strategy="ladder", max_branches=10)

        def fail_enumeration(*_args, **_kwargs):
            raise AssertionError("ladder should not call full combination enumeration")

        monkeypatch.setattr(generator, "_enumerate_valid_condition_combinations", fail_enumeration)

        branches = generator.generate(sql_node)

        assert len(branches) >= 1

    def test_ladder_scores_sql_fragment_risk_not_only_ognl(self) -> None:
        sql = """SELECT * FROM users <where>
        <if test="name != null">AND name LIKE CONCAT('%', #{name}, '%')</if>
        <if test="status != null">AND status = #{status}</if>
        </where>"""
        sql_node = XMLLanguageDriver.create_sql_source(sql)
        dimensions = DimensionExtractor().extract(sql_node)
        scorer = SQLDeltaRiskScorer()

        scores = {dimension.condition: scorer.score_dimension(dimension) for dimension in dimensions}

        assert scores["name != null"] > scores["status != null"]

    def test_nested_child_condition_keeps_parent_dependency(self) -> None:
        sql = """SELECT * FROM users <where>
        <if test="status != null">
            AND status = #{status}
            <if test="type != null">AND type = #{type}</if>
        </if>
        </where>"""
        sql_node = XMLLanguageDriver.create_sql_source(sql)
        generator = BranchGenerator(strategy="ladder", max_branches=10)

        branches = generator.generate(sql_node)
        active_sets = [set(branch["active_conditions"]) for branch in branches]

        assert {"status != null", "type != null"} in active_sets
        assert {"type != null"} not in active_sets

    def test_foreach_generates_singleton_and_large_buckets(self) -> None:
        sql = """SELECT * FROM users WHERE id IN <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>"""
        sql_node = XMLLanguageDriver.create_sql_source(sql)
        generator = BranchGenerator(strategy="ladder", max_branches=10)

        branches = generator.generate(sql_node)
        active_conditions = [branch["active_conditions"] for branch in branches]

        assert any("foreach_0_singleton" in conditions for conditions in active_conditions)
        assert any("foreach_0_large" in conditions for conditions in active_conditions)

    def test_branch_scores_and_reasons_are_attached(self) -> None:
        sql = """SELECT * FROM users <where>
        <if test="name != null">AND name LIKE CONCAT('%', #{name}, '%')</if>
        </where>"""
        sql_node = XMLLanguageDriver.create_sql_source(sql)
        generator = BranchGenerator(strategy="ladder", max_branches=5)

        branches = generator.generate(sql_node)

        assert all("risk_score" in branch for branch in branches)
        assert any(branch["risk_score"] > 0 for branch in branches)
        assert any(branch.get("score_reasons") for branch in branches)


class TestBranchValidator:
    def test_validator_deduplicates_same_sql_by_score(self) -> None:
        validator = BranchValidator()
        branches = [
            {
                "branch_id": 0,
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "active_conditions": ["status != null"],
                "risk_score": 2.0,
            },
            {
                "branch_id": 1,
                "sql": "SELECT * FROM users WHERE status = #{status}",
                "active_conditions": ["status != null", "type != null"],
                "risk_score": 5.0,
            },
        ]

        result = validator.validate_and_deduplicate(branches, max_branches=10)

        assert len(result.branches) == 1
        assert result.branches[0]["risk_score"] == 5.0
