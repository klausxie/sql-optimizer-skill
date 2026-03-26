"""Unit tests for ResultStage."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlopt.contracts.init import InitOutput, SQLUnit
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.contracts.result import Patch, Report, ResultOutput
from sqlopt.stages.result.stage import ResultStage


class TestResultStageRun:
    """Tests for ResultStage.run() method."""

    def test_run_with_valid_run_id_and_data(self):
        """Test ResultStage.run() with valid run_id and optimize/init data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-001"
            runs_dir = Path(tmpdir) / "runs" / run_id

            optimize_dir = runs_dir / "optimize"
            optimize_dir.mkdir(parents=True)
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id, name FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            optimize_output = OptimizeOutput(proposals=proposals)
            (optimize_dir / "proposals.json").write_text(
                optimize_output.to_json(), encoding="utf-8"
            )

            init_dir = runs_dir / "init"
            init_dir.mkdir(parents=True)
            sql_units = [
                SQLUnit(
                    id="sql-1",
                    mapper_file="UserMapper.xml",
                    sql_id="findUser",
                    sql_text="<select id='findUser'>SELECT * FROM users</select>",
                    statement_type="SELECT",
                ),
            ]
            init_output = InitOutput(sql_units=sql_units, run_id=run_id)
            (init_dir / "sql_units.json").write_text(init_output.to_json(), encoding="utf-8")

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert isinstance(result, ResultOutput)
                assert result.can_patch is True
                assert isinstance(result.report, Report)
                assert len(result.patches) == 1
            finally:
                os.chdir(original_cwd)

    def test_run_returns_stub_when_run_id_is_none(self):
        """Test ResultStage.run() returns stub when run_id is None."""
        stage = ResultStage(run_id=None)
        result = stage.run()

        assert isinstance(result, ResultOutput)
        assert result.can_patch is True
        assert isinstance(result.report, Report)
        assert len(result.patches) == 1
        assert result.patches[0].sql_unit_id == "stub-1"

    def test_run_returns_stub_when_optimize_file_missing(self):
        """Test ResultStage.run() returns stub when optimize file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-002"
            runs_dir = Path(tmpdir) / "runs" / run_id

            init_dir = runs_dir / "init"
            init_dir.mkdir(parents=True)
            sql_units = [
                SQLUnit(
                    id="sql-1",
                    mapper_file="UserMapper.xml",
                    sql_id="findUser",
                    sql_text="<select id='findUser'>SELECT * FROM users</select>",
                    statement_type="SELECT",
                ),
            ]
            init_output = InitOutput(sql_units=sql_units, run_id=run_id)
            (init_dir / "sql_units.json").write_text(init_output.to_json(), encoding="utf-8")

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert isinstance(result, ResultOutput)
                assert result.can_patch is True
                assert isinstance(result.report, Report)
                assert len(result.patches) == 1
            finally:
                os.chdir(original_cwd)

    def test_run_returns_stub_when_init_file_missing(self):
        """Test ResultStage.run() returns stub when init file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-003"
            runs_dir = Path(tmpdir) / "runs" / run_id

            optimize_dir = runs_dir / "optimize"
            optimize_dir.mkdir(parents=True)
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id, name FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            optimize_output = OptimizeOutput(proposals=proposals)
            (optimize_dir / "proposals.json").write_text(
                optimize_output.to_json(), encoding="utf-8"
            )

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert isinstance(result, ResultOutput)
                assert result.can_patch is True
                assert isinstance(result.report, Report)
                assert len(result.patches) == 1
            finally:
                os.chdir(original_cwd)

    def test_run_filters_proposals_by_confidence_threshold(self):
        """Test ResultStage.run() filters proposals by confidence > 0.7."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-004"
            runs_dir = Path(tmpdir) / "runs" / run_id

            optimize_dir = runs_dir / "optimize"
            optimize_dir.mkdir(parents=True)
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-high",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="High confidence",
                    confidence=0.95,
                ),
                OptimizationProposal(
                    sql_unit_id="sql-medium",
                    path_id="path-2",
                    original_sql="SELECT * FROM orders",
                    optimized_sql="SELECT id FROM orders",
                    rationale="Medium confidence",
                    confidence=0.75,
                ),
                OptimizationProposal(
                    sql_unit_id="sql-low",
                    path_id="path-3",
                    original_sql="SELECT * FROM products",
                    optimized_sql="SELECT id FROM products",
                    rationale="Low confidence",
                    confidence=0.5,
                ),
                OptimizationProposal(
                    sql_unit_id="sql-borderline",
                    path_id="path-4",
                    original_sql="SELECT * FROM items",
                    optimized_sql="SELECT id FROM items",
                    rationale="Borderline",
                    confidence=0.7,
                ),
            ]
            optimize_output = OptimizeOutput(proposals=proposals)
            (optimize_dir / "proposals.json").write_text(
                optimize_output.to_json(), encoding="utf-8"
            )

            init_dir = runs_dir / "init"
            init_dir.mkdir(parents=True)
            sql_units = [
                SQLUnit(
                    id="sql-high",
                    mapper_file="UserMapper.xml",
                    sql_id="findUser",
                    sql_text="<select id='findUser'>SELECT * FROM users</select>",
                    statement_type="SELECT",
                ),
                SQLUnit(
                    id="sql-medium",
                    mapper_file="OrderMapper.xml",
                    sql_id="findOrder",
                    sql_text="<select id='findOrder'>SELECT * FROM orders</select>",
                    statement_type="SELECT",
                ),
                SQLUnit(
                    id="sql-low",
                    mapper_file="ProductMapper.xml",
                    sql_id="findProduct",
                    sql_text="<select id='findProduct'>SELECT * FROM products</select>",
                    statement_type="SELECT",
                ),
                SQLUnit(
                    id="sql-borderline",
                    mapper_file="ItemMapper.xml",
                    sql_id="findItem",
                    sql_text="<select id='findItem'>SELECT * FROM items</select>",
                    statement_type="SELECT",
                ),
            ]
            init_output = InitOutput(sql_units=sql_units, run_id=run_id)
            (init_dir / "sql_units.json").write_text(init_output.to_json(), encoding="utf-8")

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert len(result.patches) == 2
                patch_ids = {p.sql_unit_id for p in result.patches}
                assert "sql-high" in patch_ids
                assert "sql-medium" in patch_ids
                assert "sql-low" not in patch_ids
                assert "sql-borderline" not in patch_ids
            finally:
                os.chdir(original_cwd)

    def test_run_with_no_matching_sql_units(self):
        """Test ResultStage.run() when proposals reference non-existent SQL units."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-005"
            runs_dir = Path(tmpdir) / "runs" / run_id

            optimize_dir = runs_dir / "optimize"
            optimize_dir.mkdir(parents=True)
            proposals = [
                OptimizationProposal(
                    sql_unit_id="non-existent-sql",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="High confidence",
                    confidence=0.85,
                ),
            ]
            optimize_output = OptimizeOutput(proposals=proposals)
            (optimize_dir / "proposals.json").write_text(
                optimize_output.to_json(), encoding="utf-8"
            )

            init_dir = runs_dir / "init"
            init_dir.mkdir(parents=True)
            sql_units = [
                SQLUnit(
                    id="sql-1",
                    mapper_file="UserMapper.xml",
                    sql_id="findUser",
                    sql_text="<select id='findUser'>SELECT * FROM users</select>",
                    statement_type="SELECT",
                ),
            ]
            init_output = InitOutput(sql_units=sql_units, run_id=run_id)
            (init_dir / "sql_units.json").write_text(init_output.to_json(), encoding="utf-8")

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert len(result.patches) == 0
                assert result.can_patch is False
            finally:
                os.chdir(original_cwd)

    def test_run_generates_patches_only_for_verified_proposals(self):
        """Test ResultStage only patches validated-equivalent proposals from new optimize output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-run-verified-only"
            runs_dir = Path(tmpdir) / "runs" / run_id

            optimize_dir = runs_dir / "optimize"
            optimize_dir.mkdir(parents=True)
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-verified",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Verified improvement",
                    confidence=0.9,
                    before_metrics={"actual_time_ms": 100.0},
                    after_metrics={"actual_time_ms": 20.0},
                    result_equivalent=True,
                    validation_status="validated",
                    gain_ratio=0.8,
                ),
                OptimizationProposal(
                    sql_unit_id="sql-estimated",
                    path_id="path-2",
                    original_sql="SELECT * FROM orders",
                    optimized_sql="SELECT id FROM orders",
                    rationale="Needs more validation",
                    confidence=0.95,
                    before_metrics={"estimated_cost": 80.0},
                    after_metrics={"estimated_cost": 30.0},
                    validation_status="estimated_only",
                    gain_ratio=0.625,
                ),
                OptimizationProposal(
                    sql_unit_id="sql-mismatch",
                    path_id="path-3",
                    original_sql="SELECT * FROM items",
                    optimized_sql="SELECT id FROM items",
                    rationale="Result mismatch",
                    confidence=0.99,
                    before_metrics={"actual_time_ms": 50.0},
                    after_metrics={"actual_time_ms": 10.0},
                    result_equivalent=False,
                    validation_status="result_mismatch",
                    gain_ratio=0.8,
                ),
            ]
            optimize_output = OptimizeOutput(proposals=proposals)
            (optimize_dir / "proposals.json").write_text(optimize_output.to_json(), encoding="utf-8")

            init_dir = runs_dir / "init"
            init_dir.mkdir(parents=True)
            sql_units = [
                SQLUnit(
                    id="sql-verified",
                    mapper_file="UserMapper.xml",
                    sql_id="findUser",
                    sql_text="<select id='findUser'>SELECT * FROM users</select>",
                    statement_type="SELECT",
                ),
                SQLUnit(
                    id="sql-estimated",
                    mapper_file="OrderMapper.xml",
                    sql_id="findOrder",
                    sql_text="<select id='findOrder'>SELECT * FROM orders</select>",
                    statement_type="SELECT",
                ),
                SQLUnit(
                    id="sql-mismatch",
                    mapper_file="ItemMapper.xml",
                    sql_id="findItem",
                    sql_text="<select id='findItem'>SELECT * FROM items</select>",
                    statement_type="SELECT",
                ),
            ]
            init_output = InitOutput(sql_units=sql_units, run_id=run_id)
            (init_dir / "sql_units.json").write_text(init_output.to_json(), encoding="utf-8")

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert len(result.patches) == 1
                assert result.patches[0].sql_unit_id == "sql-verified"
                assert result.can_patch is True
                assert "verified" in result.report.summary.lower()
            finally:
                os.chdir(original_cwd)


class TestCreatePatch:
    """Tests for ResultStage._create_patch() method."""

    def test_create_patch_generates_correct_unified_diff(self):
        """Test ResultStage._create_patch() generates correct unified diff."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_xml = "<select id='findUser'>SELECT * FROM users</select>"
            proposal = OptimizationProposal(
                sql_unit_id="sql-1",
                path_id="path-1",
                original_sql="SELECT * FROM users",
                optimized_sql="SELECT id, name FROM users",
                rationale="Remove wildcard",
                confidence=0.85,
            )

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()
                patch = stage._create_patch(proposal, original_xml)  # noqa: SLF001

                assert isinstance(patch, Patch)
                assert patch.sql_unit_id == "sql-1"
                assert patch.original_xml == original_xml
                assert patch.patched_xml == "SELECT id, name FROM users"

                assert "---" in patch.diff
                assert "+++" in patch.diff
                assert "original" in patch.diff
                assert "optimized" in patch.diff
            finally:
                os.chdir(original_cwd)

    def test_create_patch_with_identical_content(self):
        """Test ResultStage._create_patch() when original and optimized are identical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_xml = "<select id='findUser'>SELECT id FROM users</select>"
            proposal = OptimizationProposal(
                sql_unit_id="sql-1",
                path_id="path-1",
                original_sql="SELECT id FROM users",
                optimized_sql=original_xml,
                rationale="No change needed",
                confidence=0.85,
            )

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()
                patch = stage._create_patch(proposal, original_xml)  # noqa: SLF001

                assert isinstance(patch, Patch)
                assert patch.diff == ""
            finally:
                os.chdir(original_cwd)


class TestCreateReport:
    """Tests for ResultStage._create_report() method."""

    def test_create_report_generates_correct_structure(self):
        """Test ResultStage._create_report() generates correct report structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            high_confidence = proposals
            patches = [
                Patch(
                    sql_unit_id="sql-1",
                    original_xml="<select>SELECT *</select>",
                    patched_xml="<select>SELECT id</select>",
                    diff="--- old\n+++ new",
                ),
            ]

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()
                report = stage._create_report(proposals, high_confidence, patches)  # noqa: SLF001

                assert isinstance(report, Report)
                assert isinstance(report.summary, str)
                assert isinstance(report.details, str)
                assert isinstance(report.risks, list)
                assert isinstance(report.recommendations, list)
            finally:
                os.chdir(original_cwd)

    def test_create_report_has_summary(self):
        """Test report has summary field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            high_confidence = proposals
            patches = [
                Patch(
                    sql_unit_id="sql-1",
                    original_xml="<select>SELECT *</select>",
                    patched_xml="<select>SELECT id</select>",
                    diff="--- old\n+++ new",
                ),
            ]

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()
                report = stage._create_report(proposals, high_confidence, patches)  # noqa: SLF001

                assert report.summary is not None
                assert len(report.summary) > 0
                assert "1" in report.summary
            finally:
                os.chdir(original_cwd)

    def test_create_report_has_details(self):
        """Test report has details field with analysis info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            high_confidence = proposals
            patches = [
                Patch(
                    sql_unit_id="sql-1",
                    original_xml="<select>SELECT *</select>",
                    patched_xml="<select>SELECT id</select>",
                    diff="--- old\n+++ new",
                ),
            ]

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()
                report = stage._create_report(proposals, high_confidence, patches)  # noqa: SLF001

                assert "Total proposals analyzed: 1" in report.details
                assert "Verified optimizations" in report.details
                assert "Patches generated: 1" in report.details
            finally:
                os.chdir(original_cwd)

    def test_create_report_has_risks(self):
        """Test report has risks list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Remove wildcard",
                    confidence=0.75,
                    validation_status="estimated_only",
                ),
            ]
            high_confidence = proposals
            patches = [
                Patch(
                    sql_unit_id="sql-1",
                    original_xml="<select>SELECT *</select>",
                    patched_xml="<select>SELECT id</select>",
                    diff="--- old\n+++ new",
                ),
            ]

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()
                report = stage._create_report(proposals, high_confidence, patches)  # noqa: SLF001

                assert len(report.risks) > 0
                assert any("needs validation" in risk for risk in report.risks)
            finally:
                os.chdir(original_cwd)

    def test_create_report_has_recommendations(self):
        """Test report has recommendations list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            high_confidence = proposals
            patches = [
                Patch(
                    sql_unit_id="sql-1",
                    original_xml="<select>SELECT *</select>",
                    patched_xml="<select>SELECT id</select>",
                    diff="--- old\n+++ new",
                ),
            ]

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()
                report = stage._create_report(proposals, high_confidence, patches)  # noqa: SLF001

                assert len(report.recommendations) > 0
                assert any("Apply" in rec and "patch" in rec for rec in report.recommendations)
            finally:
                os.chdir(original_cwd)

    def test_create_report_no_high_confidence(self):
        """Test report when no high-confidence proposals found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proposals = []
            high_confidence = []
            patches: list[Patch] = []

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()
                report = stage._create_report(proposals, high_confidence, patches)  # noqa: SLF001

                assert "No verified optimizations found" in report.summary
                assert "Review SQL patterns manually" in report.recommendations[0]
            finally:
                os.chdir(original_cwd)


class TestCreateStubOutput:
    """Tests for ResultStage._create_stub_output() method."""

    def test_create_stub_output_structure(self):
        """Test _create_stub_output() returns correct structure."""
        stage = ResultStage()
        result = stage._create_stub_output()  # noqa: SLF001

        assert isinstance(result, ResultOutput)
        assert result.can_patch is True
        assert isinstance(result.report, Report)
        assert len(result.patches) == 1

    def test_create_stub_output_patch_fields(self):
        """Test stub patch has all required fields."""
        stage = ResultStage()
        result = stage._create_stub_output()  # noqa: SLF001
        patch = result.patches[0]

        assert patch.sql_unit_id == "stub-1"
        assert patch.original_xml
        assert patch.patched_xml
        assert patch.diff


class TestWriteOutput:
    """Tests for ResultStage._write_output() method."""

    def test_write_output_creates_report_file(self):
        """Test _write_output() creates report.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage()

                report = Report(
                    summary="Test summary",
                    details="Test details",
                    risks=["Test risk"],
                    recommendations=["Test recommendation"],
                )
                patch = Patch(
                    sql_unit_id="test-1",
                    original_xml="<test></test>",
                    patched_xml="<test></test>",
                    diff="",
                )
                output = ResultOutput(
                    can_patch=True,
                    report=report,
                    patches=[patch],
                )

                stage._write_output(output, "test-write-run")  # noqa: SLF001

                report_file = Path("runs/test-write-run/result/report.json")
                assert report_file.exists()

                data = json.loads(report_file.read_text(encoding="utf-8"))
                assert data["can_patch"] is True
                assert data["report"]["summary"] == "Test summary"
            finally:
                os.chdir(original_cwd)


class TestResultOutputFields:
    """Tests for ResultOutput field structure."""

    def test_result_output_has_can_patch(self):
        """Test ResultOutput has can_patch boolean field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-result-001"
            runs_dir = Path(tmpdir) / "runs" / run_id

            optimize_dir = runs_dir / "optimize"
            optimize_dir.mkdir(parents=True)
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            optimize_output = OptimizeOutput(proposals=proposals)
            (optimize_dir / "proposals.json").write_text(
                optimize_output.to_json(), encoding="utf-8"
            )

            init_dir = runs_dir / "init"
            init_dir.mkdir(parents=True)
            sql_units = [
                SQLUnit(
                    id="sql-1",
                    mapper_file="UserMapper.xml",
                    sql_id="findUser",
                    sql_text="<select id='findUser'>SELECT * FROM users</select>",
                    statement_type="SELECT",
                ),
            ]
            init_output = InitOutput(sql_units=sql_units, run_id=run_id)
            (init_dir / "sql_units.json").write_text(init_output.to_json(), encoding="utf-8")

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert hasattr(result, "can_patch")
                assert isinstance(result.can_patch, bool)
                assert result.can_patch is True
            finally:
                os.chdir(original_cwd)

    def test_result_output_has_report(self):
        """Test ResultOutput has report field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-result-002"
            runs_dir = Path(tmpdir) / "runs" / run_id

            optimize_dir = runs_dir / "optimize"
            optimize_dir.mkdir(parents=True)
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            optimize_output = OptimizeOutput(proposals=proposals)
            (optimize_dir / "proposals.json").write_text(
                optimize_output.to_json(), encoding="utf-8"
            )

            init_dir = runs_dir / "init"
            init_dir.mkdir(parents=True)
            sql_units = [
                SQLUnit(
                    id="sql-1",
                    mapper_file="UserMapper.xml",
                    sql_id="findUser",
                    sql_text="<select id='findUser'>SELECT * FROM users</select>",
                    statement_type="SELECT",
                ),
            ]
            init_output = InitOutput(sql_units=sql_units, run_id=run_id)
            (init_dir / "sql_units.json").write_text(init_output.to_json(), encoding="utf-8")

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert hasattr(result, "report")
                assert isinstance(result.report, Report)
            finally:
                os.chdir(original_cwd)

    def test_result_output_has_patches(self):
        """Test ResultOutput has patches list field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_id = "test-result-003"
            runs_dir = Path(tmpdir) / "runs" / run_id

            optimize_dir = runs_dir / "optimize"
            optimize_dir.mkdir(parents=True)
            proposals = [
                OptimizationProposal(
                    sql_unit_id="sql-1",
                    path_id="path-1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id FROM users",
                    rationale="Remove wildcard",
                    confidence=0.85,
                ),
            ]
            optimize_output = OptimizeOutput(proposals=proposals)
            (optimize_dir / "proposals.json").write_text(
                optimize_output.to_json(), encoding="utf-8"
            )

            init_dir = runs_dir / "init"
            init_dir.mkdir(parents=True)
            sql_units = [
                SQLUnit(
                    id="sql-1",
                    mapper_file="UserMapper.xml",
                    sql_id="findUser",
                    sql_text="<select id='findUser'>SELECT * FROM users</select>",
                    statement_type="SELECT",
                ),
            ]
            init_output = InitOutput(sql_units=sql_units, run_id=run_id)
            (init_dir / "sql_units.json").write_text(init_output.to_json(), encoding="utf-8")

            original_cwd = str(Path.cwd())
            try:
                os.chdir(tmpdir)
                stage = ResultStage(run_id=run_id)
                result = stage.run()

                assert hasattr(result, "patches")
                assert isinstance(result.patches, list)
                assert len(result.patches) == 1

                patch = result.patches[0]
                assert hasattr(patch, "sql_unit_id")
                assert hasattr(patch, "original_xml")
                assert hasattr(patch, "patched_xml")
                assert hasattr(patch, "diff")
            finally:
                os.chdir(original_cwd)
