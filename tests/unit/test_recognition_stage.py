"""Unit tests for RecognitionStage."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlopt.common.llm_mock_generator import MockLLMProvider
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.recognition.stage import RecognitionStage


class TestRecognitionStageRun:
    """Tests for RecognitionStage.run() method."""

    def _create_parse_file(self, run_dir: Path, run_id: str) -> None:
        """Helper to create a valid parse file."""
        parse_dir = run_dir / "runs" / run_id / "parse"
        parse_dir.mkdir(parents=True, exist_ok=True)
        parse_file = parse_dir / "sql_units_with_branches.json"

        parse_data = ParseOutput(
            sql_units_with_branches=[
                SQLUnitWithBranches(
                    sql_unit_id="sql_unit_1",
                    branches=[
                        SQLBranch(
                            path_id="path_1",
                            condition="status = 'active'",
                            expanded_sql="SELECT * FROM users WHERE status = 'active'",
                            is_valid=True,
                        ),
                        SQLBranch(
                            path_id="path_2",
                            condition="status = 'inactive'",
                            expanded_sql="SELECT * FROM users WHERE status = 'inactive'",
                            is_valid=True,
                        ),
                    ],
                ),
                SQLUnitWithBranches(
                    sql_unit_id="sql_unit_2",
                    branches=[
                        SQLBranch(
                            path_id="path_3",
                            condition=None,
                            expanded_sql="SELECT * FROM orders",
                            is_valid=True,
                        ),
                    ],
                ),
            ]
        )
        parse_file.write_text(parse_data.to_json(), encoding="utf-8")

    def test_run_with_valid_run_id_and_parse_data(self):
        """Test RecognitionStage.run() with valid run_id and parse data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_run_001"
            self._create_parse_file(Path(tmpdir), run_id)

            # Change to temp dir so RecognitionStage writes to our temp location
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id)
                output = stage.run()

                assert isinstance(output, RecognitionOutput)
                assert len(output.baselines) == 3
            finally:
                os.chdir(original_cwd)

    def test_run_returns_stub_when_run_id_is_none(self):
        """Test RecognitionStage.run() returns stub when run_id is None."""
        stage = RecognitionStage(run_id=None)
        output = stage.run()

        assert isinstance(output, RecognitionOutput)
        assert len(output.baselines) == 1
        assert output.baselines[0].sql_unit_id == "stub-1"
        assert output.baselines[0].path_id == "p1"
        assert output.baselines[0].estimated_cost == 100.0
        assert output.baselines[0].actual_time_ms == 50.0

    def test_run_returns_stub_when_run_id_not_passed(self):
        """Test RecognitionStage.run() returns stub when run_id is not passed."""
        stage = RecognitionStage(run_id=None)
        output = stage.run(run_id=None)

        assert isinstance(output, RecognitionOutput)
        assert len(output.baselines) == 1
        baseline = output.baselines[0]
        assert baseline.sql_unit_id == "stub-1"

    def test_run_returns_stub_when_parse_file_doesnt_exist(self):
        """Test RecognitionStage.run() returns stub when parse file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id="nonexistent_run")
                output = stage.run()

                assert isinstance(output, RecognitionOutput)
                assert len(output.baselines) == 1
                assert output.baselines[0].sql_unit_id == "stub-1"
            finally:
                os.chdir(original_cwd)

    def test_run_skips_invalid_branches(self):
        """Test RecognitionStage.run() skips invalid branches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_run_002"
            parse_dir = Path(tmpdir) / "runs" / run_id / "parse"
            parse_dir.mkdir(parents=True, exist_ok=True)
            parse_file = parse_dir / "sql_units_with_branches.json"

            parse_data = ParseOutput(
                sql_units_with_branches=[
                    SQLUnitWithBranches(
                        sql_unit_id="sql_unit_valid",
                        branches=[
                            SQLBranch(
                                path_id="path_valid",
                                condition=None,
                                expanded_sql="SELECT * FROM users",
                                is_valid=True,
                            ),
                        ],
                    ),
                    SQLUnitWithBranches(
                        sql_unit_id="sql_unit_invalid",
                        branches=[
                            SQLBranch(
                                path_id="path_invalid",
                                condition=None,
                                expanded_sql="SELECT * FROM orders",
                                is_valid=False,
                            ),
                        ],
                    ),
                ]
            )
            parse_file.write_text(parse_data.to_json(), encoding="utf-8")

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id)
                output = stage.run()

                assert isinstance(output, RecognitionOutput)
                assert len(output.baselines) == 1
                assert output.baselines[0].sql_unit_id == "sql_unit_valid"
                assert output.baselines[0].path_id == "path_valid"
            finally:
                os.chdir(original_cwd)

    def test_run_creates_correct_output_file(self):
        """Test RecognitionStage.run() creates correct output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_run_003"
            self._create_parse_file(Path(tmpdir), run_id)

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id)
                output = stage.run()

                output_file = Path("runs") / run_id / "recognition" / "baselines.json"
                assert output_file.exists()

                written_content = output_file.read_text(encoding="utf-8")
                parsed_output = RecognitionOutput.from_json(written_content)
                assert len(parsed_output.baselines) == len(output.baselines)
            finally:
                os.chdir(original_cwd)

    def test_run_with_multiple_sql_units(self):
        """Test RecognitionStage.run() handles multiple SQL units correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_run_004"
            parse_dir = Path(tmpdir) / "runs" / run_id / "parse"
            parse_dir.mkdir(parents=True, exist_ok=True)
            parse_file = parse_dir / "sql_units_with_branches.json"

            parse_data = ParseOutput(
                sql_units_with_branches=[
                    SQLUnitWithBranches(
                        sql_unit_id="unit_a",
                        branches=[
                            SQLBranch(
                                path_id="path_a1",
                                condition=None,
                                expanded_sql="SELECT * FROM table_a WHERE id = 1",
                                is_valid=True,
                            ),
                        ],
                    ),
                    SQLUnitWithBranches(
                        sql_unit_id="unit_b",
                        branches=[
                            SQLBranch(
                                path_id="path_b1",
                                condition=None,
                                expanded_sql="SELECT * FROM table_b JOIN table_c ON id = id",
                                is_valid=True,
                            ),
                        ],
                    ),
                ]
            )
            parse_file.write_text(parse_data.to_json(), encoding="utf-8")

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id)
                output = stage.run()

                assert isinstance(output, RecognitionOutput)
                assert len(output.baselines) == 2
                baseline_ids = {b.sql_unit_id for b in output.baselines}
                assert baseline_ids == {"unit_a", "unit_b"}
            finally:
                os.chdir(original_cwd)


class TestRecognitionStageStubOutput:
    """Tests for RecognitionStage._create_stub_output() method."""

    def test_create_stub_output_returns_recognition_output(self):
        """Test _create_stub_output returns RecognitionOutput with stub baseline."""
        stage = RecognitionStage()
        output = stage._create_stub_output()  # noqa: SLF001

        assert isinstance(output, RecognitionOutput)
        assert len(output.baselines) == 1

    def test_create_stub_output_baseline_structure(self):
        """Test stub baseline has correct structure."""
        stage = RecognitionStage()
        output = stage._create_stub_output()  # noqa: SLF001

        baseline = output.baselines[0]
        assert baseline.sql_unit_id == "stub-1"
        assert baseline.path_id == "p1"
        assert baseline.plan == {"cost": 100.0, "rows": 1000}
        assert baseline.estimated_cost == 100.0
        assert baseline.actual_time_ms == 50.0


class TestRecognitionStageWriteOutput:
    """Tests for RecognitionStage._write_output() method."""

    def test_write_output_creates_directory(self):
        """Test _write_output creates recognition directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_write"
            output = RecognitionOutput(
                baselines=[
                    PerformanceBaseline(
                        sql_unit_id="test_unit",
                        path_id="test_path",
                        plan={"cost": 50.0},
                        estimated_cost=50.0,
                        actual_time_ms=25.0,
                    )
                ]
            )

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage()
                stage._write_output(run_id, output)  # noqa: SLF001

                output_dir = Path("runs") / run_id / "recognition"
                assert output_dir.exists()
                assert output_dir.is_dir()
            finally:
                os.chdir(original_cwd)

    def test_write_output_creates_baselines_json(self):
        """Test _write_output creates baselines.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_write_json"
            baseline = PerformanceBaseline(
                sql_unit_id="test_unit",
                path_id="test_path",
                plan={"cost": 50.0},
                estimated_cost=50.0,
                actual_time_ms=25.0,
            )
            output = RecognitionOutput(baselines=[baseline])

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage()
                stage._write_output(run_id, output)  # noqa: SLF001

                output_file = Path("runs") / run_id / "recognition" / "baselines.json"
                assert output_file.exists()

                parsed = RecognitionOutput.from_json(output_file.read_text(encoding="utf-8"))
                assert len(parsed.baselines) == 1
                assert parsed.baselines[0].sql_unit_id == "test_unit"
            finally:
                os.chdir(original_cwd)


class TestPerformanceBaselineStructure:
    """Tests for PerformanceBaseline object structure."""

    def test_baseline_has_required_fields(self):
        """Test PerformanceBaseline has all required fields."""
        baseline = PerformanceBaseline(
            sql_unit_id="unit_1",
            path_id="path_1",
            plan={"Node Type": "Seq Scan", "cost": 100.0},
            estimated_cost=100.0,
            actual_time_ms=50.0,
        )

        assert baseline.sql_unit_id == "unit_1"
        assert baseline.path_id == "path_1"
        assert baseline.plan == {"Node Type": "Seq Scan", "cost": 100.0}
        assert baseline.estimated_cost == 100.0
        assert baseline.actual_time_ms == 50.0

    def test_baseline_actual_time_ms_optional(self):
        """Test PerformanceBaseline actual_time_ms is optional."""
        baseline = PerformanceBaseline(
            sql_unit_id="unit_1",
            path_id="path_1",
            plan={},
            estimated_cost=10.0,
        )

        assert baseline.actual_time_ms is None

    def test_baseline_to_json_and_from_json(self):
        """Test PerformanceBaseline serialization."""
        original = PerformanceBaseline(
            sql_unit_id="unit_test",
            path_id="path_test",
            plan={"Node Type": "Hash Join"},
            estimated_cost=75.0,
            actual_time_ms=30.0,
        )

        json_str = original.to_json()
        restored = PerformanceBaseline.from_json(json_str)

        assert restored.sql_unit_id == original.sql_unit_id
        assert restored.path_id == original.path_id
        assert restored.plan == original.plan
        assert restored.estimated_cost == original.estimated_cost
        assert restored.actual_time_ms == original.actual_time_ms


class TestMockLLMProviderIntegration:
    """Tests for MockLLMProvider.generate_baseline() integration."""

    def test_generate_baseline_returns_dict_with_required_keys(self):
        """Test generate_baseline returns dict with expected keys."""
        provider = MockLLMProvider()
        result = provider.generate_baseline("SELECT * FROM users", "postgresql")

        assert isinstance(result, dict)
        assert "sql_unit_id" in result
        assert "path_id" in result
        assert "plan" in result
        assert "estimated_cost" in result
        assert "actual_time_ms" in result

    def test_generate_baseline_different_sql_different_ids(self):
        """Test different SQL generates different unit/path IDs."""
        provider = MockLLMProvider()
        result1 = provider.generate_baseline("SELECT * FROM users", "postgresql")
        result2 = provider.generate_baseline("SELECT * FROM orders", "postgresql")

        assert result1["sql_unit_id"] != result2["sql_unit_id"]
        assert result1["path_id"] != result2["path_id"]

    def test_generate_baseline_plan_structure(self):
        """Test generate_baseline returns properly structured plan."""
        provider = MockLLMProvider()
        result = provider.generate_baseline(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id", "postgresql"
        )

        assert isinstance(result["plan"], dict)
        assert "Plan" in result["plan"]

    def test_generate_baseline_cost_estimation(self):
        """Test generate_baseline returns cost estimation."""
        provider = MockLLMProvider()
        result = provider.generate_baseline("SELECT * FROM users", "postgresql")

        assert isinstance(result["estimated_cost"], float)
        assert result["estimated_cost"] > 0

    def test_generate_baseline_with_join_has_higher_cost(self):
        """Test SQL with JOIN has higher cost than simple SQL."""
        provider = MockLLMProvider()
        simple_sql = "SELECT * FROM users"
        join_sql = "SELECT * FROM users JOIN orders ON users.id = orders.user_id"

        result_simple = provider.generate_baseline(simple_sql, "postgresql")
        result_join = provider.generate_baseline(join_sql, "postgresql")

        assert result_join["estimated_cost"] > result_simple["estimated_cost"]


class TestRecognitionStageWithMockLLM:
    """Tests for RecognitionStage using MockLLMProvider."""

    def test_stage_uses_mock_llm_provider(self):
        """Test RecognitionStage uses provided MockLLMProvider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_mock_llm"
            parse_dir = Path(tmpdir) / "runs" / run_id / "parse"
            parse_dir.mkdir(parents=True, exist_ok=True)
            parse_file = parse_dir / "sql_units_with_branches.json"

            parse_data = ParseOutput(
                sql_units_with_branches=[
                    SQLUnitWithBranches(
                        sql_unit_id="mock_unit",
                        branches=[
                            SQLBranch(
                                path_id="mock_path",
                                condition=None,
                                expanded_sql="SELECT * FROM test_table",
                                is_valid=True,
                            ),
                        ],
                    ),
                ]
            )
            parse_file.write_text(parse_data.to_json(), encoding="utf-8")

            mock_provider = MockLLMProvider()
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id, mock_llm=mock_provider)
                output = stage.run()

                assert isinstance(output, RecognitionOutput)
                assert len(output.baselines) == 1
                baseline = output.baselines[0]
                assert baseline.sql_unit_id == "mock_unit"
                assert baseline.path_id == "mock_path"
            finally:
                os.chdir(original_cwd)

    def test_stage_generates_correct_baseline_count(self):
        """Test stage generates correct number of baselines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_baseline_count"
            parse_dir = Path(tmpdir) / "runs" / run_id / "parse"
            parse_dir.mkdir(parents=True, exist_ok=True)
            parse_file = parse_dir / "sql_units_with_branches.json"

            # Create parse data with 3 valid branches total
            parse_data = ParseOutput(
                sql_units_with_branches=[
                    SQLUnitWithBranches(
                        sql_unit_id="unit_1",
                        branches=[
                            SQLBranch(
                                path_id="p1", condition=None, expanded_sql="SELECT 1", is_valid=True
                            ),
                            SQLBranch(
                                path_id="p2", condition=None, expanded_sql="SELECT 2", is_valid=True
                            ),
                        ],
                    ),
                    SQLUnitWithBranches(
                        sql_unit_id="unit_2",
                        branches=[
                            SQLBranch(
                                path_id="p3", condition=None, expanded_sql="SELECT 3", is_valid=True
                            ),
                        ],
                    ),
                ]
            )
            parse_file.write_text(parse_data.to_json(), encoding="utf-8")

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id)
                output = stage.run()

                assert len(output.baselines) == 3
            finally:
                os.chdir(original_cwd)


class TestRecognitionOutputStructure:
    """Tests for RecognitionOutput structure."""

    def test_recognition_output_to_json(self):
        """Test RecognitionOutput serializes correctly."""
        baselines = [
            PerformanceBaseline(
                sql_unit_id="u1",
                path_id="p1",
                plan={"cost": 10.0},
                estimated_cost=10.0,
            ),
            PerformanceBaseline(
                sql_unit_id="u2",
                path_id="p2",
                plan={"cost": 20.0},
                estimated_cost=20.0,
                actual_time_ms=15.0,
            ),
        ]
        output = RecognitionOutput(baselines=baselines)
        json_str = output.to_json()

        parsed = json.loads(json_str)
        assert "baselines" in parsed
        assert len(parsed["baselines"]) == 2

    def test_recognition_output_from_json(self):
        """Test RecognitionOutput deserializes correctly."""
        json_str = json.dumps(
            {
                "baselines": [
                    {
                        "sql_unit_id": "test_unit",
                        "path_id": "test_path",
                        "plan": {"Node Type": "Seq Scan"},
                        "estimated_cost": 50.0,
                        "actual_time_ms": 25.0,
                    }
                ]
            }
        )

        output = RecognitionOutput.from_json(json_str)
        assert len(output.baselines) == 1
        assert output.baselines[0].sql_unit_id == "test_unit"
