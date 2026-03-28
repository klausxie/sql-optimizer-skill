"""
测试 patch_decision 各门控
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from sqlopt.stages.patch_decision import (
    GateContext,
    GateResultStatus,
    ReasonCode,
)
from sqlopt.stages.patch_decision.gate_locator import LocatorGate
from sqlopt.stages.patch_decision.gate_acceptance import AcceptanceGate
from sqlopt.stages.patch_decision.gate_semantic import SemanticGate
from sqlopt.stages.patch_decision.gate_candidate import CandidateGate
from sqlopt.stages.patch_decision.gate_change import ChangeGate
from sqlopt.stages.patch_decision.gate_placeholder import PlaceholderGate


def make_mock_selection(
    semantic_gate_status="PASS",
    semantic_gate_confidence="HIGH",
    rewritten_sql="SELECT * FROM users",
    selected_candidate_id="candidate_1",
    dynamic_template=None,
    template_rewrite_ops=None,
):
    """创建模拟的 selection 对象"""
    selection = Mock()
    selection.semantic_gate_status = semantic_gate_status
    selection.semantic_gate_confidence = semantic_gate_confidence
    selection.rewritten_sql = rewritten_sql
    selection.selected_candidate_id = selected_candidate_id
    selection.dynamic_template = dynamic_template or {}
    selection.template_rewrite_ops = template_rewrite_ops or []
    selection.selected_patch_strategy = None
    selection.rewrite_materialization = None
    return selection


def make_mock_build(template_rewrite_ops=None):
    """创建模拟的 build 对象"""
    build = Mock()
    build.template_rewrite_ops = template_rewrite_ops or []
    build.artifact_kind = "STATEMENT"
    return build


def make_context(
    sql_unit=None,
    acceptance=None,
    selection=None,
    build=None,
    acceptance_rows=None,
):
    """创建模拟的 GateContext"""
    return GateContext(
        sql_unit=sql_unit or {"sqlKey": "test#v1", "locators": {"statementId": "test"}},
        acceptance=acceptance or {"status": "PASS"},
        selection=selection or make_mock_selection(),
        build=build or make_mock_build(),
        run_dir=Path("/tmp"),
        acceptance_rows=acceptance_rows or [],
        project_root=Path("/tmp"),
    )


class TestLocatorGate:
    """测试 LocatorGate"""

    def test_pass_with_locator(self):
        """有 locator 时通过"""
        gate = LocatorGate()
        ctx = make_context(
            sql_unit={"sqlKey": "test#v1", "locators": {"statementId": "test"}}
        )
        result = gate.execute(ctx)
        assert result.is_pass

    def test_skip_without_locator(self):
        """无 locator 时跳过"""
        gate = LocatorGate()
        ctx = make_context(
            sql_unit={"sqlKey": "test#v1", "locators": {}}
        )
        result = gate.execute(ctx)
        assert result.is_skip
        assert result.reason_code == ReasonCode.PATCH_LOCATOR_AMBIGUOUS


class TestAcceptanceGate:
    """测试 AcceptanceGate"""

    def test_pass_when_status_pass(self):
        """status=PASS 时通过"""
        gate = AcceptanceGate()
        ctx = make_context(
            acceptance={"status": "PASS"}
        )
        result = gate.execute(ctx)
        assert result.is_pass

    def test_skip_when_status_not_pass(self):
        """status!=PASS 时跳过"""
        gate = AcceptanceGate()
        ctx = make_context(
            acceptance={"status": "NEED_MORE_PARAMS", "feedback": {"reason_code": "VALIDATE_SEMANTIC_ERROR"}}
        )
        result = gate.execute(ctx)
        assert result.is_skip
        assert result.reason_code == ReasonCode.PATCH_CONFLICT_NO_CLEAR_WINNER

    def test_skip_security_blocked(self):
        """安全问题阻断"""
        gate = AcceptanceGate()
        ctx = make_context(
            acceptance={
                "status": "NEED_MORE_PARAMS",
                "feedback": {"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"}
            }
        )
        result = gate.execute(ctx)
        assert result.is_skip
        assert result.reason_code == ReasonCode.PATCH_VALIDATION_BLOCKED_SECURITY


class TestSemanticGate:
    """测试 SemanticGate"""

    def test_pass_when_semantic_gate_pass(self):
        """semantic_gate_status=PASS 时通过"""
        gate = SemanticGate()
        ctx = make_context(
            selection=make_mock_selection(semantic_gate_status="PASS")
        )
        result = gate.execute(ctx)
        assert result.is_pass

    def test_skip_when_semantic_gate_uncertain(self):
        """semantic_gate_status!=PASS 时跳过"""
        gate = SemanticGate()
        ctx = make_context(
            selection=make_mock_selection(semantic_gate_status="UNCERTAIN")
        )
        result = gate.execute(ctx)
        assert result.is_skip
        assert result.reason_code == ReasonCode.PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS

    def test_skip_when_confidence_low(self):
        """confidence=LOW 时跳过"""
        gate = SemanticGate()
        ctx = make_context(
            selection=make_mock_selection(semantic_gate_confidence="LOW")
        )
        result = gate.execute(ctx)
        assert result.is_skip
        assert result.reason_code == ReasonCode.PATCH_SEMANTIC_CONFIDENCE_LOW


class TestCandidateGate:
    """测试 CandidateGate"""

    def test_pass_single_pass_candidate(self):
        """恰好一个 PASS 候选时通过"""
        gate = CandidateGate()

        def statement_key_fn(key):
            return key.split("#")[0]

        ctx = make_context(
            acceptance_rows=[
                {"sqlKey": "test#v1", "status": "PASS"}
            ]
        )
        ctx.statement_key_fn = statement_key_fn

        result = gate.execute(ctx)
        assert result.is_pass

    def test_skip_multiple_pass_candidates(self):
        """多个 PASS 候选时跳过"""
        gate = CandidateGate()

        def statement_key_fn(key):
            return key.split("#")[0]

        ctx = make_context(
            acceptance_rows=[
                {"sqlKey": "test#v1", "status": "PASS"},
                {"sqlKey": "test#v2", "status": "PASS"}
            ]
        )
        ctx.statement_key_fn = statement_key_fn

        result = gate.execute(ctx)
        assert result.is_skip
        assert result.reason_code == ReasonCode.PATCH_CONFLICT_NO_CLEAR_WINNER


class TestChangeGate:
    """测试 ChangeGate"""

    def test_pass_with_change(self):
        """有变更时通过"""
        def normalize_fn(sql):
            return sql.strip().upper()

        gate = ChangeGate(normalize_fn)
        ctx = make_context(
            sql_unit={"sql": "SELECT * FROM users"},
            selection=make_mock_selection(rewritten_sql="SELECT id FROM users")
        )
        result = gate.execute(ctx)
        assert result.is_pass

    def test_skip_without_change(self):
        """无变更时跳过"""
        def normalize_fn(sql):
            return sql.strip().upper()

        gate = ChangeGate(normalize_fn)
        ctx = make_context(
            sql_unit={"sql": "SELECT * FROM users"},
            selection=make_mock_selection(rewritten_sql="select * from users"),
            build=make_mock_build()  # 无 dynamicFeatures
        )
        result = gate.execute(ctx)
        assert result.is_skip
        assert result.reason_code == ReasonCode.PATCH_NO_EFFECTIVE_CHANGE

    def test_pass_with_dynamic_features(self):
        """有动态特征时不检查变更"""
        def normalize_fn(sql):
            return sql.strip().upper()

        gate = ChangeGate(normalize_fn)
        ctx = make_context(
            sql_unit={"sql": "SELECT * FROM users", "dynamicFeatures": ["IF_PREDICATE"]},
            selection=make_mock_selection(rewritten_sql="SELECT * FROM users")
        )
        result = gate.execute(ctx)
        # 有 dynamicFeatures 时不检查变更，直接通过
        assert result.is_pass


class TestPlaceholderGate:
    """测试 PlaceholderGate"""

    def test_pass_normal(self):
        """正常情况通过"""
        gate = PlaceholderGate()
        ctx = make_context(
            sql_unit={"sql": "SELECT * FROM users WHERE id = #{id}"},
            selection=make_mock_selection(rewritten_sql="SELECT * FROM users WHERE id = #{id}")
        )
        result = gate.execute(ctx)
        assert result.is_pass

    def test_skip_placeholder_mismatch(self):
        """占位符不匹配时跳过"""
        gate = PlaceholderGate()
        ctx = make_context(
            sql_unit={"sql": "SELECT * FROM users WHERE id = #{id}"},
            selection=make_mock_selection(rewritten_sql="SELECT * FROM users WHERE id = ?")
        )
        result = gate.execute(ctx)
        assert result.is_skip
        assert result.reason_code == ReasonCode.PATCH_PLACEHOLDER_MISMATCH