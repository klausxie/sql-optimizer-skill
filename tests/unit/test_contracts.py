"""Tests for sqlopt.contracts module - serialization and deserialization."""

from __future__ import annotations

import json

import pytest
from sqlopt.contracts import (
    InitOutput,
    OptimizationProposal,
    OptimizeOutput,
    ParseOutput,
    Patch,
    PerformanceBaseline,
    RecognitionOutput,
    Report,
    ResultOutput,
    SQLBranch,
    SQLUnit,
    SQLUnitWithBranches,
)


class TestSQLUnit:
    """Tests for SQLUnit serialization."""

    def test_to_json(self) -> None:
        unit = SQLUnit(
            id="unit-1",
            mapper_file="/path/to/mapper.xml",
            sql_id="selectById",
            sql_text="SELECT * FROM users WHERE id = ?",
            statement_type="SELECT",
        )
        result = unit.to_json()
        parsed = json.loads(result)
        assert parsed["id"] == "unit-1"
        assert parsed["mapper_file"] == "/path/to/mapper.xml"
        assert parsed["sql_id"] == "selectById"
        assert parsed["sql_text"] == "SELECT * FROM users WHERE id = ?"
        assert parsed["statement_type"] == "SELECT"

    def test_from_json(self) -> None:
        json_str = (
            '{"id":"unit-2","mapper_file":"/a.xml","sql_id":"find","sql_text":"SELECT 1","statement_type":"SELECT"}'
        )
        unit = SQLUnit.from_json(json_str)
        assert unit.id == "unit-2"
        assert unit.mapper_file == "/a.xml"
        assert unit.sql_id == "find"
        assert unit.statement_type == "SELECT"

    def test_roundtrip(self) -> None:
        unit = SQLUnit(
            id="unit-3",
            mapper_file="/b.xml",
            sql_id="insert",
            sql_text="INSERT INTO t VALUES (?)",
            statement_type="INSERT",
        )
        json_str = unit.to_json()
        restored = SQLUnit.from_json(json_str)
        assert restored.id == unit.id
        assert restored.mapper_file == unit.mapper_file
        assert restored.sql_id == unit.sql_id
        assert restored.sql_text == unit.sql_text
        assert restored.statement_type == unit.statement_type


class TestInitOutput:
    """Tests for InitOutput serialization."""

    def test_to_json(self) -> None:
        units = [
            SQLUnit(
                id="u1",
                mapper_file="/a.xml",
                sql_id="s1",
                sql_text="SELECT 1",
                statement_type="SELECT",
            ),
            SQLUnit(
                id="u2",
                mapper_file="/b.xml",
                sql_id="s2",
                sql_text="SELECT 2",
                statement_type="SELECT",
            ),
        ]
        output = InitOutput(sql_units=units, run_id="run-123")
        result = output.to_json()
        parsed = json.loads(result)
        assert len(parsed["sql_units"]) == 2
        assert parsed["run_id"] == "run-123"
        assert "timestamp" in parsed

    def test_from_json(self) -> None:
        json_str = '{"sql_units":[{"id":"u1","mapper_file":"/a.xml","sql_id":"s1","sql_text":"SELECT 1","statement_type":"SELECT"}],"run_id":"run-456"}'
        output = InitOutput.from_json(json_str)
        assert len(output.sql_units) == 1
        assert output.sql_units[0].id == "u1"
        assert output.run_id == "run-456"

    def test_roundtrip(self) -> None:
        units = [
            SQLUnit(
                id="u1",
                mapper_file="/a.xml",
                sql_id="s1",
                sql_text="SELECT 1",
                statement_type="SELECT",
            ),
        ]
        output = InitOutput(sql_units=units, run_id="run-789")
        json_str = output.to_json()
        restored = InitOutput.from_json(json_str)
        assert restored.run_id == output.run_id
        assert len(restored.sql_units) == len(output.sql_units)


class TestSQLBranch:
    """Tests for SQLBranch serialization."""

    def test_to_json_with_condition(self) -> None:
        branch = SQLBranch(
            path_id="path-1",
            condition="status = 'active'",
            expanded_sql="SELECT * FROM users WHERE status = 'active'",
            is_valid=True,
        )
        result = branch.to_json()
        parsed = json.loads(result)
        assert parsed["path_id"] == "path-1"
        assert parsed["condition"] == "status = 'active'"
        assert parsed["expanded_sql"] == "SELECT * FROM users WHERE status = 'active'"
        assert parsed["is_valid"] is True

    def test_to_json_without_condition(self) -> None:
        branch = SQLBranch(
            path_id="path-2",
            condition=None,
            expanded_sql="SELECT * FROM users",
            is_valid=True,
        )
        result = branch.to_json()
        parsed = json.loads(result)
        assert parsed["path_id"] == "path-2"
        assert parsed["condition"] is None

    def test_from_json(self) -> None:
        json_str = '{"path_id":"path-3","condition":"x > 0","expanded_sql":"SELECT 1","is_valid":false}'
        branch = SQLBranch.from_json(json_str)
        assert branch.path_id == "path-3"
        assert branch.condition == "x > 0"
        assert branch.is_valid is False

    def test_roundtrip(self) -> None:
        branch = SQLBranch(
            path_id="path-4",
            condition="y = 1",
            expanded_sql="SELECT * FROM t WHERE y = 1",
            is_valid=True,
            risk_score=4.5,
            score_reasons=["like_prefix"],
        )
        json_str = branch.to_json()
        restored = SQLBranch.from_json(json_str)
        assert restored.path_id == branch.path_id
        assert restored.condition == branch.condition
        assert restored.expanded_sql == branch.expanded_sql
        assert restored.is_valid == branch.is_valid
        assert restored.risk_score == 4.5
        assert restored.score_reasons == ["like_prefix"]


class TestSQLUnitWithBranches:
    """Tests for SQLUnitWithBranches serialization."""

    def test_to_json_empty_branches(self) -> None:
        unit = SQLUnitWithBranches(sql_unit_id="unit-1", branches=[])
        result = unit.to_json()
        parsed = json.loads(result)
        assert parsed["sql_unit_id"] == "unit-1"
        assert parsed["branches"] == []

    def test_to_json_with_branches(self) -> None:
        branch = SQLBranch(
            path_id="p1",
            condition=None,
            expanded_sql="SELECT 1",
            is_valid=True,
        )
        unit = SQLUnitWithBranches(sql_unit_id="unit-2", branches=[branch])
        result = unit.to_json()
        parsed = json.loads(result)
        assert parsed["sql_unit_id"] == "unit-2"
        assert len(parsed["branches"]) == 1

    def test_from_json(self) -> None:
        json_str = '{"sql_unit_id":"unit-3","branches":[{"path_id":"p1","condition":null,"expanded_sql":"SELECT 1","is_valid":true}]}'
        unit = SQLUnitWithBranches.from_json(json_str)
        assert unit.sql_unit_id == "unit-3"
        assert len(unit.branches) == 1
        assert unit.branches[0].path_id == "p1"

    def test_roundtrip(self) -> None:
        branches = [
            SQLBranch(path_id="p1", condition="a=1", expanded_sql="SQL1", is_valid=True),
            SQLBranch(path_id="p2", condition=None, expanded_sql="SQL2", is_valid=False),
        ]
        unit = SQLUnitWithBranches(sql_unit_id="unit-5", branches=branches)
        json_str = unit.to_json()
        restored = SQLUnitWithBranches.from_json(json_str)
        assert restored.sql_unit_id == unit.sql_unit_id
        assert len(restored.branches) == len(branches)


class TestParseOutput:
    """Tests for ParseOutput serialization."""

    def test_to_json_empty(self) -> None:
        output = ParseOutput(sql_units_with_branches=[])
        result = output.to_json()
        parsed = json.loads(result)
        assert parsed["sql_units_with_branches"] == []

    def test_to_json_with_units(self) -> None:
        branch = SQLBranch(path_id="p1", condition=None, expanded_sql="SQL", is_valid=True)
        unit = SQLUnitWithBranches(sql_unit_id="u1", branches=[branch])
        output = ParseOutput(sql_units_with_branches=[unit])
        result = output.to_json()
        parsed = json.loads(result)
        assert len(parsed["sql_units_with_branches"]) == 1

    def test_from_json(self) -> None:
        json_str = '{"sql_units_with_branches":[{"sql_unit_id":"u2","branches":[]}]}'
        output = ParseOutput.from_json(json_str)
        assert len(output.sql_units_with_branches) == 1
        assert output.sql_units_with_branches[0].sql_unit_id == "u2"

    def test_roundtrip(self) -> None:
        branches = [SQLBranch(path_id="p1", condition=None, expanded_sql="SQL", is_valid=True)]
        units = [SQLUnitWithBranches(sql_unit_id="u3", branches=branches)]
        output = ParseOutput(sql_units_with_branches=units)
        json_str = output.to_json()
        restored = ParseOutput.from_json(json_str)
        assert len(restored.sql_units_with_branches) == 1
        assert restored.sql_units_with_branches[0].sql_unit_id == "u3"


class TestPerformanceBaseline:
    """Tests for PerformanceBaseline serialization."""

    def test_to_json(self) -> None:
        baseline = PerformanceBaseline(
            sql_unit_id="u1",
            path_id="p1",
            original_sql="SELECT * FROM users",
            plan={"NodeType": "SeqScan", "RelationName": "users"},
            estimated_cost=100.5,
            actual_time_ms=50.0,
        )
        result = baseline.to_json()
        parsed = json.loads(result)
        assert parsed["sql_unit_id"] == "u1"
        assert parsed["path_id"] == "p1"
        assert parsed["plan"]["NodeType"] == "SeqScan"
        assert parsed["estimated_cost"] == 100.5
        assert parsed["actual_time_ms"] == 50.0

    def test_from_json(self) -> None:
        json_str = '{"sql_unit_id":"u2","path_id":"p2","original_sql":"SELECT * FROM orders","plan":{"NodeType":"IndexScan"},"estimated_cost":50.0,"actual_time_ms":null}'
        baseline = PerformanceBaseline.from_json(json_str)
        assert baseline.sql_unit_id == "u2"
        assert baseline.path_id == "p2"
        assert baseline.original_sql == "SELECT * FROM orders"
        assert baseline.plan["NodeType"] == "IndexScan"
        assert baseline.estimated_cost == 50.0
        assert baseline.actual_time_ms is None

    def test_roundtrip(self) -> None:
        baseline = PerformanceBaseline(
            sql_unit_id="u3",
            path_id="p3",
            original_sql="SELECT * FROM users WHERE status = 'active'",
            plan={"NodeType": "HashJoin"},
            estimated_cost=200.0,
            actual_time_ms=100.0,
        )
        json_str = baseline.to_json()
        restored = PerformanceBaseline.from_json(json_str)
        assert restored.sql_unit_id == baseline.sql_unit_id
        assert restored.path_id == baseline.path_id
        assert restored.plan == baseline.plan
        assert restored.estimated_cost == baseline.estimated_cost
        assert restored.actual_time_ms == baseline.actual_time_ms


class TestRecognitionOutput:
    """Tests for RecognitionOutput serialization."""

    def test_to_json_empty(self) -> None:
        output = RecognitionOutput(baselines=[])
        result = output.to_json()
        parsed = json.loads(result)
        assert parsed["baselines"] == []

    def test_to_json_with_baselines(self) -> None:
        baseline = PerformanceBaseline(
            sql_unit_id="u1",
            path_id="p1",
            original_sql="SELECT 1",
            plan={},
            estimated_cost=10.0,
        )
        output = RecognitionOutput(baselines=[baseline])
        result = output.to_json()
        parsed = json.loads(result)
        assert len(parsed["baselines"]) == 1

    def test_from_json(self) -> None:
        json_str = '{"baselines":[{"sql_unit_id":"u1","path_id":"p1","original_sql":"SELECT 1","plan":{},"estimated_cost":10.0}]}'
        output = RecognitionOutput.from_json(json_str)
        assert len(output.baselines) == 1
        assert output.baselines[0].sql_unit_id == "u1"

    def test_roundtrip(self) -> None:
        baselines = [
            PerformanceBaseline(
                sql_unit_id="u1",
                path_id="p1",
                original_sql="SELECT * FROM a",
                plan={"type": "seq"},
                estimated_cost=100.0,
            ),
            PerformanceBaseline(
                sql_unit_id="u2",
                path_id="p2",
                original_sql="SELECT * FROM b",
                plan={"type": "index"},
                estimated_cost=50.0,
            ),
        ]
        output = RecognitionOutput(baselines=baselines)
        json_str = output.to_json()
        restored = RecognitionOutput.from_json(json_str)
        assert len(restored.baselines) == 2
        assert restored.baselines[0].estimated_cost == 100.0


class TestOptimizationProposal:
    """Tests for OptimizationProposal serialization."""

    def test_to_json(self) -> None:
        proposal = OptimizationProposal(
            sql_unit_id="u1",
            path_id="p1",
            original_sql="SELECT * FROM users",
            optimized_sql="SELECT id, name FROM users",
            rationale="Remove unused columns",
            confidence=0.85,
        )
        result = proposal.to_json()
        parsed = json.loads(result)
        assert parsed["sql_unit_id"] == "u1"
        assert parsed["original_sql"] == "SELECT * FROM users"
        assert parsed["optimized_sql"] == "SELECT id, name FROM users"
        assert parsed["confidence"] == 0.85

    def test_from_json(self) -> None:
        json_str = '{"sql_unit_id":"u2","path_id":"p2","original_sql":"OLD","optimized_sql":"NEW","rationale":"Better","confidence":0.9}'
        proposal = OptimizationProposal.from_json(json_str)
        assert proposal.sql_unit_id == "u2"
        assert proposal.confidence == 0.9

    def test_roundtrip(self) -> None:
        proposal = OptimizationProposal(
            sql_unit_id="u3",
            path_id="p3",
            original_sql="SELECT a, b FROM t",
            optimized_sql="SELECT b FROM t",
            rationale="Drop column a",
            confidence=0.95,
        )
        json_str = proposal.to_json()
        restored = OptimizationProposal.from_json(json_str)
        assert restored.sql_unit_id == proposal.sql_unit_id
        assert restored.original_sql == proposal.original_sql
        assert restored.optimized_sql == proposal.optimized_sql
        assert restored.rationale == proposal.rationale
        assert restored.confidence == proposal.confidence


class TestOptimizeOutput:
    """Tests for OptimizeOutput serialization."""

    def test_to_json_empty(self) -> None:
        output = OptimizeOutput(proposals=[])
        result = output.to_json()
        parsed = json.loads(result)
        assert parsed["proposals"] == []

    def test_to_json_with_proposals(self) -> None:
        proposal = OptimizationProposal(
            sql_unit_id="u1",
            path_id="p1",
            original_sql="OLD",
            optimized_sql="NEW",
            rationale="X",
            confidence=0.8,
        )
        output = OptimizeOutput(proposals=[proposal])
        result = output.to_json()
        parsed = json.loads(result)
        assert len(parsed["proposals"]) == 1

    def test_from_json(self) -> None:
        json_str = '{"proposals":[{"sql_unit_id":"u1","path_id":"p1","original_sql":"O","optimized_sql":"N","rationale":"R","confidence":0.7}]}'
        output = OptimizeOutput.from_json(json_str)
        assert len(output.proposals) == 1
        assert output.proposals[0].sql_unit_id == "u1"

    def test_roundtrip(self) -> None:
        proposals = [
            OptimizationProposal(
                sql_unit_id="u1",
                path_id="p1",
                original_sql="O1",
                optimized_sql="N1",
                rationale="R1",
                confidence=0.8,
            ),
            OptimizationProposal(
                sql_unit_id="u2",
                path_id="p2",
                original_sql="O2",
                optimized_sql="N2",
                rationale="R2",
                confidence=0.9,
            ),
        ]
        output = OptimizeOutput(proposals=proposals)
        json_str = output.to_json()
        restored = OptimizeOutput.from_json(json_str)
        assert len(restored.proposals) == 2


class TestReport:
    """Tests for Report serialization."""

    def test_to_json(self) -> None:
        report = Report(
            summary="Optimization complete",
            details="Applied 3 optimizations",
            risks=["risk1", "risk2"],
            recommendations=["rec1", "rec2"],
        )
        result = report.to_json()
        parsed = json.loads(result)
        assert parsed["summary"] == "Optimization complete"
        assert parsed["details"] == "Applied 3 optimizations"
        assert parsed["risks"] == ["risk1", "risk2"]
        assert parsed["recommendations"] == ["rec1", "rec2"]

    def test_from_json(self) -> None:
        json_str = '{"summary":"Test","details":"Details","risks":["r1"],"recommendations":["c1"]}'
        report = Report.from_json(json_str)
        assert report.summary == "Test"
        assert report.risks == ["r1"]

    def test_roundtrip(self) -> None:
        report = Report(
            summary="Sum",
            details="Det",
            risks=["a", "b"],
            recommendations=["x", "y"],
        )
        json_str = report.to_json()
        restored = Report.from_json(json_str)
        assert restored.summary == report.summary
        assert restored.details == report.details
        assert restored.risks == report.risks
        assert restored.recommendations == report.recommendations


class TestPatch:
    """Tests for Patch serialization."""

    def test_to_json(self) -> None:
        patch = Patch(
            sql_unit_id="u1",
            original_xml="<old/>",
            patched_xml="<new/>",
            diff="@@ -1 +1 @@\n-<old/>\n+<new/>",
        )
        result = patch.to_json()
        parsed = json.loads(result)
        assert parsed["sql_unit_id"] == "u1"
        assert parsed["original_xml"] == "<old/>"
        assert parsed["patched_xml"] == "<new/>"
        assert "@@ -1 +1" in parsed["diff"]

    def test_from_json(self) -> None:
        json_str = '{"sql_unit_id":"u2","original_xml":"<a/>","patched_xml":"<b/>","diff":"---"}'
        patch = Patch.from_json(json_str)
        assert patch.sql_unit_id == "u2"
        assert patch.original_xml == "<a/>"

    def test_roundtrip(self) -> None:
        patch = Patch(
            sql_unit_id="u3",
            original_xml="<original>",
            patched_xml="<patched>",
            diff="@@",
        )
        json_str = patch.to_json()
        restored = Patch.from_json(json_str)
        assert restored.sql_unit_id == patch.sql_unit_id
        assert restored.original_xml == patch.original_xml
        assert restored.patched_xml == patch.patched_xml
        assert restored.diff == patch.diff


class TestResultOutput:
    """Tests for ResultOutput serialization."""

    def test_to_json(self) -> None:
        report = Report(
            summary="Sum",
            details="Det",
            risks=[],
            recommendations=[],
        )
        output = ResultOutput(can_patch=True, report=report, patches=[])
        result = output.to_json()
        parsed = json.loads(result)
        assert parsed["can_patch"] is True
        assert parsed["report"]["summary"] == "Sum"
        assert parsed["patches"] == []

    def test_to_json_with_patches(self) -> None:
        report = Report(summary="S", details="D", risks=[], recommendations=[])
        patch = Patch(
            sql_unit_id="u1",
            original_xml="<a>",
            patched_xml="<b>",
            diff="diff",
        )
        output = ResultOutput(can_patch=True, report=report, patches=[patch])
        result = output.to_json()
        parsed = json.loads(result)
        assert len(parsed["patches"]) == 1
        assert parsed["patches"][0]["sql_unit_id"] == "u1"

    def test_from_json(self) -> None:
        json_str = '{"can_patch":false,"report":{"summary":"Test","details":"Details","risks":[],"recommendations":[]},"patches":[]}'
        output = ResultOutput.from_json(json_str)
        assert output.can_patch is False
        assert output.report.summary == "Test"

    def test_roundtrip(self) -> None:
        report = Report(
            summary="Summary",
            details="Details",
            risks=["r1"],
            recommendations=["c1"],
        )
        patch = Patch(
            sql_unit_id="u1",
            original_xml="<old>",
            patched_xml="<new>",
            diff="@@",
        )
        output = ResultOutput(can_patch=True, report=report, patches=[patch])
        json_str = output.to_json()
        restored = ResultOutput.from_json(json_str)
        assert restored.can_patch == output.can_patch
        assert restored.report.summary == output.report.summary
        assert len(restored.patches) == 1
        assert restored.patches[0].sql_unit_id == "u1"
