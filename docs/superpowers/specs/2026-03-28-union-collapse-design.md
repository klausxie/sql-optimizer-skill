# UNION 包装折叠功能设计

**日期**: 2026-03-28
**状态**: 已批准
**功能**: 为 SQL Optimizer 添加 UNION 包装折叠功能

---

## 1. 概述

### 1.1 目的

为 SQL Optimizer 添加 UNION 包装折叠功能，支持将嵌套 UNION 查询（如 `SELECT * FROM (SELECT ... UNION ALL SELECT ...) t`）简化为平面查询（`SELECT ... UNION ALL SELECT ...`）。

### 1.2 背景

- 当前 Patch Family 覆盖 83% 核心优化场景
- UNION 是常见 SQL 语法，但未在覆盖范围内
- 用户将 UNION 优化设为高优先级功能

---

## 2. 功能需求

### 2.1 支持的场景

| 场景 | 输入 | 输出 |
|------|------|------|
| 基础 UNION ALL 折叠 | `SELECT * FROM (SELECT a FROM t1 UNION ALL SELECT b FROM t2) t` | `SELECT a FROM t1 UNION ALL SELECT b FROM t2` |
| 基础 UNION 折叠 | `SELECT * FROM (SELECT a FROM t1 UNION SELECT b FROM t2) t` | `SELECT a FROM t1 UNION SELECT b FROM t2` |
| 带 ORDER BY | `SELECT * FROM (...) t ORDER BY x` | `SELECT ... UNION ALL SELECT ... ORDER BY x` |
| 带 LIMIT | `SELECT * FROM (...) t LIMIT 10` | `SELECT ... UNION ALL SELECT ... LIMIT 10` |
| 带 ORDER BY + LIMIT | `SELECT * FROM (...) t ORDER BY x LIMIT 10` | `SELECT ... UNION ALL SELECT ... ORDER BY x LIMIT 10` |

### 2.2 关键约束

- **UNION 类型保留**：LLM 输出什么类型就保留什么类型（UNION 或 UNION ALL）
- **安全性优先**：平衡覆盖，但优先保证安全
- **回放验证**：必须通过模板回放验证才能生成 patch

---

## 3. 技术设计

### 3.1 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      新增文件                                │
├─────────────────────────────────────────────────────────────┤
│  patch_families/specs/static_union_collapse.py              │
│  platforms/sql/union_utils.py                              │
│  platforms/sql/union_collapse_strategy.py                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      修改文件                                │
├─────────────────────────────────────────────────────────────┤
│  platforms/sql/patch_strategy_registry.py                   │
│  platforms/sql/patch_safety.py                              │
│  patch_families/registry.py                                 │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 通用模块 (union_utils.py)

```python
# platforms/sql/union_utils.py

def detect_union_type(sql: str) -> str:
    """检测 UNION 类型: UNION ALL / UNION"""

def contains_union(sql: str) -> bool:
    """检测 SQL 是否包含 UNION 关键字"""

def validate_union_safety(sql: str) -> tuple[bool, str | None]:
    """验证 UNION 优化的安全性"""

def extract_union_components(sql: str) -> list[dict]:
    """提取 UNION 各组件（用于未来扩展）"""

def normalize_union_sql(sql: str) -> str:
    """标准化 UNION SQL（用于比较）"""
```

### 3.3 策略实现 (union_collapse_strategy.py)

```python
# SafeUnionCollapseStrategy 类

class SafeUnionCollapseStrategy:
    strategy_type = "SAFE_UNION_COLLAPSE"
    required_capability = "SAFE_UNION_COLLAPSE"

    def plan(
        self,
        sql_unit: dict,
        rewritten_sql: str,
        fragment_catalog: dict,
        *,
        enable_fragment_materialization: bool,
        fallback_from: str | None,
        dynamic_candidate_intent: dict | None = None,
    ) -> PlannedPatchStrategy | None:
        # 1. 检测是否包含 UNION
        # 2. 验证安全性
        # 3. 生成 materialization 和 ops
        # 4. 返回 PlannedPatchStrategy
```

### 3.4 Family Spec 定义

```python
# patch_families/specs/static_union_collapse.py

STATIC_UNION_COLLAPSE_SPEC = PatchFamilySpec(
    family="STATIC_UNION_COLLAPSE",
    status="FROZEN_AUTO_PATCH",
    stage="MVP_STATIC_BASELINE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",  # 严格于 WRAPPER_COLLAPSE
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="SAFE_UNION_COLLAPSE",
        requires_replay_contract=True,
        materialization_modes=("STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE",
    ),
    verification=PatchFamilyVerificationPolicy(
        require_replay_match=True,
        require_xml_parse=True,
        require_render_ok=True,
        require_sql_parse=True,
        require_apply_check=True,
    ),
    blockers=PatchFamilyBlockingPolicy(),
    fixture_obligations=PatchFamilyFixtureObligations(...),
)
```

### 3.5 安全性检查

```python
def validate_union_safety(union_sql: str) -> tuple[bool, str | None]:
    """UNION 安全性检查"""

    checks = [
        # 不支持嵌套 UNION（复杂度高）
        ("nested_union", union_sql.upper().count('UNION') > 1,
         "nested_union_not_supported"),

        # FOR UPDATE 在 UNION 中不支持
        ("for_update", re.search(r'FOR\s+UPDATE', union_sql, re.I),
         "for_update_not_supported"),

        # 列数一致性需要在 SQL 解析阶段验证（略过）
    ]

    for check_name, failed, reason in checks:
        if failed:
            return False, reason

    return True, None
```

---

## 4. 策略注册

### 4.1 patch_safety.py 扩展

```python
# 新增 capability
ALLOWED_CAPABILITY_UNION_COLLAPSE = "SAFE_UNION_COLLAPSE"

# 在 assess_patch_safety_model 中添加检测
def assess_patch_safety_model(rewrite_facts, dynamic_intent=None):
    # ...
    if _can_apply_union_collapse(rewrite_facts):
        allowed_capabilities.append(ALLOWED_CAPABILITY_UNION_COLLAPSE)
```

### 4.2 registry.py 扩展

```python
# 注册新 Family
from ..specs.static_union_collapse import STATIC_UNION_COLLAPSE_SPEC

_FAMILY_REGISTRY = {
    # ... 现有
    "STATIC_UNION_COLLAPSE": STATIC_UNION_COLLAPSE_SPEC,
}
```

### 4.3 patch_strategy_registry.py 扩展

```python
def iter_patch_strategies() -> tuple[RegisteredPatchStrategy, ...]:
    return (
        # 新增（优先级高于 WRAPPER_COLLAPSE）
        RegisteredPatchStrategy(
            strategy_type=SafeUnionCollapseStrategy.strategy_type,
            priority=250,
            required_capability=SafeUnionCollapseStrategy.required_capability,
            implementation=SafeUnionCollapseStrategy(),
        ),
        # ... 现有��略
    )
```

---

## 5. 测试设计

### 5.1 单元测试

| 测试用例 | 说明 |
|----------|------|
| test_union_all_collapse | UNION ALL 包装折叠 |
| test_union_collapse | UNION 包装折叠 |
| test_union_with_order_by | 带 ORDER BY 的 UNION |
| test_union_with_limit | 带 LIMIT 的 UNION |
| test_union_with_order_by_and_limit | 带 ORDER BY + LIMIT |
| test_nested_union_rejected | 嵌套 UNION 拒绝 |
| test_union_with_for_update_rejected | FOR UPDATE 拒绝 |
| test_replay_verification | 回放验证 |

### 5.2 集成测试

| 测试用例 | 说明 |
|----------|------|
| test_full_pipeline | 端到端完整流程 |
| test_fallback_to_exact_template | 回退到 ExactTemplateEdit |

---

## 6. 演进性设计

### 6.1 通用模块扩展

`union_utils.py` 设计为可扩展：

```python
# 未来可添加:
def detect_intersect_type(sql: str) -> str: ...
def detect_except_type(sql: str) -> str: ...
def validate_nested_union_safety(sql: str) -> tuple[bool, str | None]: ...
```

### 6.2 策略扩展

未来可注册新策略：

```python
# patch_strategy_registry.py
RegisteredPatchStrategy(
    strategy_type="SAFE_INTERSECT_COLLAPSE",
    priority=250,
    required_capability="SAFE_INTERSECT_COLLAPSE",
    implementation=SafeIntersectCollapseStrategy(),
),

RegisteredPatchStrategy(
    strategy_type="SAFE_NESTED_UNION_COLLAPSE",
    priority=200,
    required_capability="SAFE_NESTED_UNION_COLLAPSE",
    implementation=SafeNestedUnionCollapseStrategy(),
),
```

---

## 7. 工作量估算

| 任务 | 工作量 |
|------|--------|
| union_utils.py 通用模块 | 1 天 |
| union_collapse_strategy.py 策略实现 | 2 天 |
| static_union_collapse.py Spec 定义 | 0.5 天 |
| patch_safety.py 扩展 | 0.5 天 |
| patch_strategy_registry.py 注册 | 0.5 天 |
| registry.py 注册 | 0.5 天 |
| 单元测试 | 1.5 天 |
| 集成测试 | 1 天 |
| **总计** | **7 天 (~2 周)** |

---

## 8. 风险缓解

| 风险 | 缓解措施 |
|------|----------|
| 列数不一致 | 通过 DB EXPLAIN 验证 |
| 语义变化 | 强制 semantic_required_status=PASS |
| 回放失败 | replayVerified 检查 |
| 嵌套 UNION | 明确拒绝并返回 reasonCode |

---

## 9. 验收标准

- [ ] UNION ALL 包装折叠正常工作
- [ ] UNION 包装折叠正常工作
- [ ] ORDER BY 正确保留
- [ ] LIMIT 正确保留
- [ ] 嵌套 UNION 明确拒绝
- [ ] 回放验证通过
- [ ] 单元测试覆盖主要场景
- [ ] 与现有系统无缝集成

---

## 10. 相关文件

### 新增
- `patch_families/specs/static_union_collapse.py`
- `platforms/sql/union_utils.py`
- `platforms/sql/union_collapse_strategy.py`
- `tests/test_union_collapse.py`

### 修改
- `patch_families/registry.py`
- `platforms/sql/patch_strategy_registry.py`
- `platforms/sql/patch_safety.py`

---

## Harness Plan

### Proof Obligations

1. UNION collapse stays within an explicitly approved safe family boundary
2. replay closes back to the selected target SQL
3. wrapper removal does not drift ordering, placeholders, or branch structure
4. ready and blocked-neighbor cases are both locked

### Harness Layers

#### L1 Unit Harness

- Goal: prove UNION wrapper detection, capability gating, and strategy selection
- Scope: wrapper shape, branch preservation, blocker logic
- Allowed Mocks: synthetic SQL and planner inputs are acceptable
- Artifacts Checked: in-memory family and strategy payloads
- Budget: fast PR-safe runtime

#### L2 Fixture / Contract Harness

- Goal: prove fixture scenarios and patch/report contracts for the UNION family
- Scope: ready case, blocked neighbors, replay and verification assertions
- Allowed Mocks: synthetic validate evidence is acceptable for contract proof
- Artifacts Checked: fixture matrix, patch artifacts, verification artifacts, report outputs
- Budget: moderate PR-safe runtime

#### L3 Scoped Workflow Harness

- Goal: prove one selected UNION example through a real workflow slice
- Scope: one SQL key or one mapper example
- Allowed Mocks: infrastructure-availability patches only
- Artifacts Checked: selected real run outputs
- Budget: targeted workflow runtime

#### L4 Full Workflow Harness

- Goal: prove UNION onboarding does not regress the broader fixture project
- Scope: full patch/report workflow regression
- Allowed Mocks: only workflow-stability patches that preserve patch semantics
- Artifacts Checked: full run patch, verification, and report outputs
- Budget: separately governed broader regression lane

### Shared Classification Logic

1. family readiness
2. blocker family
3. delivery classification

### Artifacts And Diagnostics

1. `pipeline/validate/acceptance.results.jsonl`
2. `pipeline/patch_generate/patch.results.jsonl`
3. `pipeline/verification/ledger.jsonl`
4. `overview/report.json`

### Execution Budget

1. `L1` and `L2` are required for family onboarding
2. `L3` should prove one representative real example
3. `L4` remains the broad-regression layer

### Regression Ownership

1. UNION family scope changes
2. wrapper-preservation logic changes
3. report fields derived from the new family

---

**设计批准日期**: 2026-03-28
