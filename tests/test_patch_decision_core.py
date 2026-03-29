"""
测试 patch_decision 模块的核心功能
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from sqlopt.stages.patch_decision import (
    GateContext,
    Gate,
    GateResult,
    GateResultStatus,
    ReasonCode,
    DeliveryTier,
    extract_acceptance_reason_code,
    extract_fallback_reason_codes,
    build_selection_evidence,
    PatchDecisionContext,
    PatchDecisionEngine,
    EngineConfig,
)


class TestConstants:
    """测试常量定义"""

    def test_reason_code_all(self):
        """测试 ReasonCode.all() 返回所有原因码"""
        codes = ReasonCode.all()
        assert len(codes) >= 14
        assert "PATCH_LOCATOR_AMBIGUOUS" in codes
        assert "PATCH_CONFLICT_NO_CLEAR_WINNER" in codes

    def test_reason_code_map_to_tier(self):
        """测试 ReasonCode.map_to_tier() 映射"""
        # 安全问题应该映射到 PATCHABLE_WITH_REWRITE
        assert ReasonCode.map_to_tier("PATCH_VALIDATION_BLOCKED_SECURITY") == DeliveryTier.PATCHABLE_WITH_REWRITE.value
        # REVIEW 应该映射到 MANUAL_REVIEW
        assert ReasonCode.map_to_tier("PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED") == DeliveryTier.MANUAL_REVIEW.value
        # None 映射到 BLOCKED
        assert ReasonCode.map_to_tier(None) == DeliveryTier.BLOCKED.value
        # 未知原因码映射到 BLOCKED
        assert ReasonCode.map_to_tier("UNKNOWN") == DeliveryTier.BLOCKED.value


class TestGateContext:
    """测试 GateContext"""

    def test_create_basic(self):
        """测试基本创建"""
        ctx = GateContext(
            sql_unit={"sqlKey": "test#v1"},
            acceptance={"status": "PASS"},
            selection=Mock(),
            build=Mock(),
            run_dir=Path("/tmp"),
            acceptance_rows=[],
            project_root=Path("/tmp"),
        )
        assert ctx.sql_key == "test#v1"
        assert ctx.context == {}

    def test_context_mutable(self):
        """测试 context 可变性"""
        ctx = GateContext(
            sql_unit={"sqlKey": "test#v1"},
            acceptance={"status": "PASS"},
            selection=Mock(),
            build=Mock(),
            run_dir=Path("/tmp"),
            acceptance_rows=[],
            project_root=Path("/tmp"),
        )
        # 设置 context
        ctx.context["patch_text"] = "test"
        ctx.context["changed_lines"] = 5
        assert ctx.context["patch_text"] == "test"
        assert ctx.context["changed_lines"] == 5

    def test_statement_key_with_fn(self):
        """测试 statement_key_fn"""
        def extract_key(sql_key: str) -> str:
            return sql_key.split("#")[0]

        ctx = GateContext(
            sql_unit={"sqlKey": "demo.user.findUsers#v1"},
            acceptance={"status": "PASS"},
            selection=Mock(),
            build=Mock(),
            run_dir=Path("/tmp"),
            acceptance_rows=[],
            project_root=Path("/tmp"),
            statement_key_fn=extract_key,
        )
        assert ctx.statement_key == "demo.user.findUsers"


class TestGateResult:
    """测试 GateResult"""

    def test_is_pass(self):
        """测试 is_pass 属性"""
        result = GateResult(status=GateResultStatus.PASS)
        assert result.is_pass
        assert not result.is_skip
        assert not result.is_block

    def test_is_skip(self):
        """测试 is_skip 属性"""
        result = GateResult(
            status=GateResultStatus.SKIP,
            reason_code="PATCH_NO_EFFECTIVE_CHANGE",
            reason_message="no change"
        )
        assert result.is_skip
        assert not result.is_pass

    def test_data_preservation(self):
        """测试 data 保留"""
        data = {"patch_text": "SELECT * FROM users"}
        result = GateResult(
            status=GateResultStatus.PASS,
            data=data
        )
        assert result.data == data


class TestHelperFunctions:
    """测试辅助函数"""

    def test_extract_acceptance_reason_code(self):
        """测试提取 acceptance reason code"""
        # 有 feedback
        acceptance = {
            "feedback": {"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"}
        }
        assert extract_acceptance_reason_code(acceptance) == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"

        # 无 feedback
        assert extract_acceptance_reason_code({}) is None
        assert extract_acceptance_reason_code({"feedback": None}) is None

    def test_extract_fallback_reason_codes(self):
        """测试提取 fallback reason codes"""
        # 从 feedback 和 perfComparison 提取
        acceptance = {
            "feedback": {"reason_code": "VALIDATE_DB_UNREACHABLE"},
            "perfComparison": {"reasonCodes": ["VALIDATE_PLAN_COMPARE_CONFIG_DISABLED"]}
        }
        codes = extract_fallback_reason_codes(acceptance)
        assert "VALIDATE_DB_UNREACHABLE" in codes
        assert "VALIDATE_PLAN_COMPARE_CONFIG_DISABLED" in codes

    def test_build_selection_evidence(self):
        """测试构建选择证据"""
        acceptance = {
            "status": "PASS",
            "rewriteSafetyLevel": "SAFE"
        }
        evidence = build_selection_evidence(
            status="PASS",
            semantic_gate_status="PASS",
            semantic_gate_confidence="HIGH",
            acceptance=acceptance
        )
        assert evidence["acceptanceStatus"] == "PASS"
        assert evidence["semanticGateStatus"] == "PASS"
        assert evidence["semanticGateConfidence"] == "HIGH"
        assert evidence["rewriteSafetyLevel"] == "SAFE"


class TestPatchDecisionContext:
    """测试向后兼容的 PatchDecisionContext"""

    def test_create(self):
        """测试创建"""
        ctx = PatchDecisionContext(
            status="PASS",
            semantic_gate_status="PASS",
            semantic_gate_confidence="HIGH",
            sql_key="test#v1",
            statement_key="test",
            same_statement=[],
            pass_rows=[],
            candidates_evaluated=1
        )
        assert ctx.is_pass
        assert ctx.status == "PASS"

    def test_has_single_pass_candidate(self):
        """测试单候选检查"""
        # 单一 PASS 候选
        ctx = PatchDecisionContext(
            status="PASS",
            semantic_gate_status="PASS",
            semantic_gate_confidence="HIGH",
            sql_key="test#v1",
            statement_key="test",
            same_statement=[{"sqlKey": "test#v1", "status": "PASS"}],
            pass_rows=[{"sqlKey": "test#v1", "status": "PASS"}],
            candidates_evaluated=1
        )
        assert ctx.has_single_pass_candidate

        # 多个 PASS 候选（但不是当前 sql_key）
        ctx2 = PatchDecisionContext(
            status="PASS",
            semantic_gate_status="PASS",
            semantic_gate_confidence="HIGH",
            sql_key="test#v1",
            statement_key="test",
            same_statement=[
                {"sqlKey": "test#v1", "status": "PASS"},
                {"sqlKey": "test#v2", "status": "PASS"}
            ],
            pass_rows=[{"sqlKey": "test#v2", "status": "PASS"}],  # 选中的是 test#v2，不是 test#v1
            candidates_evaluated=2
        )
        assert not ctx2.has_single_pass_candidate


class _RecorderGate(Gate[dict]):
    def __init__(self, name: str, order: int, callback):
        super().__init__(name=name, order=order)
        self._callback = callback

    def execute(self, ctx: GateContext) -> GateResult[dict]:
        return self._callback(ctx)


class TestPatchDecisionEngine:
    def _ctx(self) -> GateContext:
        selection = Mock()
        selection.semantic_gate_status = "PASS"
        selection.semantic_gate_confidence = "HIGH"
        selection.selected_candidate_id = "c1"
        return GateContext(
            sql_unit={"sqlKey": "demo.user.find#v1"},
            acceptance={"status": "PASS"},
            selection=selection,
            build=Mock(),
            run_dir=Path("/tmp"),
            acceptance_rows=[{"sqlKey": "demo.user.find#v1", "status": "PASS"}],
            project_root=Path("/tmp"),
            statement_key_fn=lambda sql_key: sql_key.split("#")[0],
        )

    def test_engine_executes_gates_in_order_and_propagates_pass_data(self):
        call_order = []

        def later_gate(ctx: GateContext) -> GateResult[dict]:
            call_order.append(("later", ctx.context.get("token")))
            return GateResult(status=GateResultStatus.PASS)

        def earlier_gate(_ctx: GateContext) -> GateResult[dict]:
            call_order.append(("earlier", None))
            return GateResult(
                status=GateResultStatus.PASS,
                data={"token": "from-earlier"},
            )

        engine = PatchDecisionEngine()
        engine.register(_RecorderGate("later", 20, later_gate))
        engine.register(_RecorderGate("earlier", 10, earlier_gate))

        patch_result, decision_ctx = engine.execute(self._ctx())

        assert call_order == [("earlier", None), ("later", "from-earlier")]
        assert patch_result["status"] == "NEED_DEFAULT_BUILD"
        assert decision_ctx.candidates_evaluated == 1

    def test_engine_stops_on_first_skip_and_builds_skip_payload(self):
        call_order = []

        def first_gate(_ctx: GateContext) -> GateResult[dict]:
            call_order.append("first")
            return GateResult(
                status=GateResultStatus.SKIP,
                reason_code="PATCH_NO_EFFECTIVE_CHANGE",
                reason_message="no effective change",
                context={
                    "selection_evidence": {"acceptanceStatus": "PASS"},
                    "fallback_reason_codes": ["VALIDATE_DB_UNREACHABLE"],
                },
            )

        def never_gate(_ctx: GateContext) -> GateResult[dict]:
            call_order.append("never")
            return GateResult(status=GateResultStatus.PASS)

        engine = PatchDecisionEngine()
        engine.register(_RecorderGate("first", 10, first_gate))
        engine.register(_RecorderGate("never", 20, never_gate))

        patch_result, _decision_ctx = engine.execute(self._ctx())

        assert call_order == ["first"]
        assert patch_result["selectionReason"]["code"] == "PATCH_NO_EFFECTIVE_CHANGE"
        assert patch_result["selectionEvidence"] == {"acceptanceStatus": "PASS"}
        assert patch_result["fallbackReasonCodes"] == ["VALIDATE_DB_UNREACHABLE"]
        assert patch_result["deliveryOutcome"]["tier"] == DeliveryTier.BLOCKED.value

    def test_engine_can_continue_past_skip_when_config_allows_it(self):
        call_order = []

        def skip_gate(_ctx: GateContext) -> GateResult[dict]:
            call_order.append("skip")
            return GateResult(
                status=GateResultStatus.SKIP,
                reason_code="PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE",
                reason_message="needs template-aware rewrite",
            )

        def build_gate(ctx: GateContext) -> GateResult[dict]:
            call_order.append("build")
            return GateResult(
                status=GateResultStatus.PASS,
                data={
                    "patch_text": "@@ -1 +1 @@\n-SELECT *\n+SELECT id\n",
                    "changed_lines": 1,
                    "artifact_kind": "STATEMENT",
                    "patch_file": "/tmp/demo.patch",
                },
                context={"strategy": "EXACT_TEMPLATE_EDIT"},
            )

        engine = PatchDecisionEngine(config=EngineConfig(stop_on_first_skip=False))
        engine.register(_RecorderGate("skip", 10, skip_gate))
        engine.register(_RecorderGate("build", 20, build_gate))

        patch_result, _decision_ctx = engine.execute(self._ctx())

        assert call_order == ["skip", "build"]
        assert patch_result["strategyType"] == "EXACT_TEMPLATE_EDIT"
        assert patch_result["patchFiles"] == ["/tmp/demo.patch"]
