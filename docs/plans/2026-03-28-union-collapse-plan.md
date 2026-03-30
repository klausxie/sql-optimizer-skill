# UNION Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 SQL Optimizer 实现 UNION 包装折叠功能，支持将嵌套 UNION 查询简化为平面查询

**Architecture:** 基于现有 STATIC_WRAPPER_COLLAPSE 架构扩展，新增 SafeUnionCollapseStrategy 策略，通过独立的 union_utils.py 模块提供通用能力，支持未来扩展 INTERSECT/EXCEPT

**Tech Stack:** Python, SQL Optimizer 现有框架

---

## 任务 1: 创建通用工具模块 union_utils.py

**Files:**
- Create: `python/sqlopt/platforms/sql/union_utils.py`

- [ ] **Step 1: 创建空文件并写入基础框架**

```python
"""UNION 通用工具模块

提供 UNION 相关的检测、验证和转换功能。
设计为可扩展，支持未来 INTERSECT/EXCEPT 等场景。
"""

from __future__ import annotations

import re
from typing import Any


# 正则表达式定义
_UNION_ALL_PATTERN = re.compile(r'\bUNION\s+ALL\b', re.IGNORECASE)
_UNION_PATTERN = re.compile(r'\bUNION\b(?!\s+ALL)', re.IGNORECASE)
_FOR_UPDATE_PATTERN = re.compile(r'\bFOR\s+UPDATE\b', re.IGNORECASE)


def contains_union(sql: str) -> bool:
    """检测 SQL 是否包含 UNION 关键字

    Args:
        sql: SQL 语句

    Returns:
        True if contains UNION or UNION ALL
    """
    if not sql:
        return False
    sql_upper = sql.upper()
    return 'UNION' in sql_upper


def detect_union_type(sql: str) -> str:
    """检测 UNION 类型

    Args:
        sql: SQL 语句

    Returns:
        'UNION ALL', 'UNION', 或 'NONE'
    """
    if not sql:
        return 'NONE'

    if _UNION_ALL_PATTERN.search(sql):
        return 'UNION ALL'

    if _UNION_PATTERN.search(sql):
        return 'UNION'

    return 'NONE'


def has_nested_union(sql: str) -> bool:
    """检测是否有嵌套 UNION（超过一个 UNION 关键字）

    Args:
        sql: SQL 语句

    Returns:
        True if has nested UNION
    """
    if not sql:
        return False

    # 计算 UNION 关键字数量（排除 UNION ALL 中的 UNION）
    # 简单方法：替换 UNION ALL 后再计数
    temp_sql = _UNION_ALL_PATTERN.sub('', sql)
    union_count = temp_sql.upper().count('UNION')

    return union_count > 1


def validate_union_safety(sql: str) -> tuple[bool, str | None]:
    """验证 UNION 优化的安全性

    Args:
        sql: UNION SQL 语句

    Returns:
        (is_safe, reason_code) - 如果安全返回 (True, None)，否则返回 (False, reason_code)
    """
    if not sql:
        return False, "empty_sql"

    # 检查嵌套 UNION
    if has_nested_union(sql):
        return False, "NESTED_UNION_NOT_SUPPORTED"

    # 检查 FOR UPDATE（UNION 不支持）
    if _FOR_UPDATE_PATTERN.search(sql):
        return False, "FOR_UPDATE_NOT_SUPPORTED"

    # 检查 DISTINCT（UNION 自动去重，外层 DISTINCT 可能有不同语义）
    if re.search(r'^\s*SELECT\s+DISTINCT\b', sql, re.IGNORECASE | re.MULTILINE):
        return False, "DISTINCT_SEMANTICS_MAY_DIFFER"

    return True, None


def is_union_wrapper_pattern(template_sql: str) -> bool:
    """检测模板是否匹配 UNION 包装模式

    模式: SELECT * FROM ( ... UNION ... ) [alias]

    Args:
        template_sql: 模板 SQL

    Returns:
        True if matches UNION wrapper pattern
    """
    if not template_sql:
        return False

    # 匹配模式: SELECT ... FROM ( SELECT ... UNION ... ) [alias]
    pattern = re.compile(
        r'^\s*SELECT\s+\*\s+FROM\s+\(\s*SELECT\s+.*?\s+UNION\s+',
        re.IGNORECASE | re.DOTALL
    )

    return bool(pattern.search(template_sql))
```

- [ ] **Step 2: 运行 Python 导入测试**

Run: `PYTHONPATH=python python3 -c "from sqlopt.platforms.sql.union_utils import contains_union, detect_union_type, validate_union_safety; print('Import OK')"`
Expected: Import OK

- [ ] **Step 3: 提交**

```bash
git add python/sqlopt/platforms/sql/union_utils.py
git commit -m "feat: add union_utils.py with common UNION utility functions

- contains_union(): detect UNION keyword
- detect_union_type(): detect UNION vs UNION ALL
- validate_union_safety(): safety checks for UNION optimization
- has_nested_union(): detect nested UNION
- is_union_wrapper_pattern(): detect UNION wrapper pattern

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

## 任务 2: 创建 UNION 折叠策略实现

**Files:**
- Create: `python/sqlopt/platforms/sql/union_collapse_strategy.py`

- [ ] **Step 1: 创建策略实现文件**

```python
"""UNION 包装折叠策略实现

SafeUnionCollapseStrategy - 安全折叠 UNION 包装查询
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .materialization_constants import (
    STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE,
    REASON_STATEMENT_INCLUDE_SAFE,
)
from .patchability_models import PlannedPatchStrategy
from .template_rendering import collect_fragments, normalize_sql_text, render_template_body_sql
from .union_utils import (
    contains_union,
    detect_union_type,
    is_union_wrapper_pattern,
    validate_union_safety,
)


class SafeUnionCollapseStrategy:
    """UNION 包装折叠策略

    处理模式:
    - SELECT * FROM (SELECT ... UNION ALL SELECT ...) t → SELECT ... UNION ALL SELECT ...
    - SELECT * FROM (SELECT ... UNION SELECT ...) t → SELECT ... UNION SELECT ...

    保留:
    - UNION 类型（UNION vs UNION ALL）
    - ORDER BY
    - LIMIT
    """

    strategy_type = "SAFE_UNION_COLLAPSE"
    required_capability = "SAFE_UNION_COLLAPSE"

    def plan(
        self,
        sql_unit: dict[str, Any],
        rewritten_sql: str,
        fragment_catalog: dict[str, dict[str, Any]],
        *,
        enable_fragment_materialization: bool = False,
        fallback_from: str | None = None,
        dynamic_candidate_intent: dict[str, Any] | None = None,
    ) -> PlannedPatchStrategy | None:
        """生成 UNION 折叠策略

        Args:
            sql_unit: SQL 单元
            rewritten_sql: 重写后的 SQL
            fragment_catalog: 片段目录
            enable_fragment_materialization: 是否启用片段物化
            fallback_from: 回退来源策略
            dynamic_candidate_intent: 动态候选意图

        Returns:
            PlannedPatchStrategy 或 None
        """
        _ = fragment_catalog
        _ = enable_fragment_materialization
        _ = dynamic_candidate_intent

        # 1. 检查是否包含 UNION
        if not contains_union(rewritten_sql):
            return None

        # 2. 验证安全性
        is_safe, reason = validate_union_safety(rewritten_sql)
        if not is_safe:
            return None

        # 3. 生成 materialization
        materialization, ops = self._build_materialization(sql_unit, rewritten_sql)

        if materialization is None:
            return None

        return PlannedPatchStrategy(
            strategy_type=self.strategy_type,
            mode=str(materialization.get("mode") or ""),
            reason_code=str(materialization.get("reasonCode") or REASON_STATEMENT_INCLUDE_SAFE),
            replay_verified=materialization.get("replayVerified"),
            fallback_from=fallback_from,
            materialization=materialization,
            ops=ops,
        )

    def _build_materialization(
        self,
        sql_unit: dict[str, Any],
        rewritten_sql: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """构建 materialization 和 ops

        Args:
            sql_unit: SQL 单元
            rewritten_sql: 重写后的 SQL

        Returns:
            (materialization, ops) 或 (None, [])
        """
        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        namespace = str(sql_unit.get("namespace") or "").strip()
        statement_key = str(sql_unit.get("sqlKey") or "").split("#", 1)[0]
        template_sql = str(sql_unit.get("templateSql") or "")

        # 验证必要字段
        if not xml_path.exists() or not template_sql or not rewritten_sql.strip():
            return None, []

        # 解析 XML
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(xml_path).getroot()
        except Exception:
            return None, []

        # 验证回放
        replayed = render_template_body_sql(
            rewritten_sql, namespace, xml_path, collect_fragments(root, namespace, xml_path)
        )

        if normalize_sql_text(replayed or "") != normalize_sql_text(rewritten_sql):
            return None, []

        # 检测 UNION 类型
        union_type = detect_union_type(rewritten_sql)

        # 构建 materialization
        materialization = {
            "mode": STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE,
            "targetType": "STATEMENT",
            "targetRef": statement_key,
            "reasonCode": "UNION_COLLAPSE_SAFE",
            "reasonMessage": f"wrapper query with {union_type} can be safely collapsed",
            "replayVerified": True,
            "featureFlagApplied": False,
            "unionType": union_type,
        }

        ops = [
            {
                "op": "replace_statement_body",
                "targetRef": statement_key,
                "beforeTemplate": template_sql,
                "afterTemplate": rewritten_sql,
                "preservedAnchors": [],
                "safetyChecks": {"unionCollapse": True},
            }
        ]

        return materialization, ops
```

- [ ] **Step 2: 添加常量和注册**

需要在 materialization_constants.py 中添加新常量：

- [ ] **Step 2.1: 检查并添加常量**

Run: `grep -n "STATEMENT_TEMPLATE_SAFE" python/sqlopt/platforms/sql/materialization_constants.py | head -5`
Expected: 显示现有常量定义

- [ ] **Step 2.2: 添加新常量**

```python
# 在 materialization_constants.py 添加:
STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE = "STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE"
```

- [ ] **Step 3: 运行导入测试**

Run: `PYTHONPATH=python python3 -c "from sqlopt.platforms.sql.union_collapse_strategy import SafeUnionCollapseStrategy; print('Import OK')"`
Expected: Import OK

- [ ] **Step 4: 提交**

```bash
git add python/sqlopt/platforms/sql/union_collapse_strategy.py python/sqlopt/platforms/sql/materialization_constants.py
git commit -m "feat: add SafeUnionCollapseStrategy for UNION wrapper collapse

- New strategy class SafeUnionCollapseStrategy
- Handles UNION/UNION ALL wrapper collapse
- Validates safety before generating patch
- Preserves UNION type, ORDER BY, LIMIT

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>"
```

---

## 任务 3: 创建 Family Spec 定义

**Files:**
- Create: `python/sqlopt/patch_families/specs/static_union_collapse.py`

- [ ] **Step 1: 创建 Spec 定义**

```python
"""STATIC_UNION_COLLAPSE Family Spec

UNION 包装折叠 Family 定义
"""

from __future__ import annotations

from ..models import (
    PatchFamilyAcceptancePolicy,
    PatchFamilyBlockingPolicy,
    PatchFamilyFixtureObligations,
    PatchFamilyPatchTargetPolicy,
    PatchFamilyReplayPolicy,
    PatchFamilyScope,
    PatchFamilySpec,
    PatchFamilyVerificationPolicy,
)

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
        semantic_min_confidence="HIGH",  # UNION 风险较高，使用 HIGH
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
    fixture_obligations=PatchFamilyFixtureObligations(
        ready_case_required=True,
        blocked_neighbor_required=False,
        replay_assertions_required=True,
        verification_assertions_required=True,
    ),
)
```

- [ ] **Step 2: 测试导入**

Run: `PYTHONPATH=python python3 -c "from sqlopt.patch_families.specs.static_union_collapse import STATIC_UNION_COLLAPSE_SPEC; print(f'Family: {STATIC_UNION_COLLAPSE_SPEC.family}, Status: {STATIC_UNION_COLLAPSE_SPEC.status}')"`
Expected: Family: STATIC_UNION_COLLAPSE, Status: FROZEN_AUTO_PATCH

- [ ] **Step 3: 提交**

```bash
git add python/sqlopt/patch_families/specs/static_union_collapse.py
git commit -m "feat: add STATIC_UNION_COLLAPSE Family Spec

- Semantic required: PASS
- Semantic min confidence: HIGH
- Materialization mode: STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering)"
```

---

## 任务 4: 扩展 patch_safety.py - 添加 Capability

**Files:**
- Modify: `python/sqlopt/platforms/sql/patch_safety.py`

- [ ] **Step 1: 查找现有 capability 定义位置**

Run: `grep -n "SAFE_WRAPPER_COLLAPSE" python/sqlopt/platforms/sql/patch_safety.py | head -3`
Expected: 显示相关行号

- [ ] **Step 2: 添加新 capability**

在 patch_safety.py 中添加:

```python
# 添加新的 capability 常量
SAFE_UNION_COLLAPSE = "SAFE_UNION_COLLAPSE"
```

- [ ] **Step 3: 在能力列表中添加**

查找 allowed_capabilities 赋值位置，添加新能力：

Run: `grep -n "allowed_capabilities" python/sqlopt/platforms/sql/patch_safety.py | head -3`
Expected: 显示相关行

- [ ] **Step 4: 添加 UNION 能力检测**

在适当位置添加:

```python
# 检查是否可以应用 UNION 折叠
if is_union_wrapper_pattern(template_sql) and contains_union(rewritten_sql):
    is_safe, _ = validate_union_safety(rewritten_sql)
    if is_safe:
        allowed_capabilities.append(SAFE_UNION_COLLAPSE)
```

需要添加导入:

```python
from .union_utils import (
    contains_union,
    is_union_wrapper_pattern,
    validate_union_safety,
)
```

- [ ] **Step 5: 测试**

Run: `PYTHONPATH=python python3 -c "from sqlopt.platforms.sql.patch_safety import SAFE_UNION_COLLAPSE; print(f'Capability: {SAFE_UNION_COLLAPSE}')"`
Expected: Capability: SAFE_UNION_COLLAPSE

- [ ] **Step 6: 提交**

```bash
git add python/sqlopt/platforms/sql/patch_safety.py
git commit -m "feat: add SAFE_UNION_COLLAPSE capability to patch_safety

- Add capability constant
- Add capability detection logic

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering)"
```

---

## 任务 5: 注册策略 - patch_strategy_registry.py

**Files:**
- Modify: `python/sqlopt/platforms/sql/patch_strategy_registry.py`

- [ ] **Step 1: 添加导入**

```python
from .union_collapse_strategy import SafeUnionCollapseStrategy
```

- [ ] **Step 2: 在 iter_patch_strategies 中注册**

在函数开头添加:

```python
RegisteredPatchStrategy(
    strategy_type=SafeUnionCollapseStrategy.strategy_type,
    priority=250,  # 高于 WRAPPER_COLLAPSE (200)
    required_capability=SafeUnionCollapseStrategy.required_capability,
    implementation=SafeUnionCollapseStrategy(),
),
```

- [ ] **Step 3: 测试**

Run: `PYTHONPATH=python python3 -c "
from sqlopt.platforms.sql.patch_strategy_registry import iter_patch_strategies
strategies = iter_patch_strategies()
union_strategy = [s for s in strategies if s.strategy_type == 'SAFE_UNION_COLLAPSE']
print(f'Found: {len(union_strategy)} UNION strategy')
print(f'Priority: {union_strategy[0].priority if union_strategy else \"N/A\"}')
"`
Expected: Found: 1 UNION strategy

- [ ] **Step 4: 提交**

```bash
git add python/sqlopt/platforms/sql/patch_strategy_registry.py
git commit -m "feat: register SafeUnionCollapseStrategy in patch_strategy_registry

- Add strategy with priority 250
- Higher than WRAPPER_COLLAPSE (200)

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering)"
```

---

## 任务 6: 注册 Family - registry.py

**Files:**
- Modify: `python/sqlopt/patch_families/registry.py`

- [ ] **Step 1: 添加导入**

```python
from .specs.static_union_collapse import STATIC_UNION_COLLAPSE_SPEC
```

- [ ] **Step 2: 在 _FAMILY_REGISTRY 中注册**

```python
_FAMILY_REGISTRY = {
    # ... existing
    "STATIC_UNION_COLLAPSE": STATIC_UNION_COLLAPSE_SPEC,
}
```

- [ ] **Step 3: 测试**

Run: `PYTHONPATH=python python3 -c "
from sqlopt.patch_families.registry import lookup_patch_family_spec
family = lookup_patch_family_spec('STATIC_UNION_COLLAPSE')
print(f'Found: {family.family if family else \"None\"}')
print(f'Status: {family.status if family else \"N/A\"}')
"`
Expected: Found: STATIC_UNION_COLLAPSE

- [ ] **Step 4: 提交**

```bash
git add python/sqlopt/patch_families/registry.py
git commit -m "feat: register STATIC_UNION_COLLAPSE in family registry

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering)"
```

---

## 任务 7: 单元测试

**Files:**
- Create: `tests/test_union_collapse.py`

- [ ] **Step 1: 创建测试文件**

```python
"""UNION Collapse 单元测试"""

import pytest
from sqlopt.platforms.sql.union_utils import (
    contains_union,
    detect_union_type,
    validate_union_safety,
    has_nested_union,
    is_union_wrapper_pattern,
)


class TestContainsUnion:
    def test_contains_union_all(self):
        assert contains_union("SELECT * FROM t1 UNION ALL SELECT * FROM t2") is True

    def test_contains_union(self):
        assert contains_union("SELECT * FROM t1 UNION SELECT * FROM t2") is True

    def test_no_union(self):
        assert contains_union("SELECT * FROM t1") is False

    def test_empty_string(self):
        assert contains_union("") is False

    def test_none(self):
        assert contains_union(None) is False


class TestDetectUnionType:
    def test_union_all(self):
        assert detect_union_type("SELECT * FROM t1 UNION ALL SELECT * FROM t2") == "UNION ALL"

    def test_union(self):
        assert detect_union_type("SELECT * FROM t1 UNION SELECT * FROM t2") == "UNION"

    def test_no_union(self):
        assert detect_union_type("SELECT * FROM t1") == "NONE"

    def test_empty(self):
        assert detect_union_type("") == "NONE"


class TestValidateUnionSafety:
    def test_safe_union_all(self):
        is_safe, reason = validate_union_safety("SELECT a FROM t1 UNION ALL SELECT b FROM t2")
        assert is_safe is True
        assert reason is None

    def test_safe_union(self):
        is_safe, reason = validate_union_safety("SELECT a FROM t1 UNION SELECT b FROM t2")
        assert is_safe is True
        assert reason is None

    def test_nested_union_unsafe(self):
        sql = "SELECT a FROM t1 UNION SELECT b FROM t2 UNION SELECT c FROM t3"
        is_safe, reason = validate_union_safety(sql)
        assert is_safe is False
        assert reason == "NESTED_UNION_NOT_SUPPORTED"

    def test_for_update_unsafe(self):
        sql = "SELECT * FROM t1 UNION ALL SELECT * FROM t2 FOR UPDATE"
        is_safe, reason = validate_union_safety(sql)
        assert is_safe is False
        assert reason == "FOR_UPDATE_NOT_SUPPORTED"

    def test_distinct_unsafe(self):
        sql = "SELECT DISTINCT a FROM t1 UNION ALL SELECT b FROM t2"
        is_safe, reason = validate_union_safety(sql)
        assert is_safe is False
        assert reason == "DISTINCT_SEMANTICS_MAY_DIFFER"


class TestHasNestedUnion:
    def test_single_union(self):
        assert has_nested_union("SELECT a FROM t1 UNION SELECT b FROM t2") is False

    def test_nested_union(self):
        assert has_nested_union("SELECT a FROM t1 UNION SELECT b FROM t2 UNION SELECT c FROM t3") is True

    def test_union_all_count_once(self):
        # UNION ALL should not be counted as nested
        assert has_nested_union("SELECT a FROM t1 UNION ALL SELECT b FROM t2") is False


class TestIsUnionWrapperPattern:
    def test_wrapper_pattern(self):
        sql = "SELECT * FROM (SELECT a FROM t1 UNION ALL SELECT b FROM t2) tmp"
        assert is_union_wrapper_pattern(sql) is True

    def test_non_wrapper(self):
        sql = "SELECT a FROM t1 UNION ALL SELECT b FROM t2"
        assert is_union_wrapper_pattern(sql) is False

    def test_empty(self):
        assert is_union_wrapper_pattern("") is False
```

- [ ] **Step 2: 运行测试**

Run: `PYTHONPATH=python python3 -m pytest tests/test_union_collapse.py -v`
Expected: 15 passed

- [ ] **Step 3: 提交**

```bash
git add tests/test_union_collapse.py
git commit -m "test: add unit tests for UNION collapse feature

- Test contains_union
- Test detect_union_type
- Test validate_union_safety
- Test has_nested_union
- Test is_union_wrapper_pattern

15 tests total

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering)"
```

---

## 任务 8: 集成测试 - Strategy 测试

**Files:**
- Modify: `tests/test_patch_strategy_planner.py` 或新建 `tests/test_union_collapse_strategy.py`

- [ ] **Step 1: 创建策略测试**

```python
"""UNION Collapse Strategy 集成测试"""

import pytest
from unittest.mock import MagicMock
from sqlopt.platforms.sql.union_collapse_strategy import SafeUnionCollapseStrategy


class TestSafeUnionCollapseStrategy:
    def test_plan_returns_none_when_no_union(self):
        """没有 UNION 时应返回 None"""
        strategy = SafeUnionCollapseStrategy()

        sql_unit = {
            "sqlKey": "test.UserMapper.findAll",
            "xmlPath": "test.xml",
            "templateSql": "SELECT * FROM users",
        }

        result = strategy.plan(
            sql_unit=sql_unit,
            rewritten_sql="SELECT * FROM users WHERE status = 1",
            fragment_catalog={},
            enable_fragment_materialization=False,
            fallback_from=None,
            dynamic_candidate_intent=None,
        )

        assert result is None

    def test_plan_returns_none_when_nested_union(self):
        """嵌套 UNION 时应返回 None"""
        strategy = SafeUnionCollapseStrategy()

        sql_unit = {
            "sqlKey": "test.UserMapper.findAll",
            "xmlPath": "test.xml",
            "templateSql": "SELECT * FROM (SELECT a FROM t1 UNION SELECT b FROM t2 UNION SELECT c FROM t3) tmp",
        }

        result = strategy.plan(
            sql_unit=sql_unit,
            rewritten_sql="SELECT a FROM t1 UNION SELECT b FROM t2 UNION SELECT c FROM t3",
            fragment_catalog={},
            enable_fragment_materialization=False,
            fallback_from=None,
            dynamic_candidate_intent=None,
        )

        assert result is None

    def test_strategy_type(self):
        """验证策略类型"""
        strategy = SafeUnionCollapseStrategy()
        assert strategy.strategy_type == "SAFE_UNION_COLLAPSE"

    def test_required_capability(self):
        """验证所需 capability"""
        strategy = SafeUnionCollapseStrategy()
        assert strategy.required_capability == "SAFE_UNION_COLLAPSE"
```

- [ ] **Step 2: 运行测试**

Run: `PYTHONPATH=python python3 -m pytest tests/test_union_collapse_strategy.py -v`
Expected: 4 passed

- [ ] **Step 3: 提交**

```bash
git add tests/test_union_collapse_strategy.py
git commit -m "test: add integration tests for SafeUnionCollapseStrategy

- Test plan returns None when no union
- Test plan returns None when nested union
- Verify strategy_type
- Verify required_capability

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering)"
```

---

## 任务 9: 最终验证

- [ ] **Step 1: 运行所有 UNION 相关测试**

Run: `PYTHONPATH=python python3 -m pytest tests/ -k "union" -v`
Expected: All passed

- [ ] **Step 2: 验证 Family 注册**

Run: `PYTHONPATH=python python3 -c "
from sqlopt.patch_families.registry import list_registered_patch_families
families = list_registered_patch_families()
union_families = [f for f in families if 'UNION' in f.family.upper()]
print(f'UNION Families: {len(union_families)}')
for f in union_families:
    print(f'  - {f.family}: {f.status}')
"`
Expected: UNION Families: 1

- [ ] **Step 3: 提交最终更改**

```bash
git status
git add -A
git commit -m "feat: implement UNION collapse feature

- Add union_utils.py with common UNION utilities
- Add SafeUnionCollapseStrategy
- Add STATIC_UNION_COLLAPSE Family Spec
- Register strategy and family
- Add comprehensive unit and integration tests

Closes: #<issue-number>

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering)"
```

---

## 实现完成检查清单

- [ ] 任务 1: union_utils.py 创建完成
- [ ] 任务 2: union_collapse_strategy.py 创建完成
- [ ] 任务 3: static_union_collapse.py 创建完成
- [ ] 任务 4: patch_safety.py 扩展完成
- [ ] 任务 5: patch_strategy_registry.py 注册完成
- [ ] 任务 6: registry.py 注册完成
- [ ] 任务 7: 单元测试完成
- [ ] 任务 8: 集成测试完成
- [ ] 任务 9: 最终验证通过