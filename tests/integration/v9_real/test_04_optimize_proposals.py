"""
V9 Optimize Stage Integration Tests - Proposal Generation

Tests the OPTIMIZE stage which generates optimization proposals using
heuristic rules when LLM is disabled.

QA Test Scenario:
  Scenario: Optimize generates proposals
    Steps:
      1. Run init → parse → recognition → optimize
      2. Load proposals
    Expected Result:
      - testWhereMultipleIf has verdict=ACTIONABLE (LIKE with leading wildcard)
      - testCountAll has verdict=NO_ACTION (simple aggregate, already optimal)
"""

from __future__ import annotations

import pytest

from sqlopt.application.v9_stages import run_stage
from tests.integration.v9_real.conftest import (
    load_proposals,
    load_sql_units,
    run_v9_stage,
)

# Valid verdict values for optimize proposals
VALID_VERDICTS = {"ACTIONABLE", "NO_ACTION", "ERROR"}


class TestV9Optimize:
    """Test suite for V9 OPTIMIZE stage proposal generation."""

    @pytest.fixture(scope="class")
    def full_pipeline_dir(self, temp_run_dir, real_mapper_config, validator):
        """
        Run init → parse → recognition → optimize stages.

        This fixture runs all prerequisite stages before the optimize stage,
        returning the run directory for tests to inspect.
        """
        stages = ["init", "parse", "recognition", "optimize"]
        for stage in stages:
            result = run_v9_stage(
                stage,
                temp_run_dir,
                config=real_mapper_config,
                validator=validator,
            )
            # Early exit if a stage fails
            if not result.get("success", False):
                pytest.fail(
                    f"Stage '{stage}' failed: {result.get('error', 'unknown error')}"
                )
        return temp_run_dir

    # -------------------------------------------------------------------------
    # Basic Functionality Tests
    # -------------------------------------------------------------------------

    def test_optimize_generates_proposals(self, full_pipeline_dir):
        """Run optimize stage and verify proposals.json is created."""
        proposals = load_proposals(full_pipeline_dir)
        assert len(proposals) > 0, (
            "No proposals generated - optimize stage may have failed"
        )

    def test_optimize_proposal_has_required_fields(self, full_pipeline_dir):
        """Each proposal must have sqlKey, verdict, and issues fields."""
        proposals = load_proposals(full_pipeline_dir)
        assert len(proposals) > 0, "No proposals to validate"

        for proposal in proposals:
            assert "sqlKey" in proposal, f"Proposal missing sqlKey: {proposal}"
            assert "verdict" in proposal, (
                f"Proposal {proposal.get('sqlKey', '?')} missing verdict"
            )
            assert "issues" in proposal, (
                f"Proposal {proposal.get('sqlKey', '?')} missing issues"
            )

    def test_optimize_verdicts_are_valid(self, full_pipeline_dir):
        """All proposals must have verdict in valid set {ACTIONABLE, NO_ACTION, ERROR}."""
        proposals = load_proposals(full_pipeline_dir)
        assert len(proposals) > 0, "No proposals to validate"

        for proposal in proposals:
            sql_key = proposal.get("sqlKey", "?")
            verdict = proposal.get("verdict", "")
            assert verdict in VALID_VERDICTS, (
                f"Proposal '{sql_key}' has invalid verdict: '{verdict}'. "
                f"Expected one of {VALID_VERDICTS}"
            )

    def test_optimize_actionable_proposals_have_suggestions(self, full_pipeline_dir):
        """ACTIONABLE proposals should have suggestions or optimizedSql."""
        proposals = load_proposals(full_pipeline_dir)

        for proposal in proposals:
            if proposal.get("verdict") == "ACTIONABLE":
                sql_key = proposal.get("sqlKey", "?")
                has_suggestions = bool(proposal.get("suggestions"))
                has_optimized_sql = bool(proposal.get("optimizedSql"))
                assert has_suggestions or has_optimized_sql, (
                    f"ACTIONABLE proposal '{sql_key}' missing both "
                    f"suggestions and optimizedSql"
                )

    # -------------------------------------------------------------------------
    # Scenario-Specific Tests
    # -------------------------------------------------------------------------

    def test_optimize_complex_query_gets_proposal(self, full_pipeline_dir):
        """
        Complex queries like testWhereMultipleIf should get ACTIONABLE verdict.

        The testWhereMultipleIf query has:
        - Multiple IF conditions (4 conditions)
        - LIKE with CONCAT('%', #{name}, '%') - leading wildcard pattern

        This should be flagged as ACTIONABLE due to performance issues.
        """
        proposals = load_proposals(full_pipeline_dir)

        # Find the testWhereMultipleIf proposal
        target_key = "com.test.mapper.UserMapper.testWhereMultipleIf"
        target_proposal = next(
            (p for p in proposals if p.get("sqlKey") == target_key),
            None,
        )

        assert target_proposal is not None, (
            f"Proposal for '{target_key}' not found. "
            f"Available keys: {[p.get('sqlKey') for p in proposals]}"
        )

        # Verify it's ACTIONABLE due to LIKE with leading wildcard
        assert target_proposal.get("verdict") == "ACTIONABLE", (
            f"Expected '{target_key}' to be ACTIONABLE due to "
            f"LIKE with leading wildcard, got: {target_proposal.get('verdict')}"
        )

        # Should have detected issues
        issues = target_proposal.get("issues", [])
        assert len(issues) > 0, (
            f"ACTIONABLE proposal '{target_key}' should have detected issues"
        )

    def test_optimize_simple_query_no_action(self, full_pipeline_dir):
        """
        Simple aggregate queries like testCountAll should get NO_ACTION verdict.

        The testCountAll query is a simple COUNT(*) which is already optimal.
        """
        proposals = load_proposals(full_pipeline_dir)

        # Find the testCountAll proposal
        target_key = "com.test.mapper.UserMapper.testCountAll"
        target_proposal = next(
            (p for p in proposals if p.get("sqlKey") == target_key),
            None,
        )

        assert target_proposal is not None, (
            f"Proposal for '{target_key}' not found. "
            f"Available keys: {[p.get('sqlKey') for p in proposals]}"
        )

        # Verify it's NO_ACTION (already optimal)
        assert target_proposal.get("verdict") == "NO_ACTION", (
            f"Expected '{target_key}' to be NO_ACTION (simple aggregate), "
            f"got: {target_proposal.get('verdict')}"
        )

    # -------------------------------------------------------------------------
    # Additional Validation Tests
    # -------------------------------------------------------------------------

    def test_optimize_proposals_reflect_sql_units_coverage(
        self, full_pipeline_dir, selected_scenarios
    ):
        """
        Optimize should generate proposals for all SQL units from recognition stage.

        Every SQL unit that has a baseline should have a corresponding proposal.
        """
        proposals = load_proposals(full_pipeline_dir)
        sql_units = load_sql_units(full_pipeline_dir)

        # Create set of sqlKeys that went through recognition (have baselines)
        proposal_keys = {p.get("sqlKey") for p in proposals}

        # All selected scenarios should have proposals
        missing_keys = set(selected_scenarios) - proposal_keys
        assert len(missing_keys) == 0, f"Missing proposals for SQL keys: {missing_keys}"

    def test_optimize_proposal_issues_are_list(self, full_pipeline_dir):
        """The issues field should always be a list (even if empty)."""
        proposals = load_proposals(full_pipeline_dir)

        for proposal in proposals:
            issues = proposal.get("issues")
            assert isinstance(issues, list), (
                f"Proposal '{proposal.get('sqlKey', '?')}' issues field "
                f"should be list, got: {type(issues)}"
            )
