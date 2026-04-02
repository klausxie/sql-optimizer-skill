"""Unit tests for parse stage HTML report generation via generate_parse_report()."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlopt.common.parse_stats import (
    PerUnitBranchStats,
    ParseStageStats,
    build_parse_stage_stats,
)
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.stages.parse.stage import ParseStage


class TestGenerateParseReport:
    """Tests for generate_parse_report() covering parse stage HTML output."""

    def test_generate_parse_report_with_branches(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test 1: ParseOutput with branches produces HTML containing branch path_id values."""
        # Build ParseOutput with 2 units × 2 branches
        units = [
            SQLUnitWithBranches(
                sql_unit_id="com.test.UserMapper.findById",
                theoretical_branches=2,
                branches=[
                    SQLBranch(
                        path_id="path-0",
                        condition="status != null",
                        expanded_sql="SELECT * FROM users WHERE status = #{status}",
                        is_valid=True,
                        risk_flags=["NO_INDEX"],
                        risk_level="HIGH",
                        risk_score=8.5,
                    ),
                    SQLBranch(
                        path_id="path-1",
                        condition="name != null",
                        expanded_sql="SELECT * FROM users WHERE name = #{name}",
                        is_valid=True,
                        risk_flags=[],
                        risk_level="LOW",
                        risk_score=2.0,
                    ),
                ],
            ),
            SQLUnitWithBranches(
                sql_unit_id="com.test.OrderMapper.findByStatus",
                theoretical_branches=2,
                branches=[
                    SQLBranch(
                        path_id="path-0",
                        condition="orderStatus > 0",
                        expanded_sql="SELECT * FROM orders WHERE orderStatus > 0",
                        is_valid=True,
                        risk_flags=["FULL_SCAN"],
                        risk_level="MEDIUM",
                        risk_score=5.0,
                    ),
                ],
            ),
        ]
        output = ParseOutput(
            sql_units_with_branches=units,
            run_id="test-report-001",
            strategy="ladder",
            max_branches=50,
        )

        # Create required init files so build_parse_stage_stats works
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "runs" / "test-report-001" / "init"
        run_dir.mkdir(parents=True)
        (run_dir / "sql_units.json").write_text(
            json.dumps(
                [
                    {
                        "id": "com.test.UserMapper.findById",
                        "mapper_file": "UserMapper.xml",
                        "sql_id": "findById",
                        "sql_text": "SELECT * FROM users",
                        "statement_type": "SELECT",
                    },
                    {
                        "id": "com.test.OrderMapper.findByStatus",
                        "mapper_file": "OrderMapper.xml",
                        "sql_id": "findByStatus",
                        "sql_text": "SELECT * FROM orders",
                        "statement_type": "SELECT",
                    },
                ]
            ),
            encoding="utf-8",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "SUMMARY.html")
            from sqlopt.common.stage_report_generator import generate_parse_report

            stats = build_parse_stage_stats(
                output=output,
                total_branches=3,
                failed_units=0,
                duration_seconds=0.1,
                run_id="test-report-001",
            )
            generate_parse_report(output, stats, output_path)

            html = open(output_path).read()
            assert "path-0" in html, "HTML should contain branch path_id values"
            assert "path-1" in html, "HTML should contain branch path_id values"
            assert "badge" in html, "HTML should contain risk badges"

    def test_generate_parse_report_with_parse_stats(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test 2: ParseStageStats produces HTML with normal/extreme stat card values."""
        # Setup parse output
        units = [
            SQLUnitWithBranches(
                sql_unit_id="com.test.UserMapper.findActive",
                theoretical_branches=4,
                branches=[
                    SQLBranch(
                        path_id=f"path-{i}",
                        condition=None,
                        expanded_sql=f"SELECT * FROM users WHERE active = {i}",
                        is_valid=True,
                        risk_level="LOW" if i < 2 else "HIGH",
                        risk_score=float(i),
                    )
                    for i in range(3)
                ],
            ),
        ]
        output = ParseOutput(
            sql_units_with_branches=units,
            run_id="test-stats-001",
            strategy="all_combinations",
            max_branches=50,
        )

        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "runs" / "test-stats-001" / "init"
        run_dir.mkdir(parents=True)
        (run_dir / "sql_units.json").write_text(
            json.dumps(
                [
                    {
                        "id": "com.test.UserMapper.findActive",
                        "mapper_file": "UserMapper.xml",
                        "sql_id": "findActive",
                        "sql_text": "SELECT * FROM users WHERE active = ?",
                        "statement_type": "SELECT",
                    },
                ]
            ),
            encoding="utf-8",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "SUMMARY.html")
            from sqlopt.common.stage_report_generator import generate_parse_report

            stats = build_parse_stage_stats(
                output=output,
                total_branches=3,
                failed_units=0,
                duration_seconds=0.1,
                run_id="test-stats-001",
            )
            # Call with ParseStageStats — should produce stat card values
            generate_parse_report(output, stats, output_path)

            html = open(output_path).read()
            # Should contain stat card labels
            assert "正常理论分支" in html, "HTML should contain normal theoretical branches label"
            assert "正常实际分支" in html, "HTML should contain normal actual branches label"
            assert "正常覆盖率" in html, "HTML should contain normal coverage label"

    def test_parse_stage_generates_report_with_branches(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test 3: ParseStage stub produces SUMMARY.html with branch rows in the table."""
        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "runs" / "parse-stage-report-test" / "init"
        run_dir.mkdir(parents=True)

        mapper = tmp_path / "src" / "main" / "resources" / "mapper" / "TestMapper.xml"
        mapper.parent.mkdir(parents=True)
        mapper.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.test.TestMapper">
    <select id="findByCondition">
        SELECT * FROM test
        <where>
            <if test="status != null">AND status = #{status}</if>
            <if test="type != null">AND type = #{type}</if>
        </where>
    </select>
</mapper>""",
            encoding="utf-8",
        )

        (run_dir / "sql_units.json").write_text(
            json.dumps(
                [
                    {
                        "id": "com.test.TestMapper.findByCondition",
                        "mapper_file": "TestMapper.xml",
                        "sql_id": "findByCondition",
                        "sql_text": 'SELECT * FROM test <where><if test="status != null">AND status = #{status}</if><if test="type != null">AND type = #{type}</if></where>',
                        "statement_type": "SELECT",
                    }
                ]
            ),
            encoding="utf-8",
        )

        from sqlopt.common.config import SQLOptConfig

        config = SQLOptConfig(parse_strategy="ladder", parse_max_branches=50)
        stage = ParseStage(run_id="parse-stage-report-test", config=config, use_mock=False)
        stage.run()

        # Read generated SUMMARY.html
        parse_dir = tmp_path / "runs" / "parse-stage-report-test" / "parse"
        summary_html = parse_dir / "SUMMARY.html"
        assert summary_html.exists(), "SUMMARY.html should be generated"

        html = summary_html.read_text(encoding="utf-8")
        # Branch table should have rows (tbody with tr elements)
        assert "<tr>" in html, "SUMMARY.html should contain table rows for branches"

    def test_report_contains_all_six_stat_cards(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test 4: HTML contains all 6 stat card label texts."""
        units = [
            SQLUnitWithBranches(
                sql_unit_id="com.test.DemoMapper.demo",
                theoretical_branches=2,
                branches=[
                    SQLBranch(
                        path_id="path-0",
                        condition="a != null",
                        expanded_sql="SELECT * FROM demo WHERE a = #{a}",
                        is_valid=True,
                        risk_level="HIGH",
                        risk_score=9.0,
                    ),
                    SQLBranch(
                        path_id="path-1",
                        condition="b != null",
                        expanded_sql="SELECT * FROM demo WHERE b = #{b}",
                        is_valid=True,
                        risk_level="LOW",
                        risk_score=1.0,
                    ),
                ],
            ),
        ]
        output = ParseOutput(
            sql_units_with_branches=units,
            run_id="test-cards-001",
            strategy="ladder",
            max_branches=50,
        )

        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "runs" / "test-cards-001" / "init"
        run_dir.mkdir(parents=True)
        (run_dir / "sql_units.json").write_text(
            json.dumps(
                [
                    {
                        "id": "com.test.DemoMapper.demo",
                        "mapper_file": "DemoMapper.xml",
                        "sql_id": "demo",
                        "sql_text": "SELECT * FROM demo",
                        "statement_type": "SELECT",
                    },
                ]
            ),
            encoding="utf-8",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "SUMMARY.html")
            from sqlopt.common.stage_report_generator import generate_parse_report

            stats = build_parse_stage_stats(
                output=output,
                total_branches=2,
                failed_units=0,
                duration_seconds=0.05,
                run_id="test-cards-001",
            )
            generate_parse_report(output, stats, output_path)

            html = open(output_path).read()
            # 6 stat card labels from the prototype
            assert "正常理论分支" in html, "Should have stat-card for normal theoretical branches"
            assert "正常实际分支" in html, "Should have stat-card for normal actual branches"
            assert "高风险" in html, "Should have stat-card for high risk"
            assert "中风险" in html, "Should have stat-card for medium risk"
            assert "低风险" in html, "Should have stat-card for low risk"
            assert "异常" in html, "Should have stat-card for outliers"

    def test_report_contains_risk_chart(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """Test 5: HTML contains drawDoughnut call with risk count data."""
        units = [
            SQLUnitWithBranches(
                sql_unit_id="com.test.ChartMapper.chart",
                theoretical_branches=3,
                branches=[
                    SQLBranch(
                        path_id=f"path-{i}",
                        condition=None,
                        expanded_sql=f"SELECT * FROM chart WHERE id = {i}",
                        is_valid=True,
                        risk_level="HIGH" if i == 0 else "MEDIUM" if i == 1 else "LOW",
                        risk_score=float(10 - i * 3),
                    )
                    for i in range(3)
                ],
            ),
        ]
        output = ParseOutput(
            sql_units_with_branches=units,
            run_id="test-chart-001",
            strategy="ladder",
            max_branches=50,
        )

        monkeypatch.chdir(tmp_path)
        run_dir = tmp_path / "runs" / "test-chart-001" / "init"
        run_dir.mkdir(parents=True)
        (run_dir / "sql_units.json").write_text(
            json.dumps(
                [
                    {
                        "id": "com.test.ChartMapper.chart",
                        "mapper_file": "ChartMapper.xml",
                        "sql_id": "chart",
                        "sql_text": "SELECT * FROM chart",
                        "statement_type": "SELECT",
                    },
                ]
            ),
            encoding="utf-8",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "SUMMARY.html")
            from sqlopt.common.stage_report_generator import generate_parse_report

            stats = build_parse_stage_stats(
                output=output,
                total_branches=3,
                failed_units=0,
                duration_seconds=0.05,
                run_id="test-chart-001",
            )
            generate_parse_report(output, stats, output_path)

            html = open(output_path).read()
            # Should have donut chart call with risk data
            assert "drawDoughnut" in html, "HTML should contain drawDoughnut chart call"
            # Should have risk level data in the chart call
            assert "HIGH" in html or "high" in html.lower(), "Chart should contain HIGH risk data"
