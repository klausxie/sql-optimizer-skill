"""
Patch Decision Gates

门控基类和结果定义。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from .constants import GateResultStatus

T = TypeVar('T')


@dataclass
class GateContext:
    """
    门控执行上下文

    所有门控共享的执行数据，包括：
    - sql_unit: 扫描阶段输出的 SQL 单元
    - acceptance: validate 阶段的接受结果
    - selection: patch 选择上下文
    - build: patch 构建结果
    - run_dir: 运行目录
    - acceptance_rows: 所有接受结果行
    - project_root: 项目根目录
    - statement_key_fn: 从 sql_key 提取 statement_key 的函数
    - config: 配置字典
    - context: 门控间传递数据的共享字典
    """
    sql_unit: dict[str, Any]
    acceptance: dict[str, Any]
    selection: Any  # PatchSelectionContext
    build: Any  # PatchBuildResult
    run_dir: Any
    acceptance_rows: list[dict[str, Any]]
    project_root: Any
    statement_key_fn: Any = field(default=None)  # Callable[[str], str]
    config: dict[str, Any] | None = field(default=None)
    # 门控间传递数据的共享字典（使用 list 包装使其可变）
    _context_store: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        # 延迟初始化共享字典
        if not self._context_store:
            self._context_store.append({})

    @property
    def context(self) -> dict[str, Any]:
        """获取/设置门控间共享的上下文数据"""
        return self._context_store[0]

    @context.setter
    def context(self, value: dict[str, Any]):
        self._context_store[0] = value

    @property
    def sql_key(self) -> str:
        return self.sql_unit.get("sqlKey", "")

    @property
    def statement_key(self) -> str:
        if self.statement_key_fn:
            return self.statement_key_fn(self.sql_key)
        return self.sql_key.split("#")[0] if "#" in self.sql_key else self.sql_key


@dataclass
class GateResult(Generic[T]):
    """
    门控执行结果

    泛型 T 表示产生的数据类型，如 dict (补丁数据) 或 None。
    """
    status: GateResultStatus
    reason_code: str | None = None
    reason_message: str | None = None
    data: T | None = None  # 门控产生的数据（如补丁文本）
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pass(self) -> bool:
        return self.status == GateResultStatus.PASS

    @property
    def is_skip(self) -> bool:
        return self.status == GateResultStatus.SKIP

    @property
    def is_block(self) -> bool:
        return self.status == GateResultStatus.BLOCK


class Gate(ABC, Generic[T]):
    """
    门控抽象基类

    所有门控必须继承此类并实现 execute 方法。
    门控按照 order 顺序执行，数字越小越先执行。
    """

    def __init__(self, name: str, order: int):
        """
        初始化门控

        Args:
            name: 门控名称，用于日志和调试
            order: 执行顺序，数字越小越先执行
        """
        self.name = name
        self.order = order

    @abstractmethod
    def execute(self, ctx: GateContext) -> GateResult[T]:
        """
        执行门控检查

        Args:
            ctx: 门控执行上下文

        Returns:
            GateResult: 门控执行结果
        """
        pass

    def on_pass(self, ctx: GateContext, **data: Any) -> GateResult[T]:
        """
        默认通过处理

        Args:
            ctx: 门控执行上下文
            **data: 传递给结果的数据

        Returns:
            GateResult: 通过状态的结果
        """
        return GateResult(
            status=GateResultStatus.PASS,
            data=data if data else None,
        )

    def on_skip(
        self,
        reason_code: str,
        reason_message: str,
        **context: Any
    ) -> GateResult[T]:
        """
        默认跳过处理

        Args:
            reason_code: 原因码
            reason_message: 原因描述
            **context: 额外的上下文数据

        Returns:
            GateResult: 跳过状态的结果
        """
        return GateResult(
            status=GateResultStatus.SKIP,
            reason_code=reason_code,
            reason_message=reason_message,
            context=context,
        )

    def on_block(
        self,
        reason_code: str,
        reason_message: str,
        **context: Any
    ) -> GateResult[T]:
        """
        默认阻止处理

        Args:
            reason_code: 原因码
            reason_message: 原因描述
            **context: 额外的上下文数据

        Returns:
            GateResult: 阻止状态的结果
        """
        return GateResult(
            status=GateResultStatus.BLOCK,
            reason_code=reason_code,
            reason_message=reason_message,
            context=context,
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} order={self.order}>"


# 辅助函数：从 acceptance 中提取 reason_code
def extract_acceptance_reason_code(acceptance: dict[str, Any]) -> str | None:
    """从 acceptance 中提取 reason_code"""
    feedback = acceptance.get("feedback")
    if not isinstance(feedback, dict):
        return None
    code = str(feedback.get("reason_code") or "").strip().upper()
    return code or None


def extract_fallback_reason_codes(acceptance: dict[str, Any]) -> list[str]:
    """从 acceptance 中提取 fallback reason codes"""
    out: list[str] = []
    feedback_code = extract_acceptance_reason_code(acceptance)
    if feedback_code:
        out.append(feedback_code)

    perf = acceptance.get("perfComparison")
    perf_payload = perf if isinstance(perf, dict) else {}
    for code in perf_payload.get("reasonCodes") or []:
        normalized = str(code or "").strip().upper()
        if normalized and normalized not in out:
            out.append(normalized)

    return out


def build_selection_evidence(
    status: str,
    semantic_gate_status: str,
    semantic_gate_confidence: str,
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    """构建选择证据字典"""
    repairability = dict(acceptance.get("repairability") or {})
    return {
        "acceptanceStatus": status,
        "acceptanceReasonCode": extract_acceptance_reason_code(acceptance),
        "semanticGateStatus": semantic_gate_status,
        "semanticGateConfidence": semantic_gate_confidence,
        "repairabilityStatus": str(repairability.get("status") or "").strip().upper() or None,
        "rewriteSafetyLevel": str(acceptance.get("rewriteSafetyLevel") or "").strip().upper() or None,
    }