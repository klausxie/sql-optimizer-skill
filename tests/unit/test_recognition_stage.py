"""Unit tests for RecognitionStage."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlopt.common.llm_mock_generator import MockLLMProvider
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.recognition.stage import RecognitionStage


class FakeDBConnector:
    """Simple fake DB connector for recognition-stage tests."""

    def __init__(
        self,
        explain_result: dict | None = None,
        query_result: list[dict] | None = None,
        query_error: Exception | None = None,
    ) -> None:
        self.explain_result = explain_result or {
            "plan": {
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Total Cost": 42.0,
                    "Actual Total Time": 5.5,
                    "Actual Rows": 2,
                }
            },
            "estimated_cost": 42.0,
            "actual_time_ms": 5.5,
        }
        self.query_result = query_result or [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]
        self.query_error = query_error
        self.explain_calls: list[str] = []
        self.query_calls: list[str] = []
        self.disconnected = False

    def execute_explain(self, sql: str) -> dict:
        self.explain_calls.append(sql)
        return self.explain_result

    def execute_query(self, sql: str, params: tuple | None = None) -> list[dict]:
        del params
        self.query_calls.append(sql)
        if self.query_error is not None:
            raise self.query_error
        return self.query_result

    def disconnect(self) -> None:
        self.disconnected = True


class DBBackedRecognitionProvider(MockLLMProvider):
    """Provider wrapper that exposes a DB connector and forbids LLM baseline fallback."""

    def __init__(self, db_connector: FakeDBConnector) -> None:
        super().__init__()
        self.db_connector = db_connector

    def generate_baseline(self, sql: str, platform: str = "postgresql") -> dict:
        raise AssertionError(
            f"generate_baseline should not be called when DB connector is available: {sql} / {platform}"
        )


class TestRecognitionStageRun:
    """Tests for RecognitionStage.run() method."""

    def _create_parse_file(self, run_dir: Path, run_id: str) -> None:
        """Helper to create parse output in per-unit format."""
        parse_dir = run_dir / "runs" / run_id / "parse"
        units_dir = parse_dir / "units"
        units_dir.mkdir(parents=True, exist_ok=True)

        unit_ids = ["sql_unit_1", "sql_unit_2"]
        (units_dir / "_index.json").write_text(json.dumps(unit_ids), encoding="utf-8")

        sql_unit_1_data = {
            "sql_unit_id": "sql_unit_1",
            "branches": [
                {
                    "path_id": "path_1",
                    "condition": "status = 'active'",
                    "expanded_sql": "SELECT * FROM users WHERE status = 'active'",
                    "is_valid": True,
                },
                {
                    "path_id": "path_2",
                    "condition": "status = 'inactive'",
                    "expanded_sql": "SELECT * FROM users WHERE status = 'inactive'",
                    "is_valid": True,
                },
            ],
        }
        (units_dir / "sql_unit_1.json").write_text(json.dumps(sql_unit_1_data), encoding="utf-8")

        sql_unit_2_data = {
            "sql_unit_id": "sql_unit_2",
            "branches": [
                {
                    "path_id": "path_3",
                    "condition": None,
                    "expanded_sql": "SELECT * FROM orders",
                    "is_valid": True,
                },
            ],
        }
        (units_dir / "sql_unit_2.json").write_text(json.dumps(sql_unit_2_data), encoding="utf-8")

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

    def test_run_executes_select_branch_against_db_and_collects_result_signature(self):
        """Test RecognitionStage uses DB baseline execution when connector is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_run_db_select"
            self._create_parse_file(Path(tmpdir), run_id)
            db_connector = FakeDBConnector()
            provider = DBBackedRecognitionProvider(db_connector)

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id, llm_provider=provider)
                output = stage.run()

                baseline = output.baselines[0]
                assert db_connector.explain_calls
                assert db_connector.query_calls
                assert db_connector.disconnected is True
                assert baseline.rows_returned == 2
                assert baseline.rows_examined == 2
                assert baseline.result_signature is not None
                assert baseline.result_signature["row_count"] == 2
                assert baseline.result_signature["sample_size"] == 2
                assert baseline.actual_time_ms is not None
                assert baseline.execution_error is None
            finally:
                os.chdir(original_cwd)

    def test_run_skips_query_execution_for_non_select_sql(self):
        """Test RecognitionStage only executes SELECT statements for baseline results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_run_db_update"
            parse_dir = Path(tmpdir) / "runs" / run_id / "parse"
            parse_dir.mkdir(parents=True, exist_ok=True)
            parse_file = parse_dir / "sql_units_with_branches.json"
            parse_data = ParseOutput(
                sql_units_with_branches=[
                    SQLUnitWithBranches(
                        sql_unit_id="sql_unit_update",
                        branches=[
                            SQLBranch(
                                path_id="path_update",
                                condition=None,
                                expanded_sql="UPDATE users SET status = 1 WHERE id = 1",
                                is_valid=True,
                            ),
                        ],
                    )
                ]
            )
            parse_file.write_text(parse_data.to_json(), encoding="utf-8")
            db_connector = FakeDBConnector()
            provider = DBBackedRecognitionProvider(db_connector)

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id, llm_provider=provider)
                output = stage.run()

                baseline = output.baselines[0]
                assert db_connector.explain_calls
                assert not db_connector.query_calls
                assert baseline.rows_returned is None
                assert baseline.result_signature is None
                assert baseline.execution_error is None
            finally:
                os.chdir(original_cwd)

    def test_run_keeps_plan_when_query_execution_fails(self):
        """Test RecognitionStage still writes baseline when real query execution fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_run_db_query_fail"
            self._create_parse_file(Path(tmpdir), run_id)
            db_connector = FakeDBConnector(query_error=RuntimeError("boom"))
            provider = DBBackedRecognitionProvider(db_connector)

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage(run_id=run_id, llm_provider=provider)
                output = stage.run()

                baseline = output.baselines[0]
                assert baseline.plan is not None
                assert baseline.estimated_cost == 42.0
                assert baseline.rows_returned is None
                assert baseline.result_signature is None
                assert baseline.execution_error == "query_execution_failed: boom"
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
                        original_sql="SELECT * FROM test",
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
                original_sql="SELECT * FROM test",
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

    def test_write_output_persists_extended_baseline_fields(self):
        """Test _write_output keeps result-signature fields in per-unit files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_write_extended"
            baseline = PerformanceBaseline(
                sql_unit_id="test_unit",
                path_id="test_path",
                original_sql="SELECT * FROM test",
                plan={"cost": 50.0},
                estimated_cost=50.0,
                actual_time_ms=25.0,
                rows_returned=3,
                rows_examined=20,
                result_signature={"row_count": 3, "checksum": "abc"},
                execution_error=None,
                branch_type="dynamic",
            )

            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage()
                stage._write_output(run_id, RecognitionOutput(baselines=[baseline]))  # noqa: SLF001

                unit_file = Path("runs") / run_id / "recognition" / "units" / "test_unit.json"
                unit_data = json.loads(unit_file.read_text(encoding="utf-8"))
                stored_baseline = unit_data["baselines"][0]
                assert stored_baseline["rows_returned"] == 3
                assert stored_baseline["rows_examined"] == 20
                assert stored_baseline["result_signature"]["checksum"] == "abc"
                assert stored_baseline["branch_type"] == "dynamic"
            finally:
                os.chdir(original_cwd)

    def test_write_output_persists_empty_baselines(self):
        """Test _write_output writes empty compatibility files for downstream stages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test_write_empty"
            original_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                stage = RecognitionStage()
                stats = stage._write_output(run_id, RecognitionOutput(baselines=[]))  # noqa: SLF001

                output_file = Path("runs") / run_id / "recognition" / "baselines.json"
                index_file = Path("runs") / run_id / "recognition" / "units" / "_index.json"
                assert output_file.exists()
                assert index_file.exists()
                assert RecognitionOutput.from_json(output_file.read_text(encoding="utf-8")).baselines == []
                assert json.loads(index_file.read_text(encoding="utf-8")) == []
                assert stats["unit_count"] == 0
            finally:
                os.chdir(original_cwd)


class TestPerformanceBaselineStructure:
    """Tests for PerformanceBaseline object structure."""

    def test_baseline_has_required_fields(self):
        """Test PerformanceBaseline has all required fields."""
        baseline = PerformanceBaseline(
            sql_unit_id="unit_1",
            path_id="path_1",
            original_sql="SELECT * FROM users WHERE id = 1",
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
            original_sql="SELECT * FROM users",
            plan={},
            estimated_cost=10.0,
        )

        assert baseline.actual_time_ms is None

    def test_baseline_to_json_and_from_json(self):
        """Test PerformanceBaseline serialization."""
        original = PerformanceBaseline(
            sql_unit_id="unit_test",
            path_id="path_test",
            original_sql="SELECT * FROM orders WHERE status = 'active'",
            plan={"Node Type": "Hash Join"},
            estimated_cost=75.0,
            actual_time_ms=30.0,
            rows_returned=12,
            rows_examined=1200,
            result_signature={"row_count": 12, "checksum": "sig"},
            execution_error=None,
        )

        json_str = original.to_json()
        restored = PerformanceBaseline.from_json(json_str)

        assert restored.sql_unit_id == original.sql_unit_id
        assert restored.path_id == original.path_id
        assert restored.plan == original.plan
        assert restored.estimated_cost == original.estimated_cost
        assert restored.actual_time_ms == original.actual_time_ms
        assert restored.rows_returned == original.rows_returned
        assert restored.rows_examined == original.rows_examined
        assert restored.result_signature == original.result_signature
        assert restored.execution_error == original.execution_error


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
                stage = RecognitionStage(run_id=run_id, llm_provider=mock_provider)
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
                            SQLBranch(path_id="p1", condition=None, expanded_sql="SELECT 1", is_valid=True),
                            SQLBranch(path_id="p2", condition=None, expanded_sql="SELECT 2", is_valid=True),
                        ],
                    ),
                    SQLUnitWithBranches(
                        sql_unit_id="unit_2",
                        branches=[
                            SQLBranch(path_id="p3", condition=None, expanded_sql="SELECT 3", is_valid=True),
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
                original_sql="SELECT * FROM a",
                plan={"cost": 10.0},
                estimated_cost=10.0,
            ),
            PerformanceBaseline(
                sql_unit_id="u2",
                path_id="p2",
                original_sql="SELECT * FROM b",
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
                        "original_sql": "SELECT * FROM test",
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


# Tests for hot value replacement

from sqlopt.contracts.init import FieldDistribution
from sqlopt.stages.recognition.stage import (
    _resolve_mybatis_params_for_explain,
    _lookup_hot_value,
    _format_hot_value,
)


def test_lookup_hot_value_found():
    """Test finding hot value for parameter."""
    fd = FieldDistribution(
        table_name="users",
        column_name="user_id",
        distinct_count=100,
        null_count=0,
        total_count=1000,
        top_values=[{"value": "42", "count": 500}],
    )
    field_dists = {"users": [fd]}

    result = _lookup_hot_value("user_id", "select * from users where user_id = #{user_id}", field_dists)
    assert result == "42"


def test_lookup_hot_value_not_found():
    """Test when no hot value available."""
    field_dists = {}

    result = _lookup_hot_value("user_id", "select * from users", field_dists)
    assert result is None


def test_lookup_hot_value_table_mismatch():
    """Test when table doesn't match SQL."""
    fd = FieldDistribution(
        table_name="orders",
        column_name="order_id",
        distinct_count=100,
        null_count=0,
        total_count=500,
        top_values=[{"value": "100", "count": 50}],
    )
    field_dists = {"orders": [fd]}

    result = _lookup_hot_value("order_id", "select * from users where user_id = #{user_id}", field_dists)
    assert result is None


def test_lookup_hot_value_snake_case():
    """Test parameter name with snake_case matching."""
    fd = FieldDistribution(
        table_name="users",
        column_name="user_id",
        distinct_count=100,
        null_count=0,
        total_count=1000,
        top_values=[{"value": "99", "count": 300}],
    )
    field_dists = {"users": [fd]}

    # camelCase param should match snake_case column
    result = _lookup_hot_value("userId", "select * from users where userId = #{userId}", field_dists)
    assert result == "99"


def test_format_hot_value_numeric():
    """Test numeric value formatting."""
    assert _format_hot_value("42", "INTEGER") == "42"
    assert _format_hot_value("123.45", "DECIMAL") == "123.45"
    assert _format_hot_value("1", "BIGINT") == "1"


def test_format_hot_value_string():
    """Test string value formatting."""
    assert _format_hot_value("admin", "VARCHAR") == "'admin'"
    assert _format_hot_value("test", None) == "'test'"
    assert _format_hot_value("active", "TEXT") == "'active'"


def test_format_hot_value_already_numeric():
    """Test value that's already numeric string."""
    assert _format_hot_value("42", "VARCHAR") == "42"
    assert _format_hot_value("-5", "VARCHAR") == "-5"
    assert _format_hot_value("3.14", "VARCHAR") == "3.14"


def test_resolve_mybatis_params_with_hot_value():
    """Test param replacement uses hot value."""
    fd = FieldDistribution(
        table_name="users",
        column_name="status",
        distinct_count=5,
        null_count=0,
        total_count=1000,
        top_values=[{"value": "active", "count": 800}],
    )
    field_dists = {"users": [fd]}

    sql = "SELECT * FROM users WHERE status = #{status}"
    result = _resolve_mybatis_params_for_explain(sql, None, field_dists)

    assert "= 'active'" in result
    assert "#{status}" not in result


def test_resolve_mybatis_params_without_hot_value():
    """Test fallback to static value when no hot value."""
    field_dists = {}

    sql = "SELECT * FROM users WHERE name = #{name}"
    result = _resolve_mybatis_params_for_explain(sql, None, field_dists)

    # Should use static sample value (from param name "name")
    assert "'test'" in result
    assert "#{name}" not in result


def test_resolve_mybatis_params_with_field_distributions_none():
    """Test when field_distributions is None."""
    sql = "SELECT * FROM users WHERE id = #{id}"
    result = _resolve_mybatis_params_for_explain(sql, None, None)

    # Should use static sample value
    assert "1" in result
    assert "#{id}" not in result
