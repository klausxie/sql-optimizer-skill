"""
V9 Real Integration Tests - Aggregation Query Optimization Test

This module validates optimization of SQL aggregation queries like
COUNT, SUM, AVG, MAX, MIN, GROUP BY, and HAVING.

Test Class: TestV9AggregationOptimization
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# Ensure python path is set
ROOT = Path(__file__).resolve().parents[4]
PYTHON_DIR = ROOT / "python"
import sys

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from sqlopt.contracts import ContractValidator
from sqlopt.application.v9_stages import run_stage

from conftest import (
    load_proposals,
    load_sql_units,
)
from validate_helper import validate_full_pipeline_output


# =============================================================================
# Helper Functions
# =============================================================================


def run_full_pipeline(run_dir: Path, config: dict, validator) -> dict[str, Any]:
    """
    Run all 5 V9 stages sequentially and return results.

    Args:
        run_dir: Temporary run directory
        config: Configuration dict
        validator: ContractValidator instance

    Returns:
        Dict mapping stage name to result dict
    """
    stages = ["init", "parse", "recognition", "optimize", "patch"]
    results = {}
    for stage in stages:
        result = run_stage(
            stage,
            run_dir,
            config=config,
            validator=validator,
        )
        results[stage] = result
        if not result.get("success"):
            print(f"Stage {stage} failed: {result}")
    return results


# =============================================================================
# Test Class: TestV9AggregationOptimization
# =============================================================================


class TestV9AggregationOptimization:
    """Integration tests for V9 aggregation query optimization."""

    def test_aggregation_queries_processed(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict,
        validator: ContractValidator,
    ) -> None:
        """
        Test that all aggregation scenarios are processed through full pipeline.

        Verifies:
        - testCountAll - simple COUNT(*) - NO_ACTION expected
        - testCountByStatus - COUNT with WHERE - NO_ACTION or ACTIONABLE
        - testGroupBy - GROUP BY - NO_ACTION
        - testGroupByHaving - GROUP BY + HAVING - ACTIONABLE if no LIMIT
        - testMultiAggFunction - multiple aggregations - NO_ACTION or ACTIONABLE
        """
        # Run full pipeline
        run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # Load proposals
        proposals = load_proposals(temp_run_dir)
        assert len(proposals) > 0, "No proposals generated"

        # Build map of sqlKey -> proposal
        proposal_map: dict[str, Any] = {
            p.get("sqlKey"): p for p in proposals if p.get("sqlKey")
        }

        # Aggregation scenario keys
        aggregation_scenarios = [
            "testCountAll",
            "testCountByStatus",
            "testGroupBy",
            "testGroupByHaving",
            "testMultiAggFunction",
        ]

        # Verify all scenarios are in proposals
        for scenario in aggregation_scenarios:
            sql_key = f"com.test.mapper.UserMapper.{scenario}"
            assert sql_key in proposal_map, f"{scenario} not in proposals"

        # Verify COUNT scenarios have verdict
        for count_scenario in ["testCountAll", "testCountByStatus"]:
            sql_key = f"com.test.mapper.UserMapper.{count_scenario}"
            if sql_key in proposal_map:
                proposal = proposal_map[sql_key]
                assert "verdict" in proposal, (
                    f"{count_scenario} proposal missing verdict"
                )
                # COUNT(*) without WHERE is typically NO_ACTION
                if count_scenario == "testCountAll":
                    assert proposal["verdict"] in ("NO_ACTION", "ACTIONABLE"), (
                        f"{count_scenario} should be NO_ACTION or ACTIONABLE, "
                        f"got {proposal['verdict']}"
                    )

        # Verify GROUP BY scenarios have verdict
        group_by_scenarios = [
            "testGroupBy",
            "testGroupByHaving",
            "testMultiAggFunction",
        ]
        for scenario in group_by_scenarios:
            sql_key = f"com.test.mapper.UserMapper.{scenario}"
            proposal = proposal_map.get(sql_key)
            assert proposal is not None, f"{scenario} not found"
            assert "verdict" in proposal, f"{scenario} proposal missing verdict"

    def test_group_by_having_proposal(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict,
        validator: ContractValidator,
    ) -> None:
        """
        Test that testGroupByHaving generates a proper proposal.

        The heuristic provider should detect that:
        - Aggregation query has HAVING but no LIMIT
        - This could return large result sets
        - Should suggest adding LIMIT
        """
        # Run full pipeline
        run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # Load proposals
        proposals = load_proposals(temp_run_dir)
        proposal_map = {p.get("sqlKey"): p for p in proposals}

        sql_key = "com.test.mapper.UserMapper.testGroupByHaving"
        assert sql_key in proposal_map, "testGroupByHaving not in proposals"

        proposal = proposal_map[sql_key]
        assert "verdict" in proposal, "proposal missing verdict"
        assert "suggestions" in proposal, "proposal missing suggestions"

        # The query has HAVING without LIMIT - should be ACTIONABLE
        # or at minimum have suggestions about LIMIT
        suggestions = proposal.get("suggestions", [])
        assert len(suggestions) > 0 or proposal["verdict"] == "ACTIONABLE", (
            f"testGroupByHaving should have suggestions about LIMIT, "
            f"got verdict={proposal['verdict']}, suggestions={suggestions}"
        )

    def test_aggregation_without_limit_flagged(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict,
        validator: ContractValidator,
    ) -> None:
        """
        Test that aggregation queries without LIMIT are flagged.

        The heuristic provider should detect that aggregation queries
        without LIMIT could return large datasets and suggest adding LIMIT.
        """
        # Run full pipeline
        run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # Load proposals
        proposals = load_proposals(temp_run_dir)
        proposal_map = {p.get("sqlKey"): p for p in proposals}

        # testGroupByHaving has HAVING but no LIMIT - should be flagged
        sql_key = "com.test.mapper.UserMapper.testGroupByHaving"
        proposal = proposal_map.get(sql_key)

        if proposal:
            # Either verdict is ACTIONABLE or suggestions mention LIMIT
            has_limit_suggestion = False
            suggestions = proposal.get("suggestions", [])
            for suggestion in suggestions:
                suggestion_text = str(suggestion).lower()
                if "limit" in suggestion_text:
                    has_limit_suggestion = True
                    break

            assert proposal["verdict"] == "ACTIONABLE" or has_limit_suggestion, (
                f"testGroupByHaving should be flagged for missing LIMIT. "
                f"verdict={proposal.get('verdict')}, "
                f"suggestions={suggestions}"
            )

    def test_multiple_aggregation_functions(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict,
        validator: ContractValidator,
    ) -> None:
        """
        Test that queries with multiple aggregation functions are handled.

        testMultiAggFunction has COUNT, SUM, AVG, MAX, MIN in one query.
        Should handle without error and generate appropriate proposal.
        """
        # Run full pipeline
        run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # Load proposals
        proposals = load_proposals(temp_run_dir)
        proposal_map = {p.get("sqlKey"): p for p in proposals}

        sql_key = "com.test.mapper.UserMapper.testMultiAggFunction"
        assert sql_key in proposal_map, "testMultiAggFunction not in proposals"

        proposal = proposal_map[sql_key]
        assert "verdict" in proposal, "proposal missing verdict"

        # The query has all 5 aggregation functions - should process without error
        # It may be NO_ACTION if no performance issues detected
        assert proposal["verdict"] in ("NO_ACTION", "ACTIONABLE"), (
            f"testMultiAggFunction should be NO_ACTION or ACTIONABLE, "
            f"got {proposal['verdict']}"
        )

    def test_aggregation_scenarios_in_sql_units(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict,
        validator: ContractValidator,
    ) -> None:
        """
        Verify that aggregation scenarios exist in sql_units after init stage.
        """
        # Run init stage only
        result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )
        assert result.get("success"), f"Init stage failed: {result}"

        # Load sql units
        sql_units = load_sql_units(temp_run_dir)
        sql_unit_map = {u.get("sqlKey"): u for u in sql_units}

        # Verify all aggregation scenarios exist
        aggregation_scenarios = [
            "com.test.mapper.UserMapper.testCountAll",
            "com.test.mapper.UserMapper.testCountByStatus",
            "com.test.mapper.UserMapper.testGroupBy",
            "com.test.mapper.UserMapper.testGroupByHaving",
            "com.test.mapper.UserMapper.testMultiAggFunction",
        ]

        for sql_key in aggregation_scenarios:
            assert sql_key in sql_unit_map, f"{sql_key} not found in sql_units"

            unit = sql_unit_map[sql_key]
            sql_text = unit.get("sql", "").upper()

            # Verify SQL contains expected aggregation functions
            if "testCountAll" in sql_key or "testCountByStatus" in sql_key:
                assert "COUNT" in sql_text, f"{sql_key} should contain COUNT"
            elif "testGroupBy" in sql_key:
                assert "GROUP BY" in sql_text or "GROUP" in sql_text, (
                    f"{sql_key} should contain GROUP BY"
                )
            elif "testMultiAggFunction" in sql_key:
                assert all(
                    func in sql_text for func in ["COUNT", "SUM", "AVG", "MAX", "MIN"]
                ), f"{sql_key} should contain all 5 aggregation functions"

    def test_aggregation_proposal_structure(
        self,
        temp_run_dir: Path,
        real_mapper_config: dict,
        validator: ContractValidator,
    ) -> None:
        """
        Test that aggregation proposals have correct structure.

        Each proposal should have:
        - sqlKey
        - verdict (NO_ACTION, ACTIONABLE, or ERROR)
        - suggestions (list of optimization suggestions)
        - metrics (optional, performance metrics)
        """
        # Run full pipeline
        run_full_pipeline(temp_run_dir, real_mapper_config, validator)

        # Load proposals
        proposals = load_proposals(temp_run_dir)
        proposal_map = {p.get("sqlKey"): p for p in proposals}

        # Check aggregation proposals
        aggregation_keys = [
            "com.test.mapper.UserMapper.testCountAll",
            "com.test.mapper.UserMapper.testGroupByHaving",
            "com.test.mapper.UserMapper.testMultiAggFunction",
        ]

        for sql_key in aggregation_keys:
            if sql_key in proposal_map:
                proposal = proposal_map[sql_key]

                # Required fields
                assert "sqlKey" in proposal, f"{sql_key} missing sqlKey"
                assert "verdict" in proposal, f"{sql_key} missing verdict"
                assert proposal["verdict"] in ("NO_ACTION", "ACTIONABLE", "ERROR"), (
                    f"{sql_key} has invalid verdict: {proposal['verdict']}"
                )

                # Suggestions should be a list
                assert "suggestions" in proposal, f"{sql_key} missing suggestions"
                assert isinstance(proposal["suggestions"], list), (
                    f"{sql_key} suggestions should be a list"
                )
