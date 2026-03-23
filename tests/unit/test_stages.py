"""Unit tests for all pipeline stages."""

import pytest
from sqlopt.contracts.init import InitOutput
from sqlopt.contracts.optimize import OptimizeOutput
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import RecognitionOutput
from sqlopt.contracts.result import ResultOutput
from sqlopt.stages.base import Stage
from sqlopt.stages.init.stage import InitStage
from sqlopt.stages.optimize.stage import OptimizeStage
from sqlopt.stages.parse.stage import ParseStage
from sqlopt.stages.recognition.stage import RecognitionStage
from sqlopt.stages.result.stage import ResultStage


class TestStageBase:
    """Tests for the Stage base class."""

    def test_stage_name_property(self):
        """Test that Stage name property returns the set name."""

        class DummyStage(Stage[None, None]):
            def run(self, _input_data=None):
                return None

        stage = DummyStage("test_stage")
        assert stage.name == "test_stage"


class TestInitStage:
    """Tests for InitStage."""

    def test_init_stage_instantiation(self):
        """Test InitStage can be instantiated."""
        stage = InitStage()
        assert isinstance(stage, InitStage)
        assert isinstance(stage, Stage)

    def test_init_stage_name(self):
        """Test InitStage has correct name."""
        stage = InitStage()
        assert stage.name == "init"

    def test_init_stage_run_returns_init_output(self):
        """Test InitStage.run() returns InitOutput."""
        stage = InitStage()
        output = stage.run()
        assert isinstance(output, InitOutput)

    def test_init_output_has_sql_units(self):
        """Test InitOutput contains sql_units list."""
        stage = InitStage()
        output = stage.run()
        assert hasattr(output, "sql_units")
        assert isinstance(output.sql_units, list)
        assert len(output.sql_units) > 0

    def test_init_output_has_run_id(self):
        """Test InitOutput contains run_id."""
        stage = InitStage()
        output = stage.run()
        assert hasattr(output, "run_id")
        assert isinstance(output.run_id, str)
        assert output.run_id == "stub-run"


class TestParseStage:
    """Tests for ParseStage."""

    def test_parse_stage_instantiation(self):
        """Test ParseStage can be instantiated."""
        stage = ParseStage()
        assert isinstance(stage, ParseStage)
        assert isinstance(stage, Stage)

    def test_parse_stage_name(self):
        """Test ParseStage has correct name."""
        stage = ParseStage()
        assert stage.name == "parse"

    def test_parse_stage_run_returns_parse_output(self):
        """Test ParseStage.run() returns ParseOutput."""
        stage = ParseStage()
        output = stage.run()
        assert isinstance(output, ParseOutput)

    def test_parse_output_has_sql_units_with_branches(self):
        """Test ParseOutput contains sql_units_with_branches list."""
        stage = ParseStage()
        output = stage.run()
        assert hasattr(output, "sql_units_with_branches")
        assert isinstance(output.sql_units_with_branches, list)
        assert len(output.sql_units_with_branches) > 0


class TestRecognitionStage:
    """Tests for RecognitionStage."""

    def test_recognition_stage_instantiation(self):
        """Test RecognitionStage can be instantiated."""
        stage = RecognitionStage()
        assert isinstance(stage, RecognitionStage)
        assert isinstance(stage, Stage)

    def test_recognition_stage_name(self):
        """Test RecognitionStage has correct name."""
        stage = RecognitionStage()
        assert stage.name == "recognition"

    def test_recognition_stage_run_returns_recognition_output(self):
        """Test RecognitionStage.run() returns RecognitionOutput."""
        stage = RecognitionStage()
        output = stage.run()
        assert isinstance(output, RecognitionOutput)

    def test_recognition_output_has_baselines(self):
        """Test RecognitionOutput contains baselines list."""
        stage = RecognitionStage()
        output = stage.run()
        assert hasattr(output, "baselines")
        assert isinstance(output.baselines, list)
        assert len(output.baselines) > 0


class TestOptimizeStage:
    """Tests for OptimizeStage."""

    def test_optimize_stage_instantiation(self):
        """Test OptimizeStage can be instantiated."""
        stage = OptimizeStage()
        assert isinstance(stage, OptimizeStage)
        assert isinstance(stage, Stage)

    def test_optimize_stage_name(self):
        """Test OptimizeStage has correct name."""
        stage = OptimizeStage()
        assert stage.name == "optimize"

    def test_optimize_stage_run_returns_optimize_output(self):
        """Test OptimizeStage.run() returns OptimizeOutput."""
        stage = OptimizeStage()
        output = stage.run()
        assert isinstance(output, OptimizeOutput)

    def test_optimize_output_has_proposals(self):
        """Test OptimizeOutput contains proposals list."""
        stage = OptimizeStage()
        output = stage.run()
        assert hasattr(output, "proposals")
        assert isinstance(output.proposals, list)
        assert len(output.proposals) > 0


class TestResultStage:
    """Tests for ResultStage."""

    def test_result_stage_instantiation(self):
        """Test ResultStage can be instantiated."""
        stage = ResultStage()
        assert isinstance(stage, ResultStage)
        assert isinstance(stage, Stage)

    def test_result_stage_name(self):
        """Test ResultStage has correct name."""
        stage = ResultStage()
        assert stage.name == "result"

    def test_result_stage_run_returns_result_output(self):
        """Test ResultStage.run() returns ResultOutput."""
        stage = ResultStage()
        output = stage.run()
        assert isinstance(output, ResultOutput)

    def test_result_output_has_report(self):
        """Test ResultOutput contains report."""
        stage = ResultStage()
        output = stage.run()
        assert hasattr(output, "report")
        assert output.report is not None

    def test_result_output_has_patches(self):
        """Test ResultOutput contains patches list."""
        stage = ResultStage()
        output = stage.run()
        assert hasattr(output, "patches")
        assert isinstance(output.patches, list)
        assert len(output.patches) > 0

    def test_result_output_can_patch_is_bool(self):
        """Test ResultOutput can_patch is boolean."""
        stage = ResultStage()
        output = stage.run()
        assert hasattr(output, "can_patch")
        assert isinstance(output.can_patch, bool)
