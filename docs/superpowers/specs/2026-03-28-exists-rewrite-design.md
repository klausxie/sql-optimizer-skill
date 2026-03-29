# EXISTS 重写功能设计

**日期**: 2026-03-28
**状态**: 已批准，2026-03-30 harness review 收紧 v1 边界
**功能**: 为 SQL Optimizer 添加 EXISTS 重写功能

---

## 1. 概述

### 1.1 目的

为 SQL Optimizer 添加一个窄安全边界的 `EXISTS` 重写功能，在 v1 中只支持正向相关 `EXISTS -> IN` 改写。

### 1.2 背景

- 当前 Patch Family 覆盖 28 个优化场景（包含 UNION）
- EXISTS 是常见 SQL 模式，但未在覆盖范围内
- 用户将 EXISTS 优化设为高优先级功能

---

## 2. 功能需求

### 2.1 支持的场景

| 场景 | 输入 | 输出 |
|------|------|------|
| EXISTS → IN | `WHERE EXISTS (SELECT 1 FROM t WHERE t.id = a.id)` | `WHERE a.id IN (SELECT t.id FROM t)` |

### 2.2 关键约束

- **安全性优先**：平衡覆盖，但优先保证安全
- **语义验证**：必须通过 DB EXPLAIN 验证
- **回放验证**：必须通过模板回放验证
- **置信度**：要求 HIGH
- **v1 边界**：只允许正向 `EXISTS -> IN` 安全基线，不在 v1 内混入更宽语义路径

### 2.3 v1 显式排除项

下列路径不属于本设计的 v1 family boundary：

1. `NOT EXISTS -> NOT IN`
2. `EXISTS -> JOIN`
3. 需要借助 `DISTINCT` 修复重复行的 rewrite
4. 无法证明关联键安全投影的相关子查询

---

## 3. 技术设计

### 3.1 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                      新增文件                                │
├─────────────────────────────────────────────────────────────┤
│  platforms/sql/exists_utils.py                             │
│  platforms/sql/patch_capability_rules/safe_exists_rewrite.py │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      修改文件                                │
├─────────────────────────────────────────────────────────────┤
│  platforms/sql/patch_capability_rules/__init__.py          │
│  platforms/sql/materialization_constants.py                │
│  patch_families/registry.py                                 │
│  patch_families/specs/static_exists_rewrite.py            │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 通用模块 (exists_utils.py)

```python
# platforms/sql/exists_utils.py

def contains_exists(sql: str) -> bool:
    """检测 SQL 是否包含 EXISTS 关键字"""

def detect_exists_pattern(sql: str) -> dict:
    """检测 EXISTS 模式
    Returns: {
        "type": "EXISTS" | "NOT_EXISTS",
        "subquery": str,
        "correlation": str,
        "positive_exists": bool,
    }
    """

def rewrite_exists_to_in(sql: str, pattern: dict) -> str | None:
    """将 EXISTS 重写为 IN"""

def validate_exists_rewrite_safety(original: str, rewritten: str) -> tuple[bool, str | None]:
    """验证重写安全性"""
```

### 3.3 Capability 规则

```python
# patch_capability_rules/safe_exists_rewrite.py

class SafeExistsRewriteCapabilityRule:
    capability = "SAFE_EXISTS_REWRITE"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        # 检查语义门
        # 检查正向 EXISTS 模式
        # 检查相关键是否可安全投影
        # 检查重写安全性
```

---

## 4. 实现策略

### 4.1 重写模式

#### EXISTS → IN
```sql
-- 原始
SELECT * FROM a WHERE EXISTS (SELECT 1 FROM b WHERE b.id = a.id)

-- 重写后
SELECT * FROM a WHERE a.id IN (SELECT b.id FROM b)
```

v1 不包含：

1. `NOT EXISTS -> NOT IN`
2. `EXISTS -> JOIN`

### 4.2 安全性检查

```python
def validate_exists_rewrite_safety(original: str, rewritten: str) -> tuple[bool, str | None]:
    """EXISTS 重写安全性检查"""

    checks = [
        # 相关子查询检查
        ("correlation_required", not has_correlation(original),
         "CORRELATION_REQUIRED"),

        # 只允许正向 EXISTS family，NOT EXISTS 不进入 v1 family
        ("positive_exists_only", not pattern["positive_exists"],
         "NEGATED_EXISTS_OUT_OF_SCOPE"),

        # 关联键必须能安全投影为 IN 子查询目标
        ("unsafe_projection_key", not has_safe_projection_key(pattern),
         "UNSAFE_EXISTS_PROJECTION_KEY"),
    ]

    for check_name, failed, reason in checks:
        if failed:
            return False, reason

    return True, None
```

---

## 5. 测试设计

### 5.1 单元测试

| 测试用例 | 说明 |
|----------|------|
| test_contains_exists | EXISTS 检测 |
| test_detect_exists_pattern | EXISTS 模式检测 |
| test_rewrite_exists_to_in | EXISTS → IN 重写 |
| test_validate_exists_safety | 安全性验证 |
| test_negated_exists_blocked | `NOT EXISTS` 被阻断 |
| test_exists_join_path_blocked | `EXISTS -> JOIN` 不进入 v1 family |

### 5.2 集成测试

| 测试用例 | 说明 |
|----------|------|
| test_capability_rule | Capability 规则测试 |
| test_patch_generation | Patch 生成测试 |
| test_exists_ready_and_blocked_neighbors | ready 与 blocked-neighbor 场景同时锁住 |
| test_exists_scoped_workflow | 一条真实 workflow slice 证明 v1 family |

---

## 6. 工作量估算

| 任务 | 工作量 |
|------|--------|
| exists_utils.py 通用模块 | 1.5 天 |
| Capability 规则实现 | 1.5 天 |
| Family Spec 定义 | 0.5 天 |
| 注册策略和 Family | 0.5 天 |
| 单元测试与 blocked-neighbor 覆盖 | 1 天 |
| 集成测试与 scoped workflow harness | 1.5 天 |
| **总计** | **6.5 天 (~1.5 周)** |

---

## 7. 风险缓解

| 风险 | 缓解措施 |
|------|----------|
| v1 边界被悄悄放宽 | 将 `NOT EXISTS -> NOT IN` 与 `EXISTS -> JOIN` 显式定义为 out-of-scope |
| 相关键不可安全投影 | 要求 family 级 blocker，拒绝进入 ready path |
| 相关子查询 | 必须存在关联条件才能转换 |
| 性能退化 | 强制 DB EXPLAIN 验证 |

---

## 8. 验收标准

- [ ] EXISTS → IN 重写正常工作
- [ ] `NOT EXISTS -> NOT IN` 在 v1 中保持 blocked / out-of-scope
- [ ] `EXISTS -> JOIN` 在 v1 中保持 blocked / out-of-scope
- [ ] 安全性检查通过
- [ ] 回放验证通过
- [ ] 单元测试覆盖主要场景
- [ ] 至少一条 scoped workflow harness 通过
- [ ] 与现有系统无缝集成

---

## 9. 相关文件

### 新增
- `platforms/sql/exists_utils.py`
- `platforms/sql/patch_capability_rules/safe_exists_rewrite.py`
- `tests/test_exists_rewrite.py`

### 修改
- `platforms/sql/patch_capability_rules/__init__.py`
- `platforms/sql/materialization_constants.py`
- `patch_families/registry.py`
- `patch_families/specs/static_exists_rewrite.py`

---

## Harness Plan

### Proof Obligations

1. `EXISTS` rewrite stays within an explicitly approved positive-`EXISTS -> IN` safe family boundary
2. replay closes back to the selected target SQL
3. placeholder and correlation semantics do not drift
4. `NOT EXISTS` and `EXISTS -> JOIN` remain blocked or out-of-scope in v1
5. ready and blocked-neighbor cases are both locked

### Harness Layers

#### L1 Unit Harness

- Goal: prove `EXISTS` detection, capability gating, and strategy selection
- Scope: family classification, blocker logic, positive-`EXISTS` safe boundaries
- Allowed Mocks: synthetic SQL and planner inputs are acceptable
- Artifacts Checked: in-memory family and strategy payloads
- Budget: fast PR-safe runtime

#### L2 Fixture / Contract Harness

- Goal: prove fixture scenarios and patch/report contracts for the `EXISTS` family
- Scope: ready case, blocked neighbors, replay and verification assertions, out-of-scope family paths
- Allowed Mocks: synthetic validate evidence is acceptable for contract proof
- Artifacts Checked: fixture matrix, patch artifacts, verification artifacts, report outputs
- Budget: moderate PR-safe runtime

#### L3 Scoped Workflow Harness

- Goal: prove one selected `EXISTS` example through a real workflow slice before family onboarding closes
- Scope: one SQL key or one mapper example
- Allowed Mocks: infrastructure-availability patches only
- Artifacts Checked: selected real run outputs
- Budget: targeted workflow runtime

#### L4 Full Workflow Harness

- Goal: prove `EXISTS` onboarding does not regress the broader fixture project
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
2. `L3` is required to prove one representative real example before onboarding closes
3. `L4` remains the broad-regression layer

### Regression Ownership

1. `EXISTS` family scope changes
2. correlation or placeholder handling changes
3. any future widening to `NOT EXISTS` or `JOIN` paths
4. report fields derived from the new family

---

**设计批准日期**: 2026-03-28
