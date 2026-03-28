"""
Gate 1: Locator Gate

定位器检查门控，验证 SQL 单元是否具有有效的定位器。
"""

from .gates import Gate, GateContext, GateResult
from .constants import ReasonCode


class LocatorGate(Gate[None]):
    """
    Gate 1: 定位器检查

    验证 sql_unit 中是否有有效的 locators.statementId。
    如果缺失定位器，无法生成有效的补丁。
    """

    def __init__(self):
        super().__init__("Locator", order=1)

    def execute(self, ctx: GateContext) -> GateResult[None]:
        locators = ctx.sql_unit.get("locators") or {}

        if not locators.get("statementId"):
            return self.on_skip(
                ReasonCode.PATCH_LOCATOR_AMBIGUOUS,
                "missing locators.statementId in scan output",
                candidates_evaluated=len(ctx.acceptance_rows) or 1,
            )

        return self.on_pass(ctx)