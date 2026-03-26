"""Unit tests for OptimizeStage."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.optimize.stage import OptimizeStage
from sqlopt.stages.recognition.stage import _build_result_signature


class FakeOptimizeDBConnector:
    """Simple DB connector for optimize-stage validation tests."""

    def __init__(
        self,
        explain_result: dict | None = None,
        query_rows: list[dict] | None = None,
        query_error: Exception | None = None,
    ) -> None:
        self.explain_result = explain_result or {
            "plan": {
                "Plan": {
                    "Node Type": "Index Scan",
                    "Total Cost": 15.0,
                    "Actual Total Time": 2.0,
                    "Actual Rows": 2,
                }
            },
            "estimated_cost": 15.0,
            "actual_time_ms": 2.0,
        }
        self.query_rows = query_rows or [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]
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
        return self.query_rows

    def disconnect(self) -> None:
        self.disconnected = True


class ValidatingOptimizeProvider:
    """Provider stub for optimize-stage validation tests."""

    def __init__(
        self,
        optimized_sql: str = "SELECT id, name FROM users WHERE id = 1",
        confidence: float = 0.92,
        db_connector: FakeOptimizeDBConnector | None = None,
        baseline_payload: dict | None = None,
    ) -> None:
        self.optimized_sql = optimized_sql
        self.confidence = confidence
        self.db_connector = db_connector
        self.baseline_payload = baseline_payload or {
            "plan": {"Plan": {"Total Cost": 20.0, "Actual Total Time": 4.0}},
            "estimated_cost": 20.0,
            "actual_time_ms": 4.0,
        }
        self.optimization_calls: list[str] = []
        self.baseline_calls: list[str] = []

    def generate_optimization(self, sql: str, description: str = "") -> str:
        self.optimization_calls.append(sql)
        return json.dumps(
            {
                "sql_unit_id": "unit-1",
                "path_id": "path-a",
                "optimized_sql": self.optimized_sql,
                "rationale": f"optimized:{description or 'default'}",
                "confidence": self.confidence,
            }
        )

    def generate_baseline(self, sql: str, platform: str = "postgresql") -> dict:
        self.baseline_calls.append(f"{platform}:{sql}")
        return self.baseline_payload


class TestOptimizeStageRun:
    """Tests for OptimizeStage.run() method."""

    def _create_run_structure(self, tmpdir: Path, run_id: str) -> Path:
        """Create the standard run directory structure."""
        run_path = tmpdir / "runs" / run_id
        recognition_dir = run_path / "recognition"
        parse_dir = run_path / "parse"
        recognition_dir.mkdir(parents=True, exist_ok=True)
        parse_dir.mkdir(parents=True, exist_ok=True)
        return run_path

    def _write_baselines_file(self, run_path: Path, baselines: list[PerformanceBaseline]) -> None:
        """Write baselines.json file."""
        recognition_dir = run_path / "recognition"
        baselines_file = recognition_dir / "baselines.json"
        output = RecognitionOutput(baselines=baselines)
        baselines_file.write_text(output.to_json(), encoding="utf-8")

    def _write_parse_file(self, run_path: Path, sql_units: list[SQLUnitWithBranches]) -> None:
        """Write sql_units_with_branches.json file."""
        parse_dir = run_path / "parse"
        parse_file = parse_dir / "sql_units_with_branches.json"
        output = ParseOutput(sql_units_with_branches=sql_units)
        parse_file.write_text(output.to_json(), encoding="utf-8")

    def test_run_with_valid_run_id_and_data_returns_proposals(self):
        """Test that run() returns proposals when valid run_id and data exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-001"
            run_path = self._create_run_structure(Path(tmpdir), run_id)

            baselines = [
                PerformanceBaseline(
                    sql_unit_id="unit-1",
                    path_id="path-a",
                    original_sql="SELECT * FROM users WHERE id = 1",
                    plan={},
                    estimated_cost=100.0,
                )
            ]
            self._write_baselines_file(run_path, baselines)

            sql_units = [
                SQLUnitWithBranches(
                    sql_unit_id="unit-1",
                    branches=[
                        SQLBranch(
                            path_id="path-a",
                            condition=None,
                            expanded_sql="SELECT * FROM users WHERE id = 1",
                            is_valid=True,
                        )
                    ],
                )
            ]
            self._write_parse_file(run_path, sql_units)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                result = stage.run()

                assert isinstance(result, OptimizeOutput)
                assert len(result.proposals) == 1
                proposal = result.proposals[0]
                assert proposal.sql_unit_id == "unit-1"
                assert proposal.path_id == "path-a"
                assert proposal.original_sql == "SELECT * FROM users WHERE id = 1"
                assert proposal.optimized_sql is not None
                assert proposal.rationale is not None
                assert 0.0 <= proposal.confidence <= 1.0
            finally:
                os.chdir(original_cwd)

    def test_run_returns_stub_when_run_id_is_none(self):
        """Test that run() returns stub output when run_id is None."""
        stage = OptimizeStage(run_id=None)
        result = stage.run()

        assert isinstance(result, OptimizeOutput)
        assert len(result.proposals) == 1
        proposal = result.proposals[0]
        assert proposal.sql_unit_id == "stub-1"
        assert proposal.optimized_sql == "SELECT id, name FROM users"
        assert proposal.rationale == "Reduce columns to improve performance"
        assert proposal.confidence == 0.9

    def test_run_returns_stub_when_baselines_file_missing(self):
        """Test that run() returns stub when baselines file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "nonexistent-run"
            run_path = Path(tmpdir) / "runs" / run_id
            run_path.mkdir(parents=True, exist_ok=True)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                result = stage.run()

                assert isinstance(result, OptimizeOutput)
                assert len(result.proposals) == 1
                assert result.proposals[0].sql_unit_id == "stub-1"
            finally:
                os.chdir(original_cwd)

    def test_run_looks_up_original_sql_from_parse_data(self):
        """Test that run() correctly looks up original SQL from parse data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-lookup"
            run_path = self._create_run_structure(Path(tmpdir), run_id)

            baselines = [
                PerformanceBaseline(
                    sql_unit_id="sql-1",
                    path_id="branch-1",
                    original_sql="SELECT id, name FROM customers",
                    plan={},
                    estimated_cost=50.0,
                ),
                PerformanceBaseline(
                    sql_unit_id="sql-2",
                    path_id="branch-1",
                    original_sql="SELECT * FROM orders WHERE status = 'active'",
                    plan={},
                    estimated_cost=75.0,
                ),
            ]
            self._write_baselines_file(run_path, baselines)

            sql_units = [
                SQLUnitWithBranches(
                    sql_unit_id="sql-1",
                    branches=[
                        SQLBranch(
                            path_id="branch-1",
                            condition=None,
                            expanded_sql="SELECT id, name FROM customers",
                            is_valid=True,
                        )
                    ],
                ),
                SQLUnitWithBranches(
                    sql_unit_id="sql-2",
                    branches=[
                        SQLBranch(
                            path_id="branch-1",
                            condition=None,
                            expanded_sql="SELECT * FROM orders WHERE status = 'active'",
                            is_valid=True,
                        )
                    ],
                ),
            ]
            self._write_parse_file(run_path, sql_units)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                result = stage.run()

                assert isinstance(result, OptimizeOutput)
                assert len(result.proposals) == 2

                assert result.proposals[0].original_sql == "SELECT id, name FROM customers"
                assert result.proposals[1].original_sql == "SELECT * FROM orders WHERE status = 'active'"
            finally:
                os.chdir(original_cwd)

    def test_run_creates_proposals_via_mock_llm(self):
        """Test that run() creates correct proposals via MockLLM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-mock"
            run_path = self._create_run_structure(Path(tmpdir), run_id)

            baselines = [
                PerformanceBaseline(
                    sql_unit_id="mock-unit",
                    path_id="mock-path",
                    original_sql="SELECT * FROM products",
                    plan={},
                    estimated_cost=100.0,
                )
            ]
            self._write_baselines_file(run_path, baselines)

            sql_units = [
                SQLUnitWithBranches(
                    sql_unit_id="mock-unit",
                    branches=[
                        SQLBranch(
                            path_id="mock-path",
                            condition=None,
                            expanded_sql="SELECT * FROM products",
                            is_valid=True,
                        )
                    ],
                )
            ]
            self._write_parse_file(run_path, sql_units)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                result = stage.run()

                proposal = result.proposals[0]
                assert proposal.original_sql == "SELECT * FROM products"
                assert proposal.optimized_sql.startswith("/*") or "optimized" in proposal.optimized_sql.lower()
                assert proposal.rationale is not None
                assert 0.0 <= proposal.confidence <= 1.0
            finally:
                os.chdir(original_cwd)

    def test_run_processes_all_baselines_with_original_sql(self):
        """Test that run() processes all baselines since they all have original_sql."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-all-baselines"
            run_path = self._create_run_structure(Path(tmpdir), run_id)

            baselines = [
                PerformanceBaseline(
                    sql_unit_id="unit-1",
                    path_id="path-1",
                    original_sql="SELECT a FROM table_a",
                    plan={},
                    estimated_cost=100.0,
                ),
                PerformanceBaseline(
                    sql_unit_id="unit-2",
                    path_id="path-2",
                    original_sql="SELECT b FROM table_b",
                    plan={},
                    estimated_cost=100.0,
                ),
            ]
            self._write_baselines_file(run_path, baselines)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                result = stage.run()

                # Both baselines get processed since they all have original_sql
                assert len(result.proposals) == 2
                assert result.proposals[0].sql_unit_id == "unit-1"
                assert result.proposals[1].sql_unit_id == "unit-2"
            finally:
                os.chdir(original_cwd)

    def test_run_handles_multiple_branches_per_unit(self):
        """Test that run() handles multiple branches per SQL unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-branches"
            run_path = self._create_run_structure(Path(tmpdir), run_id)

            baselines = [
                PerformanceBaseline(
                    sql_unit_id="unit-multi",
                    path_id="branch-a",
                    original_sql="SELECT * FROM items WHERE type = 'A'",
                    plan={},
                    estimated_cost=50.0,
                ),
                PerformanceBaseline(
                    sql_unit_id="unit-multi",
                    path_id="branch-b",
                    original_sql="SELECT * FROM items WHERE type = 'B'",
                    plan={},
                    estimated_cost=75.0,
                ),
            ]
            self._write_baselines_file(run_path, baselines)

            sql_units = [
                SQLUnitWithBranches(
                    sql_unit_id="unit-multi",
                    branches=[
                        SQLBranch(
                            path_id="branch-a",
                            condition="type = 'A'",
                            expanded_sql="SELECT * FROM items WHERE type = 'A'",
                            is_valid=True,
                        ),
                        SQLBranch(
                            path_id="branch-b",
                            condition="type = 'B'",
                            expanded_sql="SELECT * FROM items WHERE type = 'B'",
                            is_valid=True,
                        ),
                    ],
                )
            ]
            self._write_parse_file(run_path, sql_units)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                result = stage.run()

                assert len(result.proposals) == 2
                sqls = {p.original_sql for p in result.proposals}
                assert "SELECT * FROM items WHERE type = 'A'" in sqls
                assert "SELECT * FROM items WHERE type = 'B'" in sqls
            finally:
                os.chdir(original_cwd)

    def test_run_validates_optimized_sql_with_db_connector(self):
        """Test run() records before/after metrics when DB validation is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-db-validation"
            run_path = self._create_run_structure(Path(tmpdir), run_id)
            baseline_rows = [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]

            baselines = [
                PerformanceBaseline(
                    sql_unit_id="unit-1",
                    path_id="path-a",
                    original_sql="SELECT * FROM users WHERE id = 1",
                    plan={"Plan": {"Total Cost": 100.0, "Actual Total Time": 25.0, "Actual Rows": 2}},
                    estimated_cost=100.0,
                    actual_time_ms=25.0,
                    rows_returned=2,
                    rows_examined=20,
                    result_signature=_build_result_signature(baseline_rows),
                )
            ]
            self._write_baselines_file(run_path, baselines)

            db_connector = FakeOptimizeDBConnector(query_rows=baseline_rows)
            provider = ValidatingOptimizeProvider(db_connector=db_connector)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id, llm_provider=provider)
                result = stage.run()

                assert len(result.proposals) == 1
                proposal = result.proposals[0]
                assert proposal.before_metrics["estimated_cost"] == 100.0
                assert proposal.after_metrics["estimated_cost"] == 15.0
                assert proposal.validation_status == "validated"
                assert proposal.result_equivalent is True
                assert proposal.gain_ratio is not None
                assert db_connector.explain_calls
                assert db_connector.query_calls
                assert db_connector.disconnected is True
            finally:
                os.chdir(original_cwd)

    def test_run_marks_result_mismatch_when_signature_differs(self):
        """Test run() marks validation mismatch when optimized results differ."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-db-mismatch"
            run_path = self._create_run_structure(Path(tmpdir), run_id)
            baselines = [
                PerformanceBaseline(
                    sql_unit_id="unit-1",
                    path_id="path-a",
                    original_sql="SELECT * FROM users WHERE id = 1",
                    plan={"Plan": {"Total Cost": 80.0, "Actual Total Time": 10.0, "Actual Rows": 1}},
                    estimated_cost=80.0,
                    actual_time_ms=10.0,
                    rows_returned=1,
                    result_signature={"row_count": 1, "sample_size": 1, "columns": ["id"], "checksum": "same"},
                )
            ]
            self._write_baselines_file(run_path, baselines)

            db_connector = FakeOptimizeDBConnector(query_rows=[{"id": 99}])
            provider = ValidatingOptimizeProvider(db_connector=db_connector)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id, llm_provider=provider)
                result = stage.run()

                proposal = result.proposals[0]
                assert proposal.validation_status == "result_mismatch"
                assert proposal.result_equivalent is False
            finally:
                os.chdir(original_cwd)

    def test_run_uses_estimated_only_validation_without_db_connector(self):
        """Test run() still records after metrics when only provider baseline is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-estimated-only"
            run_path = self._create_run_structure(Path(tmpdir), run_id)
            baselines = [
                PerformanceBaseline(
                    sql_unit_id="unit-1",
                    path_id="path-a",
                    original_sql="SELECT * FROM users WHERE id = 1",
                    plan={"Plan": {"Total Cost": 60.0}},
                    estimated_cost=60.0,
                )
            ]
            self._write_baselines_file(run_path, baselines)
            provider = ValidatingOptimizeProvider()

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id, llm_provider=provider)
                result = stage.run()

                proposal = result.proposals[0]
                assert proposal.validation_status == "estimated_only"
                assert proposal.after_metrics["estimated_cost"] == 20.0
                assert proposal.result_equivalent is None
                assert provider.baseline_calls
            finally:
                os.chdir(original_cwd)


class TestOptimizeStageStub:
    """Tests for OptimizeStage._create_stub_output() method."""

    def test_create_stub_output_returns_optimize_output(self):
        """Test that _create_stub_output returns OptimizeOutput instance."""
        stage = OptimizeStage()
        result = stage._create_stub_output()  # noqa: SLF001

        assert isinstance(result, OptimizeOutput)

    def test_create_stub_output_has_one_proposal(self):
        """Test that stub output has exactly one proposal."""
        stage = OptimizeStage()
        result = stage._create_stub_output()  # noqa: SLF001

        assert len(result.proposals) == 1

    def test_create_stub_proposal_structure(self):
        """Test that stub proposal has correct structure."""
        stage = OptimizeStage()
        result = stage._create_stub_output()  # noqa: SLF001

        proposal = result.proposals[0]
        assert isinstance(proposal, OptimizationProposal)
        assert proposal.sql_unit_id == "stub-1"
        assert proposal.path_id == "p1"
        assert proposal.original_sql == "SELECT * FROM users"
        assert proposal.optimized_sql == "SELECT id, name FROM users"
        assert proposal.rationale == "Reduce columns to improve performance"
        assert proposal.confidence == 0.9


class TestOptimizeStageWriteOutput:
    """Tests for OptimizeStage._write_output() method."""

    def test_write_output_creates_json_file(self):
        """Test that _write_output() creates correct JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-write-output"
            output_dir = Path(tmpdir) / "runs" / run_id / "optimize"
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_dir / "proposals.json"

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                output = OptimizeOutput(
                    proposals=[
                        OptimizationProposal(
                            sql_unit_id="write-test",
                            path_id="path-x",
                            original_sql="SELECT 1",
                            optimized_sql="SELECT 1 LIMIT 1",
                            rationale="Add limit",
                            confidence=0.95,
                        )
                    ]
                )
                stage._write_output(run_id, output)  # noqa: SLF001

                assert output_file.exists()

                content = json.loads(output_file.read_text(encoding="utf-8"))
                assert "proposals" in content
                assert len(content["proposals"]) == 1
                assert content["proposals"][0]["sql_unit_id"] == "write-test"
                assert content["proposals"][0]["original_sql"] == "SELECT 1"
                assert content["proposals"][0]["optimized_sql"] == "SELECT 1 LIMIT 1"
            finally:
                os.chdir(original_cwd)

    def test_write_output_creates_directory_if_missing(self):
        """Test that _write_output() creates output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-write-new-dir"
            output_dir = Path(tmpdir) / "runs" / run_id / "optimize"

            assert not output_dir.exists()

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                output = OptimizeOutput(proposals=[])
                stage._write_output(run_id, output)  # noqa: SLF001

                assert output_dir.exists()
                assert (output_dir / "proposals.json").exists()
            finally:
                os.chdir(original_cwd)

    def test_write_output_multiple_proposals(self):
        """Test that _write_output() handles multiple proposals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-write-multi"
            output_dir = Path(tmpdir) / "runs" / run_id / "optimize"
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_dir / "proposals.json"

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                output = OptimizeOutput(
                    proposals=[
                        OptimizationProposal(
                            sql_unit_id="multi-1",
                            path_id="p1",
                            original_sql="SELECT 1",
                            optimized_sql="SELECT 1",
                            rationale="First",
                            confidence=0.8,
                        ),
                        OptimizationProposal(
                            sql_unit_id="multi-2",
                            path_id="p2",
                            original_sql="SELECT 2",
                            optimized_sql="SELECT 2",
                            rationale="Second",
                            confidence=0.85,
                        ),
                    ]
                )
                stage._write_output(run_id, output)  # noqa: SLF001

                content = json.loads(output_file.read_text(encoding="utf-8"))
                assert len(content["proposals"]) == 2
            finally:
                os.chdir(original_cwd)

    def test_write_output_persists_validation_fields(self):
        """Test that _write_output() keeps validation fields in JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-write-validation"
            output_dir = Path(tmpdir) / "runs" / run_id / "optimize"
            output_dir.mkdir(parents=True, exist_ok=True)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                stage = OptimizeStage(run_id=run_id)
                output = OptimizeOutput(
                    proposals=[
                        OptimizationProposal(
                            sql_unit_id="validate-1",
                            path_id="p1",
                            original_sql="SELECT * FROM t",
                            optimized_sql="SELECT id FROM t",
                            rationale="Reduce columns",
                            confidence=0.95,
                            before_metrics={"estimated_cost": 80.0},
                            after_metrics={"estimated_cost": 20.0},
                            result_equivalent=True,
                            validation_status="validated",
                            validation_error=None,
                            gain_ratio=0.75,
                        )
                    ]
                )
                stage._write_output(run_id, output)  # noqa: SLF001

                content = json.loads((output_dir / "proposals.json").read_text(encoding="utf-8"))
                proposal = content["proposals"][0]
                assert proposal["validation_status"] == "validated"
                assert proposal["result_equivalent"] is True
                assert proposal["gain_ratio"] == 0.75
            finally:
                os.chdir(original_cwd)


class TestOptimizationProposalStructure:
    """Tests for OptimizationProposal structure and serialization."""

    def test_proposal_to_json_and_back(self):
        """Test that OptimizationProposal serializes and deserializes correctly."""
        original = OptimizationProposal(
            sql_unit_id="test-proposal",
            path_id="test-path",
            original_sql="SELECT * FROM test",
            optimized_sql="SELECT id FROM test",
            rationale="Reduce columns",
            confidence=0.88,
            before_metrics={"estimated_cost": 100.0},
            after_metrics={"estimated_cost": 20.0},
            result_equivalent=True,
            validation_status="validated",
            validation_error=None,
            gain_ratio=0.8,
        )

        json_str = original.to_json()
        restored = OptimizationProposal.from_json(json_str)

        assert restored.sql_unit_id == original.sql_unit_id
        assert restored.path_id == original.path_id
        assert restored.original_sql == original.original_sql
        assert restored.optimized_sql == original.optimized_sql
        assert restored.rationale == original.rationale
        assert restored.confidence == original.confidence
        assert restored.before_metrics == original.before_metrics
        assert restored.after_metrics == original.after_metrics
        assert restored.result_equivalent == original.result_equivalent
        assert restored.validation_status == original.validation_status
        assert restored.gain_ratio == original.gain_ratio

    def test_proposal_confidence_range(self):
        """Test that confidence value is within valid range."""
        proposal = OptimizationProposal(
            sql_unit_id="c-range",
            path_id="c-path",
            original_sql="SELECT 1",
            optimized_sql="SELECT 1",
            rationale="Test",
            confidence=0.75,
        )
        assert 0.0 <= proposal.confidence <= 1.0


class TestOptimizeOutputStructure:
    """Tests for OptimizeOutput structure and serialization."""

    def test_optimize_output_to_json_and_back(self):
        """Test that OptimizeOutput serializes and deserializes correctly."""
        original = OptimizeOutput(
            proposals=[
                OptimizationProposal(
                    sql_unit_id="out-1",
                    path_id="op-1",
                    original_sql="SELECT a",
                    optimized_sql="SELECT a LIMIT 10",
                    rationale="Add limit",
                    confidence=0.9,
                ),
                OptimizationProposal(
                    sql_unit_id="out-2",
                    path_id="op-2",
                    original_sql="SELECT b",
                    optimized_sql="SELECT b",
                    rationale="No change",
                    confidence=0.5,
                ),
            ]
        )

        json_str = original.to_json()
        restored = OptimizeOutput.from_json(json_str)

        assert len(restored.proposals) == 2
        assert restored.proposals[0].sql_unit_id == "out-1"
        assert restored.proposals[1].sql_unit_id == "out-2"
