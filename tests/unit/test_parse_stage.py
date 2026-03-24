import pytest
from sqlopt.common.config import SQLOptConfig
from sqlopt.stages.parse.stage import ParseStage
from sqlopt.contracts.parse import ParseOutput


class TestParseStage:
    """Tests for ParseStage with config integration."""

    def test_parse_stage_with_config(self):
        """ParseStage accepts config and uses it."""
        config = SQLOptConfig(parse_strategy="ladder", parse_max_branches=50)
        stage = ParseStage(run_id="test", config=config)
        assert stage.config == config

    def test_parse_stage_without_config(self):
        """ParseStage works without config (uses defaults)."""
        stage = ParseStage(run_id="test")
        assert stage.config is None

    def test_parse_stage_run_returns_parse_output(self):
        """run() returns ParseOutput with correct structure."""
        config = SQLOptConfig(parse_strategy="ladder", parse_max_branches=50)
        stage = ParseStage(run_id="test", config=config)
        output = stage.run()
        assert isinstance(output, ParseOutput)
        assert hasattr(output, "sql_units_with_branches")

    def test_parse_stage_stub_data_without_run_id(self):
        """Without run_id, returns stub data."""
        stage = ParseStage()
        output = stage.run()
        assert isinstance(output, ParseOutput)
        assert len(output.sql_units_with_branches) >= 1
