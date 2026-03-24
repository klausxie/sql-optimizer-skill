"""Unit tests for StageRunner pipeline orchestrator."""

import re
import tempfile
from pathlib import Path

import pytest
import yaml
from sqlopt.stage_runner import (
    STAGE_ORDER,
    PipelineResult,
    StageResult,
    StageRunner,
)


class TestStageRunnerInit:
    """Tests for StageRunner initialization."""

    def test_run_id_is_timestamp_format(self):
        """Test that run_id is in timestamp format run-YYYYMMDD-HHMMSS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)
            assert runner.run_id.startswith("run-")
            assert re.fullmatch(r"run-\d{8}-\d{6}", runner.run_id) is not None

    def test_config_loaded_from_path(self):
        """Test that config is loaded from the provided path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(
                yaml.dump(
                    {
                        "config_version": "v1",
                        "project_root_path": tmpdir,
                        "db_platform": "mysql",
                    }
                )
            )
            runner = StageRunner(str(config_path), base_dir=tmpdir)
            assert runner.config.db_platform == "mysql"
            assert runner.config.project_root_path == tmpdir

    def test_progress_tracker_registered_all_stages(self):
        """Test that all 5 stages are registered in progress tracker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)
            assert set(runner.progress.stages.keys()) == set(STAGE_ORDER)


class TestStageResult:
    """Tests for StageResult dataclass."""

    def test_stage_result_with_output(self):
        """Test StageResult with output data."""
        result = StageResult(stage_name="init", output={"status": "completed"})
        assert result.stage_name == "init"
        assert result.output == {"status": "completed"}
        assert result.error is None

    def test_stage_result_with_error(self):
        """Test StageResult with error."""
        result = StageResult(stage_name="parse", error="Parse error")
        assert result.stage_name == "parse"
        assert result.output is None
        assert result.error == "Parse error"

    def test_stage_result_default_values(self):
        """Test StageResult default values are None."""
        result = StageResult(stage_name="optimize")
        assert result.stage_name == "optimize"
        assert result.output is None
        assert result.error is None


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_pipeline_result_success(self):
        """Test PipelineResult with success=True."""
        result = PipelineResult(success=True)
        assert result.success is True
        assert result.stage_results == {}

    def test_pipeline_result_failure(self):
        """Test PipelineResult with success=False."""
        result = PipelineResult(success=False)
        assert result.success is False

    def test_pipeline_result_with_stage_results(self):
        """Test PipelineResult contains stage results dict."""
        stage_results = {
            "init": StageResult(stage_name="init", output={"status": "completed"}),
            "parse": StageResult(stage_name="parse", output={"status": "completed"}),
        }
        result = PipelineResult(success=True, stage_results=stage_results)
        assert len(result.stage_results) == 2
        assert "init" in result.stage_results
        assert "parse" in result.stage_results


class TestStageRunnerRunStage:
    """Tests for StageRunner.run_stage() method."""

    def test_run_stage_executes_single_stage(self):
        """Test that run_stage executes a single named stage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            runner.run_stage("init")

            status = runner.get_status()
            assert status["stages"]["init"]["status"] == "completed"

    def test_run_stage_invalid_name_raises_value_error(self):
        """Test that run_stage raises ValueError for invalid stage name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            with pytest.raises(ValueError, match="Invalid stage"):
                runner.run_stage("invalid_stage")


class TestStageRunnerRunAll:
    """Tests for StageRunner.run_all() method."""

    def test_run_all_executes_all_5_stages_in_order(self):
        """Test that run_all executes all 5 stages in STAGE_ORDER."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            result = runner.run_all()

            assert isinstance(result, PipelineResult)
            assert result.success is True
            assert len(result.stage_results) == len(STAGE_ORDER)

            status = runner.get_status()
            for stage in STAGE_ORDER:
                assert status["stages"][stage]["status"] == "completed"

    def test_run_all_returns_pipeline_result(self):
        """Test that run_all returns a PipelineResult."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            result = runner.run_all()

            assert isinstance(result, PipelineResult)
            assert hasattr(result, "success")
            assert hasattr(result, "stage_results")

    def test_run_all_all_stages_succeed(self):
        """Test that all stages succeed when running run_all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            result = runner.run_all()

            assert result.success is True


class TestStageRunnerGetStatus:
    """Tests for StageRunner.get_status() method."""

    def test_get_status_returns_dict(self):
        """Test that get_status returns a dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            status = runner.get_status()

            assert isinstance(status, dict)

    def test_get_status_contains_run_id(self):
        """Test that get_status result contains run_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            status = runner.get_status()

            assert "run_id" in status
            assert status["run_id"] == runner.run_id

    def test_get_status_contains_stages(self):
        """Test that get_status result contains stages dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            status = runner.get_status()

            assert "stages" in status
            assert isinstance(status["stages"], dict)
            assert set(status["stages"].keys()) == set(STAGE_ORDER)

    def test_get_status_after_run_stage(self):
        """Test get_status shows correct stage status after run_stage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            runner.run_stage("init")

            status = runner.get_status()
            assert status["stages"]["init"]["status"] == "completed"
            assert status["stages"]["parse"]["status"] == "pending"


class TestStageRunnerIsComplete:
    """Tests for StageRunner.is_complete() method."""

    def test_is_complete_false_before_run(self):
        """Test is_complete returns False before any stages run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            assert runner.is_complete() is False

    def test_is_complete_true_after_run_all(self):
        """Test is_complete returns True after run_all completes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            runner.run_all()

            assert runner.is_complete() is True

    def test_is_complete_false_after_partial_run(self):
        """Test is_complete returns False after only some stages run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            runner.run_stage("init")
            runner.run_stage("parse")

            assert runner.is_complete() is False


class TestStageRunnerHasFailures:
    """Tests for StageRunner.has_failures() method."""

    def test_has_failures_false_before_run(self):
        """Test has_failures returns False before any stages run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            assert runner.has_failures() is False

    def test_has_failures_false_after_successful_run(self):
        """Test has_failures returns False after successful run_all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "sqlopt.yml"
            config_path.write_text(yaml.dump({"config_version": "v1"}))
            runner = StageRunner(str(config_path), base_dir=tmpdir)

            runner.run_all()

            assert runner.has_failures() is False


class TestStageOrder:
    """Tests for STAGE_ORDER constant."""

    def test_stage_order_contains_5_stages(self):
        """Test STAGE_ORDER contains exactly 5 stages."""
        assert len(STAGE_ORDER) == 5

    def test_stage_order_correct_sequence(self):
        """Test STAGE_ORDER has correct sequence."""
        assert STAGE_ORDER == ["init", "parse", "recognition", "optimize", "result"]
