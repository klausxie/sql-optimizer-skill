# JOIN 优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 4 种 JOIN 优化 family：LEFT→INNER 转换、JOIN 消除、JOIN 重排、JOIN 合并

**Architecture:** 采用 LLM 主导 + 规则安全门的架构。每个优化特性包含：工具函数、Capability Rule、Family Spec、单元测试。按照 A→B→C→D 顺序实现。

**Tech Stack:** Python, sqlparse, 现有 Capability Rule 框架, 现有 Family Spec 框架

---

## 文件结构

```
python/sqlopt/platforms/sql/
├── join_utils.py                          # 通用 JOIN 工具函数（新建）
├── patch_capability_rules/
│   ├── safe_join_left_to_inner.py        # A: LEFT→INNER（新建）
│   ├── safe_join_elimination.py          # B: JOIN 消除（新建）
│   ├── safe_join_reordering.py            # C: JOIN 重排（新建）
│   └── safe_join_consolidation.py        # D: JOIN 合并（新建）
└── materialization_constants.py          # 添加新的 materialization mode（修改）

python/sqlopt/patch_families/specs/
├── static_join_left_to_inner.py          # A: Family Spec（新建）
├── static_join_elimination.py            # B: Family Spec（新建）
├── static_join_reordering.py             # C: Family Spec（新建）
└── static_join_consolidation.py          # D: Family Spec（新建）

python/sqlopt/patch_families/registry.py  # 注册新 family（修改）

tests/
└── test_join_*.py                        # 单元测试（新建）
```

---

## 实现顺序

先实现特性 A（LEFT→INNER），然后 B、C、D 按相同模式实现。

---

## 特性 A: LEFT→INNER JOIN 转换

### Task A1: 创建 JOIN 工具函数模块

**Files:**
- Create: `python/sqlopt/platforms/sql/join_utils.py`

- [ ] **Step 1: 创建 join_utils.py 模块**

```python
"""JOIN 工具函数模块

提供 JOIN 分析和转换的通用功能。
"""

from __future__ import annotations
from enum import Enum
from typing import Optional


class JoinType(Enum):
    """JOIN 类型枚举"""
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL OUTER"
    CROSS = "CROSS"
    # 未来可扩展
    # CROSS_APPLY = "CROSS APPLY"
    # LATERAL = "LATERAL"


def contains_join(sql: str) -> bool:
    """检测 SQL 是否包含 JOIN"""
    sql_upper = sql.upper()
    join_keywords = [" JOIN ", " INNER JOIN ", " LEFT JOIN ", " RIGHT JOIN ", " FULL JOIN ", " CROSS JOIN "]
    return any(keyword in sql_upper for keyword in join_keywords)


def detect_join_type(sql: str) -> Optional[JoinType]:
    """检测 JOIN 类型"""
    sql_upper = sql.upper()
    if " LEFT JOIN " in sql_upper:
        return JoinType.LEFT
    elif " RIGHT JOIN " in sql_upper:
        return JoinType.RIGHT
    elif " FULL JOIN " in sql_upper:
        return JoinType.FULL
    elif " CROSS JOIN " in sql_upper:
        return JoinType.CROSS
    elif " JOIN " in sql_upper:
        return JoinType.INNER
    return None


def extract_join_tables(sql: str) -> list[str]:
    """提取 SQL 中所有被 JOIN 的表名"""
    import re
    # 匹配 JOIN ... ON 或 JOIN ... USING
    pattern = r'(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN\s+(\w+)\s+(?:ON|USING)'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return matches


def has_not_null_condition(sql: str, table_name: str) -> bool:
    """检测 WHERE 条件是否保证非空"""
    sql_upper = sql.upper()
    # 检查 IS NOT NULL 条件
    patterns = [
        rf'{table_name}\.\w+\s+IS\s+NOT\s+NULL',
        rf'{table_name}\.\w+\s+!=\s*NULL',
        rf'{table_name}\.\w+\s+<>\s*NULL',
        rf'IS\s+NOT\s+NULL\s*\(\s*{table_name}\.\w+\s*\)',
    ]
    import re
    for pattern in patterns:
        if re.search(pattern, sql_upper):
            return True
    return False


def left_to_inner_rewrite(sql: str) -> Optional[str]:
    """将 LEFT JOIN 转换为 INNER JOIN

    当 WHERE 条件保证非空时执行转换。
    返回转换后的 SQL，如果不适用则返回 None。
    """
    if not contains_join(sql):
        return None

    join_type = detect_join_type(sql)
    if join_type != JoinType.LEFT:
        return None

    # 提取被 JOIN 的表
    join_tables = extract_join_tables(sql)
    if not join_tables:
        return None

    # 检查是否有 NOT NULL 条件
    for table in join_tables:
        if has_not_null_condition(sql, table):
            # 执行转换
            sql = sql.upper()
            sql = sql.replace("LEFT JOIN", "INNER JOIN")
            return sql

    return None
```

- [ ] **Step 2: 运行测试验证模块可导入**

```bash
cd /Users/klaus/Desktop/sql-optimizer-skill
python3 -c "from sqlopt.platforms.sql.join_utils import contains_join, detect_join_type, left_to_inner_rewrite; print('Import OK')"
```

Expected: 输出 "Import OK"

- [ ] **Step 3: Commit**

```bash
git add python/sqlopt/platforms/sql/join_utils.py
git commit -m "feat: add join_utils module with basic JOIN analysis functions"
```

---

### Task A2: 创建 LEFT→INNER Capability Rule

**Files:**
- Create: `python/sqlopt/platforms/sql/patch_capability_rules/safe_join_left_to_inner.py`
- Modify: `python/sqlopt/platforms/sql/patch_capability_rules/__init__.py`

- [ ] **Step 1: 创建 safe_join_left_to_inner.py**

```python
"""Safe LEFT to INNER JOIN Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeJoinLeftToInnerCapability:
    """LEFT JOIN 转 INNER JOIN 能力规则

    检查是否可以将 LEFT JOIN 转换为 INNER JOIN。
    """

    capability = "SAFE_JOIN_LEFT_TO_INNER"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        # 检查通用语义门失败
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=270,
                reason=semantic_failures[0],
            )

        # 检查是否存在有效变化
        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=270)

        # 没有有效变化，不允许
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=270,
            reason="NO_EFFECTIVE_CHANGE",
        )
```

- [ ] **Step 2: 注册到 __init__.py**

Modify `python/sqlopt/platforms/sql/patch_capability_rules/__init__.py`:

在文件末尾添加导入和注册：

```python
from .safe_join_left_to_inner import SafeJoinLeftToInnerCapability
```

更新 CAPABILITY_PRIORITIES 字典：

```python
CAPABILITY_PRIORITIES = {
    # ... existing capabilities ...
    "SAFE_JOIN_LEFT_TO_INNER": 270,
}
```

- [ ] **Step 3: 运行测试验证**

```bash
cd /Users/klaus/Desktop/sql-optimizer-skill
python3 -c "from sqlopt.platforms.sql.patch_capability_rules import SafeJoinLeftToInnerCapability; print('Import OK')"
```

Expected: 输出 "Import OK"

- [ ] **Step 4: Commit**

```bash
git add python/sqlopt/platforms/sql/patch_capability_rules/safe_join_left_to_inner.py python/sqlopt/platforms/sql/patch_capability_rules/__init__.py
git commit -m "feat: add SafeJoinLeftToInnerCapability rule (priority 270)"
```

---

### Task A3: 创建 LEFT→INNER Family Spec

**Files:**
- Create: `python/sqlopt/patch_families/specs/static_join_left_to_inner.py`
- Modify: `python/sqlopt/patch_families/registry.py`
- Modify: `python/sqlopt/platforms/sql/materialization_constants.py`

- [ ] **Step 1: 创建 static_join_left_to_inner.py**

```python
"""STATIC_JOIN_LEFT_TO_INNER Family Spec

LEFT JOIN 转 INNER JOIN Family 定义
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

STATIC_JOIN_LEFT_TO_INNER_SPEC = PatchFamilySpec(
    family="STATIC_JOIN_LEFT_TO_INNER",
    status="MVP_STATIC_BASELINE",
    stage="MVP_STATIC_BASELINE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="SAFE_JOIN_LEFT_TO_INNER",
        requires_replay_contract=True,
        materialization_modes=("STATEMENT_TEMPLATE_SAFE_JOIN_LEFT_TO_INNER",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="STATEMENT_TEMPLATE_SAFE_JOIN_LEFT_TO_INNER",
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

- [ ] **Step 2: 添加 materialization constant**

Modify `python/sqlopt/platforms/sql/materialization_constants.py`:

添加新的 materialization mode：

```python
STATEMENT_TEMPLATE_SAFE_JOIN_LEFT_TO_INNER = "STATEMENT_TEMPLATE_SAFE_JOIN_LEFT_TO_INNER"
```

添加到 TEMPLATE_SAFE_MODES 集合：

```python
TEMPLATE_SAFE_MODES = {
    # ... existing modes ...
    STATEMENT_TEMPLATE_SAFE_JOIN_LEFT_TO_INNER,
}
```

添加 reason code：

```python
REASON_JOIN_LEFT_TO_INNER_SAFE = "JOIN_LEFT_TO_INNER_SAFE"
```

- [ ] **Step 3: 注册到 registry.py**

Modify `python/sqlopt/patch_families/registry.py`:

添加导入：

```python
from .specs.static_join_left_to_inner import STATIC_JOIN_LEFT_TO_INNER_SPEC
```

注册：

```python
FAMILY_REGISTRY = [
    # ... existing families ...
    STATIC_JOIN_LEFT_TO_INNER_SPEC,
]
```

- [ ] **Step 4: 运行测试验证**

```bash
cd /Users/klaus/Desktop/sql-optimizer-skill
python3 -c "from sqlopt.patch_families.specs.static_join_left_to_inner import STATIC_JOIN_LEFT_TO_INNER_SPEC; print('Import OK')"
```

Expected: 输出 "Import OK"

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/patch_families/specs/static_join_left_to_inner.py python/sqlopt/patch_families/registry.py python/sqlopt/platforms/sql/materialization_constants.py
git commit -m "feat: add STATIC_JOIN_LEFT_TO_INNER family spec"
```

---

### Task A4: 创建 LEFT→INNER 单元测试

**Files:**
- Create: `tests/test_join_left_to_inner.py`

- [ ] **Step 1: 创建单元测试文件**

```python
"""LEFT→INNER JOIN 转换单元测试"""

import pytest
from sqlopt.platforms.sql.join_utils import (
    contains_join,
    detect_join_type,
    extract_join_tables,
    has_not_null_condition,
    left_to_inner_rewrite,
    JoinType,
)


class TestContainsJoin:
    def test_contains_left_join(self):
        assert contains_join("SELECT * FROM a LEFT JOIN b ON a.id = b.id") is True

    def test_contains_inner_join(self):
        assert contains_join("SELECT * FROM a INNER JOIN b ON a.id = b.id") is True

    def test_contains_no_join(self):
        assert contains_join("SELECT * FROM a WHERE id = 1") is False


class TestDetectJoinType:
    def test_detect_left_join(self):
        result = detect_join_type("SELECT * FROM a LEFT JOIN b ON a.id = b.id")
        assert result == JoinType.LEFT

    def test_detect_inner_join(self):
        result = detect_join_type("SELECT * FROM a INNER JOIN b ON a.id = b.id")
        assert result == JoinType.INNER

    def test_detect_right_join(self):
        result = detect_join_type("SELECT * FROM a RIGHT JOIN b ON a.id = b.id")
        assert result == JoinType.RIGHT

    def test_detect_no_join(self):
        result = detect_join_type("SELECT * FROM a WHERE id = 1")
        assert result is None


class TestExtractJoinTables:
    def test_extract_single_join(self):
        result = extract_join_tables("SELECT * FROM a LEFT JOIN b ON a.id = b.id")
        assert "b" in result

    def test_extract_multiple_joins(self):
        result = extract_join_tables("SELECT * FROM a LEFT JOIN b ON a.id = b.id LEFT JOIN c ON a.id = c.id")
        assert "b" in result
        assert "c" in result


class TestHasNotNullCondition:
    def test_has_is_not_null(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.id IS NOT NULL"
        assert has_not_null_condition(sql, "b") is True

    def test_has_not_equals_null(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.id != NULL"
        assert has_not_null_condition(sql, "b") is True

    def test_no_not_null_condition(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.status = 1"
        assert has_not_null_condition(sql, "b") is False


class TestLeftToInnerRewrite:
    def test_rewrite_left_to_inner(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.id IS NOT NULL"
        result = left_to_inner_rewrite(sql)
        assert result is not None
        assert "INNER JOIN" in result
        assert "LEFT JOIN" not in result

    def test_no_rewrite_without_not_null(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id WHERE b.status = 1"
        result = left_to_inner_rewrite(sql)
        assert result is None

    def test_no_rewrite_inner_join(self):
        sql = "SELECT * FROM a INNER JOIN b ON a.id = b.id"
        result = left_to_inner_rewrite(sql)
        assert result is None
```

- [ ] **Step 2: 运行测试**

```bash
cd /Users/klaus/Desktop/sql-optimizer-skill
python3 -m pytest tests/test_join_left_to_inner.py -v
```

Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add tests/test_join_left_to_inner.py
git commit -m "test: add LEFT→INNER JOIN conversion unit tests"
```

---

## 特性 B: JOIN 消除

### Task B1: 扩展 join_utils.py 添加消除功能

**Files:**
- Modify: `python/sqlopt/platforms/sql/join_utils.py`

- [ ] **Step 1: 添加 JOIN 消除相关函数**

在 join_utils.py 中添加：

```python
def get_select_columns(sql: str) -> list[str]:
    """提取 SELECT 子句中的列"""
    import re
    # 提取 SELECT ... FROM 之间的内容
    match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    select_part = match.group(1)
    if select_part.strip() == '*':
        return ['*']
    # 分割列名
    columns = [col.strip().split()[-1] for col in select_part.split(',')]
    return columns


def is_join_table_used(sql: str, table_name: str) -> bool:
    """检查被 JOIN 的表���否在查询中被使用

    检查 SELECT、WHERE、ORDER BY、GROUP BY、HAVING 等子句
    """
    import re
    sql_upper = sql.upper()

    # 提取完整的查询（去掉 JOIN...ON 部分后）
    # 这里简化处理，实际需要更复杂的解析

    # 检查是否在 SELECT 中使用
    select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_part = select_match.group(1).upper()
        if table_name.upper() in select_part and f'{table_name}.' in sql_upper:
            return True

    # 检查是否在 WHERE 中使用（排除 JOIN...ON 条件）
    where_match = re.search(r'WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
    if where_match:
        where_part = where_match.group(1).upper()
        # 排除 ON 条件
        on_match = re.search(r'ON\s+.+?(?=\s+WHERE|\s+GROUP|\s+ORDER|\s+LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        if on_match:
            on_part = on_match.group(0).upper()
            where_part = where_part.replace(on_part, '')
        if f'{table_name.upper()}.' in where_part:
            return True

    return False


def join_elimination_candidate(sql: str) -> Optional[dict]:
    """检测 JOIN 消除候选

    返回候选信息或 None
    """
    if not contains_join(sql):
        return None

    # 提取所有被 JOIN 的表
    join_tables = extract_join_tables(sql)
    if not join_tables:
        return None

    for table in join_tables:
        # 如果表没有被使用，可能是消除候选
        if not is_join_table_used(sql, table):
            return {
                "table": table,
                "reason": "UNUSED_TABLE",
            }

    return None
```

- [ ] **Step 2: 运行测试**

```bash
cd /Users/klaus/Desktop/sql-optimizer-skill
python3 -c "from sqlopt.platforms.sql.join_utils import join_elimination_candidate; print('Import OK')"
```

Expected: 输出 "Import OK"

- [ ] **Step 3: Commit**

```bash
git add python/sqlopt/platforms/sql/join_utils.py
git commit -m "feat: add JOIN elimination detection functions"
```

---

### Task B2: 创建 JOIN 消除 Capability Rule

**Files:**
- Create: `python/sqlopt/platforms/sql/patch_capability_rules/safe_join_elimination.py`
- Modify: `python/sqlopt/platforms/sql/patch_capability_rules/__init__.py`

- [ ] **Step 1: 创建 safe_join_elimination.py**

```python
"""Safe JOIN Elimination Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeJoinEliminationCapability:
    """JOIN 消除能力规则

    检查是否可以消除不必要的 JOIN。
    """

    capability = "SAFE_JOIN_ELIMINATION"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        # 检查通用语义门失败
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=265,
                reason=semantic_failures[0],
            )

        # 检查是否存在有效变化
        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=265)

        # 没有有效变化，不允许
        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=265,
            reason="NO_EFFECTIVE_CHANGE",
        )
```

- [ ] **Step 2: 注册到 __init__.py**

添加导入和更新优先级：

```python
from .safe_join_elimination import SafeJoinEliminationCapability
```

更新 CAPABILITY_PRIORITIES：

```python
CAPABILITY_PRIORITIES = {
    # ... existing priorities ...
    "SAFE_JOIN_ELIMINATION": 265,
}
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/klaus/Desktop/sql-optimizer-skill
python3 -c "from sqlopt.platforms.sql.patch_capability_rules import SafeJoinEliminationCapability; print('Import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add python/sqlopt/platforms/sql/patch_capability_rules/safe_join_elimination.py python/sqlopt/platforms/sql/patch_capability_rules/__init__.py
git commit -m "feat: add SafeJoinEliminationCapability rule (priority 265)"
```

---

### Task B3: 创建 JOIN 消除 Family Spec

**Files:**
- Create: `python/sqlopt/patch_families/specs/static_join_elimination.py`
- Modify: `python/sqlopt/patch_families/registry.py`
- Modify: `python/sqlopt/platforms/sql/materialization_constants.py`

- [ ] **Step 1: 创建 static_join_elimination.py**

```python
"""STATIC_JOIN_ELIMINATION Family Spec

JOIN 消除 Family 定义
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

STATIC_JOIN_ELIMINATION_SPEC = PatchFamilySpec(
    family="STATIC_JOIN_ELIMINATION",
    status="MVP_STATIC_BASELINE",
    stage="MVP_STATIC_BASELINE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="SAFE_JOIN_ELIMINATION",
        requires_replay_contract=True,
        materialization_modes=("STATEMENT_TEMPLATE_SAFE_JOIN_ELIMINATION",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="STATEMENT_TEMPLATE_SAFE_JOIN_ELIMINATION",
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

- [ ] **Step 2: 添加 materialization constants**

```python
STATEMENT_TEMPLATE_SAFE_JOIN_ELIMINATION = "STATEMENT_TEMPLATE_SAFE_JOIN_ELIMINATION"
REASON_JOIN_ELIMINATION_SAFE = "JOIN_ELIMINATION_SAFE"
```

- [ ] **Step 3: 注册到 registry.py**

```python
from .specs.static_join_elimination import STATIC_JOIN_ELIMINATION_SPEC
```

添加到 FAMILY_REGISTRY

- [ ] **Step 4: Commit**

```bash
git add python/sqlopt/patch_families/specs/static_join_elimination.py python/sqlopt/patch_families/registry.py python/sqlopt/platforms/sql/materialization_constants.py
git commit -m "feat: add STATIC_JOIN_ELIMINATION family spec"
```

---

### Task B4: 创建 JOIN 消除单元测试

**Files:**
- Create: `tests/test_join_elimination.py`

- [ ] **Step 1: 创建单元测试**

```python
"""JOIN 消除单元测试"""

import pytest
from sqlopt.platforms.sql.join_utils import (
    get_select_columns,
    is_join_table_used,
    join_elimination_candidate,
)


class TestGetSelectColumns:
    def test_simple_columns(self):
        sql = "SELECT id, name FROM users"
        result = get_select_columns(sql)
        assert "id" in result
        assert "name" in result

    def test_star_select(self):
        sql = "SELECT * FROM users"
        result = get_select_columns(sql)
        assert result == ['*']

    def test_qualified_columns(self):
        sql = "SELECT u.id, u.name FROM users u"
        result = get_select_columns(sql)
        assert "id" in result
        assert "name" in result


class TestIsJoinTableUsed:
    def test_table_in_select(self):
        sql = "SELECT u.id, u.name FROM users u JOIN orders o ON u.id = o.user_id"
        assert is_join_table_used(sql, "o") is True

    def test_table_not_used(self):
        sql = "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id"
        assert is_join_table_used(sql, "o") is False


class TestJoinEliminationCandidate:
    def test_candidate_found(self):
        sql = "SELECT u.id FROM users u JOIN orders o ON u.id = o.user_id"
        result = join_elimination_candidate(sql)
        assert result is not None
        assert result["table"] == "o"
        assert result["reason"] == "UNUSED_TABLE"

    def test_no_candidate(self):
        sql = "SELECT u.id, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        result = join_elimination_candidate(sql)
        assert result is None

    def test_no_join(self):
        sql = "SELECT id FROM users WHERE id = 1"
        result = join_elimination_candidate(sql)
        assert result is None
```

- [ ] **Step 2: 运行测试**

```bash
cd /Users/klaus/Desktop/sql-optimizer-skill
python3 -m pytest tests/test_join_elimination.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_join_elimination.py
git commit -m "test: add JOIN elimination unit tests"
```

---

## 特性 C: JOIN 重排

### Task C1: 添加 JOIN 重排功能到 join_utils

- [ ] **Step 1: 添加 JOIN 重排相关函数**

```python
def get_join_order(sql: str) -> list[str]:
    """获取 JOIN 的顺序（表列表）"""
    import re
    # 提取 FROM 子句后的所有表
    pattern = r'FROM\s+(\w+)\s*(?:\w+)?.*?(?:JOIN\s+(\w+))?'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    tables = []
    for match in matches:
        if match[0]:
            tables.append(match[0])
        if match[1]:
            tables.append(match[1])
    return tables


def can_reorder_joins(sql: str) -> bool:
    """检查 JOIN 是否可以重排

    目前检查是否有阻止重排的条件
    """
    # 简化版本：只检查是否有复杂条件
    import re
    # 检查是否有 UNION、DISTINCT、GROUP BY 等可能阻止重排
    blockers = ['UNION', 'DISTINCT', 'GROUP BY', 'HAVING']
    sql_upper = sql.upper()
    for blocker in blockers:
        if blocker in sql_upper:
            return False
    return True
```

- [ ] **Step 2: Commit**

```bash
git add python/sqlopt/platforms/sql/join_utils.py
git commit -m "feat: add JOIN reordering detection functions"
```

---

### Task C2: 创建 JOIN 重排 Capability Rule

- [ ] **Step 1: 创建 safe_join_reordering.py**

```python
"""Safe JOIN Reordering Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeJoinReorderingCapability:
    """JOIN 重排能力规则"""

    capability = "SAFE_JOIN_REORDERING"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=260,
                reason=semantic_failures[0],
            )

        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=260)

        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=260,
            reason="NO_EFFECTIVE_CHANGE",
        )
```

- [ ] **Step 2: 注册并 Commit**

```bash
git add python/sqlopt/platforms/sql/patch_capability_rules/safe_join_reordering.py python/sqlopt/platforms/sql/patch_capability_rules/__init__.py
git commit -m "feat: add SafeJoinReorderingCapability (priority 260)"
```

---

### Task C3: 创建 JOIN 重排 Family Spec

- [ ] **Step 1: 创建 static_join_reordering.py**

```python
"""STATIC_JOIN_REORDERING Family Spec"""

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

STATIC_JOIN_REORDERING_SPEC = PatchFamilySpec(
    family="STATIC_JOIN_REORDERING",
    status="MVP_STATIC_BASELINE",
    stage="MVP_STATIC_BASELINE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="SAFE_JOIN_REORDERING",
        requires_replay_contract=True,
        materialization_modes=("STATEMENT_TEMPLATE_SAFE_JOIN_REORDERING",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="STATEMENT_TEMPLATE_SAFE_JOIN_REORDERING",
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

- [ ] **Step 2: 添加 materialization constants 并注册**

```python
STATEMENT_TEMPLATE_SAFE_JOIN_REORDERING = "STATEMENT_TEMPLATE_SAFE_JOIN_REORDERING"
REASON_JOIN_REORDERING_SAFE = "JOIN_REORDERING_SAFE"
```

- [ ] **Step 3: Commit**

```bash
git add python/sqlopt/patch_families/specs/static_join_reordering.py python/sqlopt/patch_families/registry.py python/sqlopt/platforms/sql/materialization_constants.py
git commit -m "feat: add STATIC_JOIN_REORDERING family spec"
```

---

### Task C4: 创建 JOIN 重排单元测试

- [ ] **Step 1: 创建测试文件**

```python
"""JOIN 重排单元测试"""

import pytest
from sqlopt.platforms.sql.join_utils import get_join_order, can_reorder_joins


class TestGetJoinOrder:
    def test_simple_joins(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id JOIN c ON b.id = c.id"
        result = get_join_order(sql)
        assert len(result) >= 2


class TestCanReorderJoins:
    def test_can_reorder(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id JOIN c ON b.id = c.id"
        assert can_reorder_joins(sql) is True

    def test_cannot_reorder_with_union(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id UNION SELECT * FROM c"
        assert can_reorder_joins(sql) is False

    def test_cannot_reorder_with_group_by(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id GROUP BY a.id"
        assert can_reorder_joins(sql) is False
```

- [ ] **Step 2: 运行测试并 Commit**

```bash
python3 -m pytest tests/test_join_reordering.py -v
git add tests/test_join_reordering.py
git commit -m "test: add JOIN reordering unit tests"
```

---

## 特性 D: JOIN 合并

### Task D1: 添加 JOIN 合并功能到 join_utils

- [ ] **Step 1: 添加合并检测函数**

```python
def find_consolidation_candidates(sql: str) -> Optional[list[dict]]:
    """查找可以合并的 JOIN 候选

    检测多个小表是否连接到同一个主表
    """
    if not contains_join(sql):
        return None

    import re
    # 查找所有 JOIN 及其 ON 条件
    pattern = r'(\w+)\s+JOIN\s+(\w+)\s+(?:AS\s+)?(\w+)?\s+ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
    matches = re.findall(pattern, sql, re.IGNORECASE)

    if len(matches) < 2:
        return None

    # 按连接的列分组
    connection_map = {}
    for match in matches:
        left_table = match[3] if match[3] else match[1]
        right_table = match[5] if match[5] else match[2]
        join_key = match[4]

        key = (left_table, join_key)
        if key not in connection_map:
            connection_map[key] = []
        connection_map[key].append({
            "join_type": match[0],
            "table": right_table,
        })

    # 找出连接到同一个表的多个 JOIN
    candidates = []
    for key, joins in connection_map.items():
        if len(joins) >= 2:
            candidates.append({
                "main_table": key[0],
                "join_key": key[1],
                "tables": [j["table"] for j in joins],
            })

    return candidates if candidates else None
```

- [ ] **Step 2: Commit**

```bash
git add python/sqlopt/platforms/sql/join_utils.py
git commit -m "feat: add JOIN consolidation detection functions"
```

---

### Task D2: 创建 JOIN 合并 Capability Rule

- [ ] **Step 1: 创建 safe_join_consolidation.py**

```python
"""Safe JOIN Consolidation Capability Rule"""

from __future__ import annotations

from ..patchability_models import CapabilityDecision
from ..rewrite_facts_models import RewriteFacts
from .support import common_gate_failures


class SafeJoinConsolidationCapability:
    """JOIN 合并能力规则"""

    capability = "SAFE_JOIN_CONSOLIDATION"

    def evaluate(self, rewrite_facts: RewriteFacts) -> CapabilityDecision:
        semantic_failures = common_gate_failures(rewrite_facts)
        if semantic_failures:
            return CapabilityDecision(
                capability=self.capability,
                allowed=False,
                priority=255,
                reason=semantic_failures[0],
            )

        if rewrite_facts.effective_change:
            return CapabilityDecision(capability=self.capability, allowed=True, priority=255)

        return CapabilityDecision(
            capability=self.capability,
            allowed=False,
            priority=255,
            reason="NO_EFFECTIVE_CHANGE",
        )
```

- [ ] **Step 2: 注册并 Commit**

```bash
git add python/sqlopt/platforms/sql/patch_capability_rules/safe_join_consolidation.py python/sqlopt/platforms/sql/patch_capability_rules/__init__.py
git commit -m "feat: add SafeJoinConsolidationCapability (priority 255)"
```

---

### Task D3: 创建 JOIN 合并 Family Spec

- [ ] **Step 1: 创建 static_join_consolidation.py**

```python
"""STATIC_JOIN_CONSOLIDATION Family Spec"""

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

STATIC_JOIN_CONSOLIDATION_SPEC = PatchFamilySpec(
    family="STATIC_JOIN_CONSOLIDATION",
    status="MVP_STATIC_BASELINE",
    stage="MVP_STATIC_BASELINE",
    scope=PatchFamilyScope(
        statement_types=("SELECT",),
        requires_template_preserving=True,
        patch_surface="STATEMENT_BODY",
    ),
    acceptance=PatchFamilyAcceptancePolicy(
        semantic_required_status="PASS",
        semantic_min_confidence="HIGH",
    ),
    patch_target_policy=PatchFamilyPatchTargetPolicy(
        selected_patch_strategy="SAFE_JOIN_CONSOLIDATION",
        requires_replay_contract=True,
        materialization_modes=("STATEMENT_TEMPLATE_SAFE_JOIN_CONSOLIDATION",),
        target_type="STATEMENT",
        target_ref_policy="SQL_UNIT",
    ),
    replay=PatchFamilyReplayPolicy(
        required_template_ops=("replace_statement_body",),
        render_mode="STATEMENT_TEMPLATE_SAFE_JOIN_CONSOLIDATION",
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

- [ ] **Step 2: 添加 materialization constants 并注册**

```python
STATEMENT_TEMPLATE_SAFE_JOIN_CONSOLIDATION = "STATEMENT_TEMPLATE_SAFE_JOIN_CONSOLIDATION"
REASON_JOIN_CONSOLIDATION_SAFE = "JOIN_CONSOLIDATION_SAFE"
```

- [ ] **Step 3: Commit**

```bash
git add python/sqlopt/patch_families/specs/static_join_consolidation.py python/sqlopt/patch_families/registry.py python/sqlopt/platforms/sql/materialization_constants.py
git commit -m "feat: add STATIC_JOIN_CONSOLIDATION family spec"
```

---

### Task D4: 创建 JOIN 合并单元测试

- [ ] **Step 1: 创建测试文件**

```python
"""JOIN 合并单元测试"""

import pytest
from sqlopt.platforms.sql.join_utils import find_consolidation_candidates


class TestFindConsolidationCandidates:
    def test_candidates_found(self):
        sql = "SELECT * FROM main m LEFT JOIN a ON m.id = a.ref_id LEFT JOIN b ON m.id = b.ref_id LEFT JOIN c ON m.id = c.ref_id"
        result = find_consolidation_candidates(sql)
        assert result is not None
        assert len(result) > 0

    def test_no_candidates(self):
        sql = "SELECT * FROM a JOIN b ON a.id = b.id"
        result = find_consolidation_candidates(sql)
        assert result is None

    def test_no_join(self):
        sql = "SELECT * FROM users WHERE id = 1"
        result = find_consolidation_candidates(sql)
        assert result is None
```

- [ ] **Step 2: 运行测试并 Commit**

```bash
python3 -m pytest tests/test_join_consolidation.py -v
git add tests/test_join_consolidation.py
git commit -m "test: add JOIN consolidation unit tests"
```

---

## 集成测试

### Task E: 运行所有测试

- [ ] **Step 1: 运行所有 JOIN 相关测试**

```bash
cd /Users/klaus/Desktop/sql-optimizer-skill
python3 -m pytest tests/test_join_*.py -v
```

- [ ] **Step 2: 运行完整测试套件**

```bash
python3 -m pytest -q
```

- [ ] **Step 3: Commit 最终更改**

```bash
git add -A
git commit -m "feat: implement all 4 JOIN optimization families (A/B/C/D)"
```

---

## 总结

| 特性 | 文件 | 优先级 | 状态 |
|------|------|--------|------|
| A: LEFT→INNER | join_utils.py, safe_join_left_to_inner.py, static_join_left_to_inner.py | 270 | ⬜ |
| B: JOIN 消除 | safe_join_elimination.py, static_join_elimination.py | 265 | ⬜ |
| C: JOIN 重排 | safe_join_reordering.py, static_join_reordering.py | 260 | ⬜ |
| D: JOIN 合并 | safe_join_consolidation.py, static_join_consolidation.py | 255 | ⬜ |

Plan complete and saved to `docs/superpowers/plans/2026-03-28-join-optimization.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?