from __future__ import annotations

import pytest

from sqlopt.stages.branching.branch_generator import BranchGenerator
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
