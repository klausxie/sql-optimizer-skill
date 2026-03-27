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
from sqlopt.contracts.optimize import (
    ActionConflict,
    OptimizationAction,
    UnitActionSummary,
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


class TestOptimizationAction:
    """Tests for OptimizationAction serialization."""

    def test_to_dict(self) -> None:
        action = OptimizationAction(
            action_id="act_001",
            operation="REPLACE",
            xpath="/mapper/select/where/if[@test='name != null']",
            target_tag="if",
            original_snippet="<if test='name != null'>AND name = #{name}</if>",
            rewritten_snippet="<if test='name != null'>AND name LIKE #{name}</if>",
            sql_fragment="AND name = #{name}",
            rationale="Use LIKE for better pattern matching",
            confidence=0.85,
            path_id="path-1",
            issue_type="PREFIX_WILDCARD",
        )
        result = action.to_dict()
        assert result["action_id"] == "act_001"
        assert result["operation"] == "REPLACE"
        assert result["xpath"] == "/mapper/select/where/if[@test='name != null']"
        assert result["target_tag"] == "if"
        assert result["original_snippet"] == "<if test='name != null'>AND name = #{name}</if>"
        assert result["rewritten_snippet"] == "<if test='name != null'>AND name LIKE #{name}</if>"
        assert result["sql_fragment"] == "AND name = #{name}"
        assert result["rationale"] == "Use LIKE for better pattern matching"
        assert result["confidence"] == 0.85
        assert result["path_id"] == "path-1"
        assert result["issue_type"] == "PREFIX_WILDCARD"

    def test_from_dict(self) -> None:
        data = {
            "action_id": "act_002",
            "operation": "ADD",
            "xpath": "/mapper/select/where",
            "target_tag": "where",
            "original_snippet": None,
            "rewritten_snippet": "<where><if test='status != null'>status = #{status}</if></where>",
            "sql_fragment": None,
            "rationale": "Add where clause wrapper",
            "confidence": 0.9,
            "path_id": None,
            "issue_type": "MISSING_WHERE",
        }
        action = OptimizationAction.from_dict(data)
        assert action.action_id == "act_002"
        assert action.operation == "ADD"
        assert action.xpath == "/mapper/select/where"
        assert action.target_tag == "where"
        assert action.original_snippet is None
        assert action.rewritten_snippet == "<where><if test='status != null'>status = #{status}</if></where>"
        assert action.confidence == 0.9
        assert action.path_id is None

    def test_roundtrip(self) -> None:
        action = OptimizationAction(
            action_id="act_003",
            operation="REMOVE",
            xpath="/mapper/select/where/if[@test='1=1']",
            target_tag="if",
            original_snippet="<if test='1=1'>AND 1=1</if>",
            rewritten_snippet=None,
            sql_fragment="AND 1=1",
            rationale="Remove tautology",
            confidence=0.95,
            path_id="path-2",
            issue_type="TAUTOLOGY",
        )
        json_str = json.dumps(action.to_dict())
        restored = OptimizationAction.from_dict(json.loads(json_str))
        assert restored.action_id == action.action_id
        assert restored.operation == action.operation
        assert restored.xpath == action.xpath
        assert restored.target_tag == action.target_tag
        assert restored.original_snippet == action.original_snippet
        assert restored.rewritten_snippet == action.rewritten_snippet
        assert restored.sql_fragment == action.sql_fragment
        assert restored.rationale == action.rationale
        assert restored.confidence == action.confidence
        assert restored.path_id == action.path_id
        assert restored.issue_type == action.issue_type

    def test_operation_types(self) -> None:
        """Test all valid operation types: REPLACE, ADD, REMOVE, WRAP."""
        for op_type in ["REPLACE", "ADD", "REMOVE", "WRAP"]:
            action = OptimizationAction(
                action_id=f"act_{op_type}",
                operation=op_type,
                xpath="/mapper/select/where",
                target_tag="where",
            )
            assert action.operation == op_type


class TestActionConflict:
    """Tests for ActionConflict serialization."""

    def test_to_dict(self) -> None:
        action_a = OptimizationAction(
            action_id="act_a",
            operation="REPLACE",
            xpath="/mapper/select/where/if",
            target_tag="if",
            original_snippet="<if test='name'>AND name = #{name}</if>",
            rewritten_snippet="<if test='name'>AND name LIKE #{name}</if>",
        )
        action_b = OptimizationAction(
            action_id="act_b",
            operation="REMOVE",
            xpath="/mapper/select/where/if",
            target_tag="if",
            original_snippet="<if test='name'>AND name = #{name}</if>",
            rewritten_snippet=None,
        )
        conflict = ActionConflict(
            xpath="/mapper/select/where/if",
            action_a=action_a,
            action_b=action_b,
            conflict_type="overlap",
            resolution="a_wins",
            merged_action=None,
        )
        result = conflict.to_dict()
        assert result["xpath"] == "/mapper/select/where/if"
        assert result["action_a"]["action_id"] == "act_a"
        assert result["action_b"]["action_id"] == "act_b"
        assert result["conflict_type"] == "overlap"
        assert result["resolution"] == "a_wins"
        assert result["merged_action"] is None

    def test_from_dict(self) -> None:
        data = {
            "xpath": "/mapper/select/where",
            "action_a": {
                "action_id": "act_x",
                "operation": "ADD",
                "xpath": "/mapper/select/where",
                "target_tag": "where",
                "original_snippet": None,
                "rewritten_snippet": "<where></where>",
            },
            "action_b": {
                "action_id": "act_y",
                "operation": "WRAP",
                "xpath": "/mapper/select/where",
                "target_tag": "where",
                "original_snippet": "<where></where>",
                "rewritten_snippet": "<where><bind name='_' value='1'/></where>",
            },
            "conflict_type": "contradict",
            "resolution": "merged",
            "merged_action": {
                "action_id": "act_merged",
                "operation": "ADD",
                "xpath": "/mapper/select/where",
                "target_tag": "where",
                "original_snippet": None,
                "rewritten_snippet": "<where></where>",
            },
        }
        conflict = ActionConflict.from_dict(data)
        assert conflict.xpath == "/mapper/select/where"
        assert conflict.action_a.action_id == "act_x"
        assert conflict.action_b.action_id == "act_y"
        assert conflict.conflict_type == "contradict"
        assert conflict.resolution == "merged"
        assert conflict.merged_action is not None
        assert conflict.merged_action.action_id == "act_merged"

    def test_roundtrip(self) -> None:
        action_a = OptimizationAction(
            action_id="act_1",
            operation="REPLACE",
            xpath="/mapper/select/where/if",
            target_tag="if",
            original_snippet="<if test='x'>AND x = #{x}</if>",
            rewritten_snippet="<if test='x'>AND x LIKE #{x}</if>",
        )
        action_b = OptimizationAction(
            action_id="act_2",
            operation="REMOVE",
            xpath="/mapper/select/where/if",
            target_tag="if",
            original_snippet="<if test='x'>AND x = #{x}</if>",
            rewritten_snippet=None,
        )
        conflict = ActionConflict(
            xpath="/mapper/select/where/if",
            action_a=action_a,
            action_b=action_b,
            conflict_type="overlap",
            resolution="dropped",
            merged_action=None,
        )
        json_str = json.dumps(conflict.to_dict())
        restored = ActionConflict.from_dict(json.loads(json_str))
        assert restored.xpath == conflict.xpath
        assert restored.action_a.action_id == conflict.action_a.action_id
        assert restored.action_b.action_id == conflict.action_b.action_id
        assert restored.conflict_type == conflict.conflict_type
        assert restored.resolution == conflict.resolution
        assert restored.merged_action is None

    def test_conflict_types(self) -> None:
        """Test all valid conflict types: overlap, contradict, redundant."""
        action_a = OptimizationAction(
            action_id="act_a",
            operation="REPLACE",
            xpath="/mapper/select/where/if",
            target_tag="if",
            original_snippet="<if test='x'>AND x = #{x}</if>",
            rewritten_snippet="<if test='x'>AND x LIKE #{x}</if>",
        )
        action_b = OptimizationAction(
            action_id="act_b",
            operation="REMOVE",
            xpath="/mapper/select/where/if",
            target_tag="if",
            original_snippet="<if test='x'>AND x = #{x}</if>",
            rewritten_snippet=None,
        )
        for conflict_type in ["overlap", "contradict", "redundant"]:
            conflict = ActionConflict(
                xpath="/mapper/select/where/if",
                action_a=action_a,
                action_b=action_b,
                conflict_type=conflict_type,
                resolution="dropped",
            )
            assert conflict.conflict_type == conflict_type


class TestUnitActionSummary:
    """Tests for UnitActionSummary serialization."""

    def test_to_dict(self) -> None:
        action = OptimizationAction(
            action_id="act_001",
            operation="REPLACE",
            xpath="/mapper/select/where/if",
            target_tag="if",
            original_snippet="<if test='name'>AND name = #{name}</if>",
            rewritten_snippet="<if test='name'>AND name LIKE #{name}</if>",
            sql_fragment="AND name = #{name}",
            rationale="Use LIKE",
            confidence=0.85,
            path_id="path-1",
            issue_type="PREFIX_WILDCARD",
        )
        summary = UnitActionSummary(
            sql_unit_id="unit-1",
            unit_xpath="/mapper/UserMapper.xml/sql/selectUserById",
            actions=[action],
            conflicts=[],
            branch_coverage={"path-1": True, "path-2": False},
            overall_confidence=0.85,
        )
        result = summary.to_dict()
        assert result["sql_unit_id"] == "unit-1"
        assert result["unit_xpath"] == "/mapper/UserMapper.xml/sql/selectUserById"
        assert len(result["actions"]) == 1
        assert result["actions"][0]["action_id"] == "act_001"
        assert result["conflicts"] == []
        assert result["branch_coverage"] == {"path-1": True, "path-2": False}
        assert result["overall_confidence"] == 0.85

    def test_from_dict(self) -> None:
        data = {
            "sql_unit_id": "unit-2",
            "unit_xpath": "/mapper/OrderMapper.xml/sql/selectOrder",
            "actions": [
                {
                    "action_id": "act_010",
                    "operation": "ADD",
                    "xpath": "/mapper/select/where",
                    "target_tag": "where",
                    "original_snippet": None,
                    "rewritten_snippet": "<where></where>",
                    "sql_fragment": None,
                    "rationale": "Add where",
                    "confidence": 0.9,
                    "path_id": None,
                    "issue_type": "MISSING_WHERE",
                }
            ],
            "conflicts": [],
            "branch_coverage": {"path-1": True},
            "overall_confidence": 0.9,
        }
        summary = UnitActionSummary.from_dict(data)
        assert summary.sql_unit_id == "unit-2"
        assert summary.unit_xpath == "/mapper/OrderMapper.xml/sql/selectOrder"
        assert len(summary.actions) == 1
        assert summary.actions[0].action_id == "act_010"
        assert summary.branch_coverage == {"path-1": True}
        assert summary.overall_confidence == 0.9

    def test_roundtrip(self) -> None:
        action = OptimizationAction(
            action_id="act_100",
            operation="WRAP",
            xpath="/mapper/select/where",
            target_tag="where",
            original_snippet="<where></where>",
            rewritten_snippet="<where><if test='_Parameter != null'>1=1</if></where>",
            sql_fragment="",
            rationale="Prevent empty where",
            confidence=0.75,
            path_id="path-1",
            issue_type="EMPTY_WHERE",
        )
        action_b = OptimizationAction(
            action_id="act_101",
            operation="REPLACE",
            xpath="/mapper/select/where/if",
            target_tag="if",
            original_snippet="<if test='name'>AND name = #{name}</if>",
            rewritten_snippet="<if test='name'>AND name LIKE #{name}</if>",
            sql_fragment="AND name = #{name}",
            rationale="Better matching",
            confidence=0.8,
            path_id="path-2",
            issue_type="PREFIX_WILDCARD",
        )
        conflict = ActionConflict(
            xpath="/mapper/select/where/if",
            action_a=action,
            action_b=action_b,
            conflict_type="overlap",
            resolution="a_wins",
        )
        summary = UnitActionSummary(
            sql_unit_id="unit-3",
            unit_xpath="/mapper/ProductMapper.xml/sql/selectProduct",
            actions=[action, action_b],
            conflicts=[conflict],
            branch_coverage={"path-1": True, "path-2": True},
            overall_confidence=0.775,
        )
        json_str = json.dumps(summary.to_dict())
        restored = UnitActionSummary.from_dict(json.loads(json_str))
        assert restored.sql_unit_id == summary.sql_unit_id
        assert restored.unit_xpath == summary.unit_xpath
        assert len(restored.actions) == len(summary.actions)
        assert restored.actions[0].action_id == summary.actions[0].action_id
        assert len(restored.conflicts) == len(summary.conflicts)
        assert restored.conflicts[0].xpath == summary.conflicts[0].xpath
        assert restored.branch_coverage == summary.branch_coverage
        assert restored.overall_confidence == summary.overall_confidence

    def test_branch_coverage(self) -> None:
        """Test branch coverage dictionary handling."""
        summary = UnitActionSummary(
            sql_unit_id="unit-4",
            unit_xpath="/mapper/TestMapper.xml/sql/test",
            actions=[],
            conflicts=[],
            branch_coverage={"path-a": True, "path-b": False, "path-c": True},
            overall_confidence=0.0,
        )
        result = summary.to_dict()
        assert result["branch_coverage"]["path-a"] is True
        assert result["branch_coverage"]["path-b"] is False
        assert result["branch_coverage"]["path-c"] is True

    def test_empty_actions(self) -> None:
        """Test UnitActionSummary with empty actions and conflicts."""
        summary = UnitActionSummary(
            sql_unit_id="unit-5",
            unit_xpath="/mapper/EmptyMapper.xml/sql/empty",
            actions=[],
            conflicts=[],
            branch_coverage={},
            overall_confidence=0.0,
        )
        result = summary.to_dict()
        assert result["actions"] == []
        assert result["conflicts"] == []
        assert result["branch_coverage"] == {}
        assert result["overall_confidence"] == 0.0
