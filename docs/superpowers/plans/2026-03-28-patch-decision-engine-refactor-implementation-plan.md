# Patch Decision Engine 重构实施方案

## 1. 文件清单

### 1.1 新建文件 (14个)

```
python/sqlopt/stages/patch_decision/
├── __init__.py                      # 模块导出
├── constants.py                     # ReasonCode 枚举 + DeliveryTier 枚举
├── gates.py                         # 门控基类 Gate, GateResult, GateContext
├── context.py                       # 决策上下文 dataclass
├── engine.py                        # 引擎编排器
├── gate_locator.py                 # Gate 1: 定位器检查
├── gate_acceptance.py               # Gate 2: Acceptance 状态检查
├── gate_semantic.py                # Gate 3: 语义等价门检查
├── gate_candidate.py               # Gate 4: 候选唯一性检查
├── gate_change.py                  # Gate 5: 有效变更检查
├── gate_template.py                 # Gate 6: 模板重复检查
├── gate_dynamic.py                 # Gate 7: 动态模板处理 (重点增强)
├── gate_placeholder.py             # Gate 8: 占位符语义检查
└── gate_build.py                   # Gate 9: 补丁构建
```

### 1.2 修改文件 (2个)

| 文件 | 修改内容 |
|------|----------|
| `patch_decision_engine.py` | 改为 Wrapper，调用新模块 |
| `patch_decision/__init__.py` | 导出所有公共接口 |

---

## 2. 任务分解与依赖关系

### 阶段 1: 基础设施 (可并行)

| 任务 | 文件 | 依赖 | 预估行数 |
|------|------|------|----------|
| T1.1 | `constants.py` | 无 | ~80行 |
| T1.2 | `gates.py` | T1.1 | ~60行 |
| T1.3 | `context.py` | T1.2 | ~30行 |

### 阶段 2: 门控实现 (可并行)

| 任务 | 文件 | 依赖 | 预估行数 | 对应原逻辑 |
|------|------|------|----------|------------|
| T2.1 | `gate_locator.py` | T1.3 | ~25行 | L124-134 |
| T2.2 | `gate_acceptance.py` | T1.3 | ~45行 | L136-174 |
| T2.3 | `gate_semantic.py` | T1.3 | ~30行 | L176-199 |
| T2.4 | `gate_candidate.py` | T1.3 | ~25行 | L201-211 |
| T2.5 | `gate_change.py` | T1.3 | ~20行 | L232-242 |
| T2.6 | `gate_template.py` | T1.3 | ~30行 | L244-271 |
| T2.7 | `gate_placeholder.py` | T1.3 | ~20行 | L327-337 |
| T2.8 | `gate_build.py` | T1.3 | ~30行 | L339-365 |

### 阶段 3: 动态模板增强 (关键)

| 任务 | 文件 | 依赖 | 预估行数 | 对应原逻辑 |
|------|------|------|----------|------------|
| T3.1 | `gate_dynamic.py` | T2.6 | ~150行 | L293-325 (扩展) |

**T3.1 关键改动**: 原逻辑只返回 BLOCKED，新逻辑需要:
1. 检查动态模板类型是否支持
2. 尝试调用 `build_template_plan_patch()` 生成模板补丁
3. 成功则返回补丁，失败才返回 BLOCKED

### 阶段 4: 引擎编排

| 任务 | 文件 | 依赖 | 预估行数 |
|------|------|------|----------|
| T4.1 | `engine.py` | T2.1-T3.1 | ~120行 |

### 阶段 5: 向后兼容

| 任务 | 文件 | 依赖 | 预估行数 |
|------|------|------|----------|
| T5.1 | `patch_decision_engine.py` (Wrapper) | T4.1 | ~50行 |
| T5.2 | `__init__.py` | T5.1 | ~20行 |

### 阶段 6: 测试

| 任务 | 文件 | 依赖 | 预估行数 |
|------|------|------|----------|
| T6.1 | `tests/test_patch_decision_gates.py` | T5.2 | ~200行 |
| T6.2 | `tests/test_patch_decision_engine.py` | T5.2 | ~150行 |

---

## 3. 任务依赖图

```
                    ┌──────────────┐
                    │   T1.1       │
                    │ constants.py │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ T1.2    │  │ T1.3    │  │         │
        │ gates.py│  │context.py│  │         │
        └────┬────┘  └────┬────┘  │         │
             │            │       │         │
             │     ┌──────┴───────┤         │
             ▼     ▼              ▼         ▼
        ┌─────────────────────────────────────────┐
        │  T2.1 - T2.8: 各个门控实现 (可并行)       │
        └────────────────────┬──────────────────┘
                             │
                             ▼
                    ┌──────────────┐
                    │   T3.1       │
                    │gate_dynamic  │ ← 关键增强
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   T4.1       │
                    │   engine.py │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ T5.1    │  │ T5.2    │  │  T6.1   │
        │ Wrapper │  │ __init__│  │ Tests   │
        └─────────┘  └─────────┘  └────┬────┘
                                      │
                                      ▼
                                 ┌────────┐
                                 │  T6.2  │
                                 │ Tests  │
                                 └────────┘
```

---

## 4. 关键代码示例

### 4.1 constants.py (T1.1)

```python
from enum import Enum

class GateResultStatus(Enum):
    PASS = "GATE_PASS"      # 门控通过
    SKIP = "GATE_SKIP"      # 跳过（阻断）
    BLOCK = "GATE_BLOCK"    # 阻止（严重错误）

class DeliveryTier(Enum):
    READY_TO_APPLY = "READY_TO_APPLY"
    BLOCKED = "BLOCKED"
    PATCHABLE_WITH_REWRITE = "PATCHABLE_WITH_REWRITE"
    MANUAL_REVIEW = "MANUAL_REVIEW"

class ReasonCode:
    # Locator
    PATCH_LOCATOR_AMBIGUOUS = "PATCH_LOCATOR_AMBIGUOUS"

    # Acceptance
    PATCH_CONFLICT_NO_CLEAR_WINNER = "PATCH_CONFLICT_NO_CLEAR_WINNER"

    # Semantic
    PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS = "PATCH_SEMANTIC_EQUIVALENCE_NOT_PASS"
    PATCH_SEMANTIC_CONFIDENCE_LOW = "PATCH_SEMANTIC_CONFIDENCE_LOW"

    # Change
    PATCH_NO_EFFECTIVE_CHANGE = "PATCH_NO_EFFECTIVE_CHANGE"

    # Template
    PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED = "PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED"

    # Dynamic (原有 + 新增)
    PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED"
    PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED"
    PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED"
    PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE = "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE"

    # Security
    PATCH_VALIDATION_BLOCKED_SECURITY = "PATCH_VALIDATION_BLOCKED_SECURITY"

    # Placeholder
    PATCH_PLACEHOLDER_MISMATCH = "PATCH_PLACEHOLDER_MISMATCH"

    @classmethod
    def all(cls) -> list[str]:
        return [v for k, v in cls.__dict__.items() if k.isupper() and isinstance(v, str)]
```

### 4.2 gates.py (T1.2)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from .constants import GateResultStatus

T = TypeVar('T')

@dataclass(frozen=True)
class GateContext:
    """所有门控共享的执行上下文"""
    sql_unit: dict[str, Any]
    acceptance: dict[str, Any]
    selection: Any           # PatchSelectionContext
    build: Any              # PatchBuildResult
    run_dir: Any
    acceptance_rows: list[dict[str, Any]]
    project_root: Any
    statement_key_fn: Any   # Callable[[str], str]
    config: dict[str, Any] | None = None

@dataclass
class GateResult(Generic[T]):
    """门控执行结果"""
    status: GateResultStatus
    reason_code: str | None = None
    reason_message: str | None = None
    data: T | None = None          # 门控产生的数据（如补丁）
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pass(self) -> bool:
        return self.status == GateResultStatus.PASS

    @property
    def is_skip(self) -> bool:
        return self.status == GateResultStatus.SKIP


class Gate(ABC, Generic[T]):
    """门控抽象基类"""

    def __init__(self, name: str, order: int):
        self.name = name
        self.order = order

    @abstractmethod
    def execute(self, ctx: GateContext) -> GateResult[T]:
        """执行门控检查"""
        pass

    def on_pass(self, ctx: GateContext, **data) -> GateResult[T]:
        """默认通过处理"""
        return GateResult(
            status=GateResultStatus.PASS,
            data=data if data else None,
        )

    def on_skip(self, reason_code: str, reason_message: str, **context) -> GateResult[T]:
        """默认跳过处理"""
        return GateResult(
            status=GateResultStatus.SKIP,
            reason_code=reason_code,
            reason_message=reason_message,
            context=context,
        )
```

### 4.3 gate_dynamic.py - 重点增强 (T3.1)

```python
import re
from .gates import Gate, GateContext, GateResult
from .constants import GateResultStatus, ReasonCode

# 已支持的动态模板类型
SUPPORTED_BLOCKING_REASONS = {
    "",
    "NO_TEMPLATE_PRESERVING_INTENT",
    "INCLUDE_DYNAMIC_SUBTREE",
    "DYNAMIC_FILTER_SUBTREE",
    "DYNAMIC_FILTER_NO_EFFECTIVE_DIFF",
}

SUPPORTED_SHAPE_FAMILIES = {
    "IF_GUARDED_FILTER_STATEMENT",
    "IF_GUARDED_COUNT_WRAPPER",
}

# 需人工审查的类型
REVIEW_REQUIRED_BLOCKING_REASONS = {
    "FOREACH_COLLECTION_PREDICATE",
    "FOREACH_INCLUDE_PREDICATE",
    "DYNAMIC_SET_CLAUSE",
}

_TEMPLATe_TAG_PATTERN = re.compile(r"</?(if|where|set|trim|foreach|choose|when|otherwise|bind|include)\b")


class DynamicTemplateGate(Gate[dict]):
    """Gate 7: 动态模板处理 - 完整支持模板级补丁生成"""

    def __init__(
        self,
        build_template_fn,           # build_template_plan_patch
        format_template_ops_fn,       # format_template_ops_for_patch
        detect_duplicate_fn,          # detect_duplicate_clause_in_template_ops
    ):
        super().__init__("DynamicTemplate", order=7)
        self._build_template = build_template_fn
        self._format_template_ops = format_template_ops_fn
        self._detect_duplicate = detect_duplicate_fn

    def execute(self, ctx: GateContext) -> GateResult[dict]:
        dynamic_features = ctx.sql_unit.get("dynamicFeatures") or []

        # 无动态特征，直接通过
        if not dynamic_features:
            return self.on_pass(ctx)

        # 尝试生成模板级补丁
        return self._try_template_patch(ctx, dynamic_features)

    def _try_template_patch(self, ctx: GateContext, dynamic_features: list) -> GateResult[dict]:
        """核心逻辑：尝试生成模板级补丁"""
        dynamic_template = ctx.selection.dynamic_template or {}
        blocking_reason = str(dynamic_template.get("blockingReason") or "").strip().upper()
        shape_family = str(dynamic_template.get("shapeFamily") or "").strip().upper()

        # Step 1: 检查是否支持
        is_supported, skip_code, skip_msg = self._check_support(
            blocking_reason, shape_family, dynamic_features
        )

        if not is_supported:
            return self.on_skip(skip_code, skip_msg, blocking_reason=blocking_reason)

        # Step 2: 格式化模板操作
        template_acceptance = self._format_template_ops(
            ctx.sql_unit, ctx.acceptance, ctx.run_dir
        )

        # Step 3: 检测重复子句
        duplicate_clause = self._detect_duplicate(template_acceptance)
        if duplicate_clause:
            return self.on_skip(
                ReasonCode.PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED,
                f"template rewrite contains duplicated {duplicate_clause} clause",
            )

        # Step 4: 尝试生成模板补丁
        patch_text, changed_lines, error = self._build_template(
            ctx.sql_unit, template_acceptance, ctx.run_dir
        )

        if error:
            return self.on_skip(
                error.get("code", "PATCH_TEMPLATE_BUILD_FAILED"),
                error.get("message", "template patch build failed"),
            )

        if patch_text:
            # 成功生成模板补丁！
            return GateResult(
                status=GateResultStatus.PASS,
                data={
                    "patch_text": patch_text,
                    "changed_lines": changed_lines,
                    "artifact_kind": self._detect_artifact_kind(patch_text),
                    "strategy": self._detect_strategy(dynamic_features, dynamic_template),
                },
                context={
                    "dynamic_template_processed": True,
                    "strategy": self._detect_strategy(dynamic_features, dynamic_template),
                }
            )

        # Step 5: 模板补丁生成失败，回退到静态分析
        return self._skip_for_unsupported(blocking_reason, shape_family)

    def _check_support(self, blocking_reason: str, shape_family: str, dynamic_features: list) -> tuple:
        """检查动态模板类型是否支持"""

        # 已支持
        if blocking_reason in SUPPORTED_BLOCKING_REASONS:
            return True, None, None
        if shape_family in SUPPORTED_SHAPE_FAMILIES:
            return True, None, None

        # 需人工审查
        if blocking_reason.startswith("FOREACH_") or shape_family == "FOREACH_IN_PREDICATE":
            return False, ReasonCode.PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED, \
                "dynamic foreach predicate requires template-aware rewrite"
        if blocking_reason == "DYNAMIC_SET_CLAUSE":
            return False, ReasonCode.PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED, \
                "dynamic set clause requires template-aware rewrite"

        # 默认不支持
        return False, ReasonCode.PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED, \
            "dynamic template type not supported for automatic patch generation"

    def _detect_artifact_kind(self, patch_text: str) -> str:
        if _TEMPLATe_TAG_PATTERN.search(patch_text):
            return "TEMPLATE"
        return "STATEMENT"

    def _detect_strategy(self, dynamic_features: list, dynamic_template: dict) -> str:
        """检测使用的策略类型"""
        blocking_reason = str(dynamic_template.get("blockingReason") or "").strip().upper()

        if "COUNT" in str(dynamic_features) or "WRAPPER" in blocking_reason:
            return "DYNAMIC_COUNT_WRAPPER_COLLAPSE"
        if "FILTER" in str(dynamic_features) or "FILTER" in blocking_reason:
            return "DYNAMIC_FILTER_WRAPPER_COLLAPSE"
        if "INCLUDE" in dynamic_features:
            return "STATIC_INCLUDE_WRAPPER_COLLAPSE"

        return "DYNAMIC_STATEMENT_TEMPLATE_EDIT"

    def _skip_for_unsupported(self, blocking_reason: str, shape_family: str) -> GateResult[dict]:
        """返回不支持的原因"""
        if blocking_reason.startswith("FOREACH_"):
            return self.on_skip(
                ReasonCode.PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED,
                "dynamic foreach predicate requires template-aware rewrite",
            )
        return self.on_skip(
            ReasonCode.PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED,
            "dynamic template type not supported",
        )
```

### 4.4 engine.py (T4.1)

```python
from dataclasses import dataclass, field
from typing import Any, Callable
from .gates import Gate, GateContext, GateResult
from .constants import GateResultStatus, DeliveryTier

@dataclass
class EngineConfig:
    stop_on_first_skip: bool = True
    enable_dynamic_template: bool = True


class PatchDecisionEngine:
    """决策引擎：编排所有门控按顺序执行"""

    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        self._gates: list[Gate] = []

    def register(self, gate: Gate) -> "PatchDecisionEngine":
        self._gates.append(gate)
        self._gates.sort(key=lambda g: g.order)
        return self

    def execute(self, ctx: GateContext) -> tuple[dict, Any]:
        results: list[GateResult] = []

        for gate in self._gates:
            result = gate.execute(ctx)
            results.append(result)

            if result.is_skip and self.config.stop_on_first_skip:
                return self._build_skip_result(result, ctx), ctx

        # 所有门控通过
        return self._build_success_result(results, ctx), ctx

    def _build_skip_result(self, result: GateResult, ctx: GateContext) -> dict:
        tier = self._map_tier(result.reason_code)
        return {
            "sqlKey": ctx.sql_unit.get("sqlKey"),
            "statementKey": ctx.sql_unit.get("statementKey"),
            "patchFiles": [],
            "diffSummary": {"skipped": True},
            "deliveryOutcome": {
                "tier": tier,
                "reasonCodes": [result.reason_code] if result.reason_code else [],
                "summary": result.reason_message or "",
            },
            "selectionReason": {
                "code": result.reason_code,
                "message": result.reason_message,
            },
            "selectionEvidence": {...},  # 从 ctx 提取
            "fallbackReasonCodes": [...],
            **result.context,
        }

    def _build_success_result(self, results: list[GateResult], ctx: GateContext) -> dict:
        # 从结果中提取补丁数据
        for r in reversed(results):
            if r.is_pass and r.data and "patch_text" in r.data:
                return self._build_patch_from_data(r.data, ctx)

        # 回退到默认语句级补丁
        return self._build_default_patch(ctx)

    def _map_tier(self, reason_code: str | None) -> str:
        if not reason_code:
            return DeliveryTier.BLOCKED.value
        if "SECURITY" in reason_code:
            return DeliveryTier.PATCHABLE_WITH_REWRITE.value
        if "REVIEW" in reason_code:
            return DeliveryTier.MANUAL_REVIEW.value
        return DeliveryTier.BLOCKED.value


# 工厂函数
def create_engine(
    build_template_fn, format_template_ops_fn, detect_duplicate_fn,
    normalize_sql_fn, format_sql_fn, build_unified_fn,
) -> PatchDecisionEngine:
    engine = PatchDecisionEngine()
    engine.register(LocatorGate())
    engine.register(AcceptanceGate())
    engine.register(SemanticGate())
    engine.register(CandidateGate())
    engine.register(ChangeGate(normalize_sql_fn))
    engine.register(TemplateGate(detect_duplicate_fn))
    engine.register(DynamicTemplateGate(build_template_fn, format_template_ops_fn, detect_duplicate_fn))
    engine.register(PlaceholderGate())
    engine.register(BuildGate(build_unified_fn, format_sql_fn))
    return engine
```

### 4.5 Wrapper (T5.1)

```python
# patch_decision_engine.py - 向后兼容 Wrapper
from .patch_decision.engine import create_engine, GateContext
from .patch_decision.context import PatchDecisionContext

def decide_patch_result(
    sql_unit, acceptance, selection, build, run_dir,
    acceptance_rows, project_root, statement_key_fn,
    skip_patch_result, finalize_generated_patch,
    format_sql_for_patch, normalize_sql_text,
    format_template_ops_for_patch, detect_duplicate_clause_in_template_ops,
    build_template_plan_patch, build_unified_patch,
):
    # 构建 GateContext
    ctx = GateContext(
        sql_unit=sql_unit,
        acceptance=acceptance,
        selection=selection,
        build=build,
        run_dir=run_dir,
        acceptance_rows=acceptance_rows,
        project_root=project_root,
        statement_key_fn=statement_key_fn,
    )

    # 创建引擎
    engine = create_engine(
        build_template_plan_patch,
        format_template_ops_for_patch,
        detect_duplicate_clause_in_template_ops,
        normalize_sql_text,
        format_sql_for_patch,
        build_unified_patch,
    )

    # 执行
    patch, _ = engine.execute(ctx)

    # 构建决策上下文（保持兼容）
    decision_ctx = PatchDecisionContext(
        status=acceptance.get("status"),
        semantic_gate_status=selection.semantic_gate_status,
        semantic_gate_confidence=selection.semantic_gate_confidence,
        sql_key=sql_unit.get("sqlKey"),
        statement_key=statement_key_fn(sql_unit.get("sqlKey")),
        same_statement=[r for r in acceptance_rows if statement_key_fn(r.get("sqlKey", "")) == statement_key_fn(sql_unit.get("sqlKey", ""))],
        pass_rows=[r for r in acceptance_rows if r.get("status") == "PASS"],
        candidates_evaluated=len(acceptance_rows) or 1,
    )

    return patch, decision_ctx
```

---

## 5. 验收标准

### 5.1 功能验收

- [ ] 所有现有 `test_patch_*.py` 测试通过
- [ ] 动态模板样例能生成真实补丁（不再全部返回 BLOCKED）
- [ ] patch_results.jsonl 输出格式兼容

### 5.2 代码质量

- [ ] 新增模块行数符合预估（总计 ~800行）
- [ ] 每个门控可独立测试
- [ ] ReasonCode 集中管理

### 5.3 性能

- [ ] 门控顺序优化生效
- [ ] 无额外性能开销

---

## 6. 回滚计划

如遇严重问题，可回滚到原始实现：
1. 保留原 `patch_decision_engine.py` 作为备份
2. 暂时禁用新模块，通过环境变量切换
3. 逐步迁移，避免大规模一次性替换