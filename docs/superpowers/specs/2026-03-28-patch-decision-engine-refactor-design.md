# Patch Decision Engine 改进规范

## 1. 当前问题总结

### 1.1 代码组织问题

- **逻辑过于集中**: `patch_decision_engine.py` 共 367 行，所有决策逻辑堆在一起
- **扩展困难**: 新增门控需要修改单一文件，违反开闭原则
- **魔法字符串泛滥**: `"PATCH_*"`, `"DYNAMIC_*"` 等散落各处

### 1.2 功能缺陷

- **动态模板处理不完整**: 第 293-325 行只返回 BLOCKED 原因，未实际生成模板级补丁
- **门控顺序不够优化**: 静态 SQL 的 normalize 检查在模板重复检查之后

### 1.3 可测试性差

- 决策逻辑依赖大量外部函数，难以隔离测试
- if-else 链式判断，路径组合难以覆盖

---

## 2. 改进目标

### 2.1 架构目标

| 目标 | 指标 |
|------|------|
| 代码拆分 | 将 367 行拆分为 8-10 个独立门控模块 |
| 可测试性 | 每个门控方法可通过 mock 外部依赖独立测试 |
| 可扩展性 | 新增门控只需添加新模块，不修改现有逻辑 |
| 动态模板 | 完整支持模板级补丁生成，而非仅返回 BLOCKED |

### 2.2 功能目标

- 统一 reason_code 常量管理
- 优化门控检查顺序
- 补全动态模板处理逻辑

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    PatchDecisionEngine                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Gate 1: LocatorGate    - 定位器检查                    │ │
│  │  Gate 2: AcceptanceGate - Acceptance 状态检查          │ │
│  │  Gate 3: SemanticGate   - 语义等价门检查                │ │
│  │  Gate 4: CandidateGate  - 候选唯一性检查                │ │
│  │  Gate 5: ChangeGate     - 有效变更检查                  │ │
│  │  Gate 6: TemplateGate   - 模板重复检查                  │ │
│  │  Gate 7: DynamicGate   - 动态模板处理                  │ │
│  │  Gate 8: PlaceholderGate - 占位符语义检查               │ │
│  │  Gate 9: BuildGate      - 补丁构建                      │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │     GateResult (返回值)         │
              │  - status: GATE_PASS/GATE_SKIP │
              │  - reason_code: str           │
              │  - reason_message: str        │
              │  - patch: dict | None         │
              │  - context: dict              │
              └───────────────────────────────┘
```

### 3.2 目录结构

```
python/sqlopt/stages/
├── patch_decision/
│   ├── __init__.py
│   ├── engine.py              # 主入口，编排所有门控
│   ├── gates.py               # 门控基类和常量
│   ├── gate_locator.py        # Gate 1: 定位器检查
│   ├── gate_acceptance.py      # Gate 2: Acceptance 状态检查
│   ├── gate_semantic.py        # Gate 3: 语义等价门检查
│   ├── gate_candidate.py       # Gate 4: 候选唯一性检查
│   ├── gate_change.py          # Gate 5: 有效变更检查
│   ├── gate_template.py        # Gate 6: 模板重复检查
│   ├── gate_dynamic.py         # Gate 7: 动态模板处理 ← 重点增强
│   ├── gate_placeholder.py     # Gate 8: 占位符语义检查
│   ├── gate_build.py           # Gate 9: 补丁构建
│   ├── constants.py            # ReasonCode 常量定义
│   └── context.py              # 决策上下文定义
└── patch_decision_engine.py    # 向后兼容 Wrapper (废弃)
```

---

## 4. 详细设计

### 4.1 常量定义 (constants.py)

```python
from enum import Enum

class GateResultStatus(Enum):
    PASS = "GATE_PASS"
    SKIP = "GATE_SKIP"
    BLOCK = "GATE_BLOCK"

class ReasonCode(Enum):
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

    # Dynamic
    PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_FOREACH_TEMPLATE_REVIEW_REQUIRED"
    PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_SET_TEMPLATE_REVIEW_REQUIRED"
    PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED = "PATCH_DYNAMIC_FILTER_TEMPLATE_REVIEW_REQUIRED"
    PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE = "PATCH_INCLUDE_FRAGMENT_REQUIRES_TEMPLATE_AWARE_REWRITE"
    PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE = "PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE"

    # Security
    PATCH_VALIDATION_BLOCKED_SECURITY = "PATCH_VALIDATION_BLOCKED_SECURITY"

    # Placeholder
    PATCH_PLACEHOLDER_MISMATCH = "PATCH_PLACEHOLDER_MISMATCH"

    # Build
    PATCH_BUILD_FAILED = "PATCH_BUILD_FAILED"


class DeliveryTier(Enum):
    READY_TO_APPLY = "READY_TO_APPLY"
    BLOCKED = "BLOCKED"
    PATCHABLE_WITH_REWRITE = "PATCHABLE_WITH_REWRITE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
```

### 4.2 门控基类 (gates.py)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from .constants import GateResultStatus, ReasonCode

T = TypeVar('T')

@dataclass(frozen=True)
class GateContext:
    """门控执行上下文，所有门控共享的数据"""
    sql_unit: dict[str, Any]
    acceptance: dict[str, Any]
    selection: Any
    build: Any
    run_dir: Any
    acceptance_rows: list[dict]
    project_root: Any
    config: dict[str, Any] | None = None

@dataclass
class GateResult(Generic[T]):
    """门控执行结果"""
    status: GateResultStatus
    reason_code: str | None = None
    reason_message: str | None = None
    data: T | None = None
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
        """执行门控检查，返回结果"""
        pass

    def on_pass(self, ctx: GateContext) -> GateResult[T]:
        """门控通过时的默认处理"""
        return GateResult(status=GateResultStatus.PASS)

    def on_skip(self, reason_code: str, reason_message: str, **context) -> GateResult[T]:
        """门控跳过时的默认处理"""
        return GateResult(
            status=GateResultStatus.SKIP,
            reason_code=reason_code,
            reason_message=reason_message,
            context=context,
        )
```

### 4.3 动态模板门控 (gate_dynamic.py) - 重点改进

```python
from .gates import Gate, GateContext, GateResult
from .constants import ReasonCode, GateResultStatus, DeliveryTier

class DynamicTemplateGate(Gate[dict]):
    """
    Gate 7: 动态模板处理

    改进点：
    1. 不再只返回 BLOCKED，而是尝试生成模板级补丁
    2. 根据动态模板类型选择合适的策略
    3. 失败时才返回 BLOCKED
    """

    def __init__(self, build_template_fn, format_template_ops_fn):
        super().__init__("DynamicTemplate", order=7)
        self._build_template = build_template_fn
        self._format_template_ops = format_template_ops_fn

    def execute(self, ctx: GateContext) -> GateResult[dict]:
        dynamic_features = ctx.sql_unit.get("dynamicFeatures") or []

        # 无动态特征，直接通过
        if not dynamic_features:
            return self.on_pass(ctx)

        # 尝试模板级补丁生成
        return self._try_template_patch(ctx, dynamic_features)

    def _try_template_patch(self, ctx: GateContext, dynamic_features: list) -> GateResult[dict]:
        """尝试生成模板级补丁"""
        dynamic_template = ctx.selection.dynamic_template or {}
        dynamic_blocking_reason = str(dynamic_template.get("blockingReason") or "").strip().upper()
        dynamic_shape_family = str(dynamic_template.get("shapeFamily") or "").strip().upper()

        # 1. 检查是否支持当前动态模板类型
        supported = self._check_supported(dynamic_features, dynamic_blocking_reason, dynamic_shape_family)
        if not supported:
            return self._skip_for_unsupported(dynamic_blocking_reason, dynamic_shape_family)

        # 2. 格式化模板操作
        template_acceptance = self._format_template_ops(
            ctx.sql_unit, ctx.acceptance, ctx.run_dir
        )

        # 3. 检测重复子句
        duplicate_clause = ctx.selection.detect_duplicate_clause(template_acceptance)
        if duplicate_clause:
            return self.on_skip(
                ReasonCode.PATCH_TEMPLATE_DUPLICATE_CLAUSE_DETECTED.value,
                f"template rewrite contains duplicated {duplicate_clause} clause",
                dynamic_template_blocking_reason=dynamic_blocking_reason,
            )

        # 4. 尝试生成模板补丁
        patch_text, changed_lines, error = self._build_template(
            ctx.sql_unit, template_acceptance, ctx.run_dir
        )

        if error:
            return self.on_skip(
                error.get("code", "PATCH_TEMPLATE_BUILD_FAILED"),
                error.get("message", "template patch build failed"),
                dynamic_template_blocking_reason=dynamic_blocking_reason,
            )

        if patch_text:
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
                    "dynamic_template_strategy": dynamic_shape_family or dynamic_blocking_reason,
                }
            )

        # 5. 模板补丁生成失败，返回原因
        return self._skip_for_unsupported(dynamic_blocking_reason, dynamic_shape_family)

    def _check_supported(self, dynamic_features, blocking_reason, shape_family) -> bool:
        """检查当前动态模板类型是否支持"""
        # 已支持的类型
        supported_blocking_reasons = {
            "",  # 无动态特征
            "NO_TEMPLATE_PRESERVING_INTENT",
            "INCLUDE_DYNAMIC_SUBTREE",
            "DYNAMIC_FILTER_SUBTREE",
            "DYNAMIC_FILTER_NO_EFFECTIVE_DIFF",
        }
        supported_shape_families = {
            "IF_GUARDED_FILTER_STATEMENT",
            "IF_GUARDED_COUNT_WRAPPER",
        }

        return (
            blocking_reason in supported_blocking_reasons
            or shape_family in supported_shape_families
            or not dynamic_features  # 无动态特征也算支持
        )

    def _detect_artifact_kind(self, patch_text: str) -> str:
        """检测补丁产物类型"""
        import re
        if re.search(r"</?(if|where|set|trim|foreach|choose|when|otherwise|bind|include)\b", patch_text):
            return "TEMPLATE"
        return "STATEMENT"

    def _detect_strategy(self, dynamic_features: list, dynamic_template: dict) -> str:
        """检测使用的策略类型"""
        blocking_reason = str(dynamic_template.get("blockingReason") or "").strip().upper()
        shape_family = str(dynamic_template.get("shapeFamily") or "").strip().upper()

        if "COUNT" in str(dynamic_features) or "WRAPPER" in blocking_reason:
            if "DYNAMIC" in blocking_reason:
                return "DYNAMIC_COUNT_WRAPPER_COLLAPSE"
            return "SAFE_WRAPPER_COLLAPSE"

        if "FILTER" in str(dynamic_features) or "FILTER" in blocking_reason:
            return "DYNAMIC_FILTER_WRAPPER_COLLAPSE"

        if "INCLUDE" in dynamic_features:
            return "STATIC_INCLUDE_WRAPPER_COLLAPSE"

        return "DYNAMIC_STATEMENT_TEMPLATE_EDIT"
```

### 4.4 引擎编排 (engine.py)

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from .gates import Gate, GateContext, GateResult
from .constants import GateResultStatus

@dataclass
class EngineConfig:
    """引擎配置"""
    stop_on_first_block: bool = True  # 遇到 BLOCK 是否继续
    enable_dynamic_template: bool = True  # 是否启用动态模板处理

class PatchDecisionEngine:
    """
    Patch 决策引擎

    职责：
    1. 编排所有门控按顺序执行
    2. 收集门控结果，生成最终补丁决策
    3. 处理向后兼容
    """

    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()
        self._gates: list[Gate] = []
        self._dependencies: dict[str, Any] = {}

    def register_gate(self, gate: Gate) -> "PatchDecisionEngine":
        """注册门控"""
        self._gates.append(gate)
        self._gates.sort(key=lambda g: g.order)
        return self

    def register_dependency(self, name: str, instance: Any) -> "PatchDecisionEngine":
        """注册依赖实例"""
        self._dependencies[name] = instance
        return self

    def execute(self, ctx: GateContext) -> tuple[dict, Any]:
        """执行所有门控，返回最终结果"""
        results: list[GateResult] = []

        for gate in self._gates:
            result = gate.execute(ctx)

            if self.config.stop_on_first_block and result.status == GateResultStatus.SKIP:
                # 收集结果但继续执行（用于诊断）
                results.append(result)
                break

            results.append(result)

            if result.status == GateResultStatus.SKIP:
                # 生成跳过结果
                return self._build_skip_result(result, ctx), ctx

        # 所有门控通过，生成补丁
        return self._build_success_result(results, ctx), ctx

    def _build_skip_result(self, result: GateResult, ctx: GateContext) -> dict:
        """构建跳过结果"""
        return {
            "sqlKey": ctx.sql_unit.get("sqlKey"),
            "statementKey": ctx.sql_unit.get("statementKey"),
            "patchFiles": [],
            "diffSummary": {"skipped": True},
            "deliveryOutcome": {
                "tier": self._map_to_tier(result.reason_code),
                "reasonCodes": [result.reason_code] if result.reason_code else [],
                "summary": result.reason_message or "",
            },
            "selectionReason": {
                "code": result.reason_code,
                "message": result.reason_message,
            },
        }

    def _build_success_result(self, results: list[GateResult], ctx: GateContext) -> dict:
        """构建成功结果"""
        # 从最后一个 PASS 结果中提取补丁数据
        last_pass = None
        for r in reversed(results):
            if r.is_pass and r.data:
                last_pass = r
                break

        if last_pass and last_pass.data:
            return self._build_patch_result(last_pass.data, ctx)

        # 回退到默认语句级补丁生成
        return self._build_default_patch(ctx)

    def _map_to_tier(self, reason_code: str | None) -> str:
        """将 reason_code 映射到 DeliveryTier"""
        if not reason_code:
            return "BLOCKED"

        if "SECURITY" in reason_code:
            return "PATCHABLE_WITH_REWRITE"
        if "REVIEW" in reason_code:
            return "MANUAL_REVIEW"

        return "BLOCKED"


# 工厂函数：创建默认配置的引擎
def create_default_engine(
    build_template_fn,
    format_template_ops_fn,
    detect_duplicate_fn,
    normalize_sql_fn,
    format_sql_fn,
    build_unified_fn,
) -> PatchDecisionEngine:
    """创建默认配置的决策引擎"""

    engine = PatchDecisionEngine()

    # 注册所有门控
    engine.register_gate(LocatorGate())
    engine.register_gate(AcceptanceGate())
    engine.register_gate(SemanticGate())
    engine.register_gate(CandidateGate())
    engine.register_gate(ChangeGate(normalize_sql_fn))  # 注入依赖
    engine.register_gate(TemplateGate(detect_duplicate_fn))
    engine.register_gate(DynamicTemplateGate(build_template_fn, format_template_ops_fn))
    engine.register_gate(PlaceholderGate())
    engine.register_gate(BuildGate(build_unified_fn, format_sql_fn))

    return engine
```

---

## 5. 迁移计划

### 5.1 阶段 1: 创建新架构 (Week 1)

- [ ] 创建 `patch_decision/` 目录
- [ ] 实现 `constants.py` - ReasonCode 枚举
- [ ] 实现 `gates.py` - 门控基类
- [ ] 实现 `context.py` - 决策上下文
- [ ] 实现所有 9 个门控类（从现有逻辑迁移）

### 5.2 阶段 2: 增强动态模板处理 (Week 1-2)

- [ ] 重写 `gate_dynamic.py`:
  - [ ] 添加模板补丁生成逻辑
  - [ ] 添加策略检测
  - [ ] 添加产物类型检测
- [ ] 补充单元测试覆盖

### 5.3 阶段 3: 向后兼容 (Week 2)

- [ ] 保留 `patch_decision_engine.py` 作为 Wrapper:
  ```python
  # patch_decision_engine.py
  from .patch_decision.engine import create_default_engine, GateContext

  def decide_patch_result(*args, **kwargs):
      # 构建 GateContext
      ctx = GateContext(...)

      # 创建引擎并执行
      engine = create_default_engine(...)
      return engine.execute(ctx)
  ```
- [ ] 运行所有现有测试确保兼容

### 5.4 阶段 4: 验证优化 (Week 2)

- [ ] 运行完整测试套件
- [ ] 性能基准测试
- [ ] 更新文档

---

## 6. 预期收益

| 指标 | 当前 | 改进后 |
|------|------|--------|
| 模块行数 | 367 行 (单文件) | 8-10 个独立文件 |
| 门控可独立测试 | 困难 | 容易 |
| 新增门控成本 | 修改单文件 | 添加新文件 |
| 动态模板支持 | 仅返回 BLOCKED | 完整生成补丁 |
| ReasonCode 管理 | 散落各处 | 集中枚举 |

---

## 7. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 迁移破坏现有功能 | 保留向后兼容 Wrapper，渐进式迁移 |
| 门控顺序变化影响行为 | 单元测试覆盖所有现有场景 |
| 动态模板生成引入 bug | 添加集成测试验证补丁正确性 |

---

## 8. 验收标准

- [ ] 所有现有测试通过
- [ ] 动态模板样例能生成真实补丁（不再全部返回 BLOCKED）
- [ ] 新增 20+ 单元测试覆盖各个门控
- [ ] 代码审查通过