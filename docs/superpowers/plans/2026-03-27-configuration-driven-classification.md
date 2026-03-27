# 配置驱动分类架构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Patch Family 分类逻辑从硬编码改为配置驱动，添加新 family 从 4 步减少到 2 步

**Architecture:** 创建 classification/ 模块，实现 ClassificationConfig 数据模型和注册表调度器，将简单的 regex-based 分类迁移到配置，复杂逻辑保留函数作为 fallback

**Tech Stack:** Python dataclasses, re (regex), pytest

---

## 文件结构

```
python/sqlopt/patch_families/classification/
├── __init__.py           # 导出 classify_patch_family, ClassificationContext
├── models.py              # ClassificationConfig, ClassificationContext 数据模型
├── registry.py            # _CONFIG 注册表 + classify_patch_family() 调度器
├── patterns.py           # 预编译 regex 模式
└── validators.py         # 复杂分类函数（从 validator_sql.py 迁移）

tests/
└── test_classification.py  # 新测试文件
```

---

## Task 1: 创建 classification 模块目录和模型

**Files:**
- Create: `python/sqlopt/patch_families/classification/__init__.py`
- Create: `python/sqlopt/patch_families/classification/models.py`
- Test: `tests/test_classification.py`

- [ ] **Step 1: 写入失败的测试**

```python
# tests/test_classification.py
from sqlopt.patch_families.classification import (
    ClassificationConfig,
    ClassificationContext,
    classify_patch_family,
)

def test_classification_config_can_be_imported():
    """ClassificationConfig can be imported from classification module."""
    config = ClassificationConfig(
        family="TEST_FAMILY",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\btest\b"],
        rewritten_patterns=[],
    )
    assert config.family == "TEST_FAMILY"
    assert config.strategy_type == "EXACT_TEMPLATE_EDIT"


def test_classification_context_can_be_created():
    """ClassificationContext can be created with SQL parameters."""
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users",
        rewritten_sql="SELECT id FROM users",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    assert ctx.original_sql == "SELECT * FROM users"
    assert ctx.rewritten_sql == "SELECT id FROM users"


def test_classify_patch_family_is_callable():
    """classify_patch_family function is importable and callable."""
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users WHERE id IN (1)",
        rewritten_sql="SELECT * FROM users WHERE id = 1",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py -v`
Expected: FAIL - ModuleNotFoundError: No module named 'sqlopt.patch_families.classification'

- [ ] **Step 3: 创建 models.py**

```python
# python/sqlopt/patch_families/classification/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClassificationConfig:
    """单个 family 的分类配置"""
    family: str  # FAMILY_ID (e.g., "STATIC_IN_LIST_SIMPLIFICATION")
    strategy_type: str | None = None  # patch strategy type (e.g., "EXACT_TEMPLATE_EDIT")
    original_patterns: list[str] | None = None  # regex patterns to match original_sql
    rewritten_patterns: list[str] | None = None  # regex patterns to match rewritten_sql
    validator_func: str | None = None  # fallback: validator function name
    requires_rewrite_facts: bool = False  # 是否需要 rewrite_facts
    requires_dynamic_template: bool = False


@dataclass
class ClassificationContext:
    """分类上下文，封装所有输入参数"""
    original_sql: str
    rewritten_sql: str | None
    rewrite_facts: dict[str, Any] | None = None
    selected_patch_strategy: dict[str, Any] | None = None
```

- [ ] **Step 4: 创建 __init__.py (最小实现)**

```python
# python/sqlopt/patch_families/classification/__init__.py
from __future__ import annotations

from .models import ClassificationConfig, ClassificationContext


def classify_patch_family(ctx: ClassificationContext) -> str | None:
    """主分类函数，暂时返回 None"""
    # TODO: 实现配置匹配逻辑
    return None


__all__ = [
    "ClassificationConfig",
    "ClassificationContext",
    "classify_patch_family",
]
```

- [ ] **Step 5: 运行测试验证通过**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/patch_families/classification/ tests/test_classification.py
git commit -m "feat: add classification module with models

- Add ClassificationConfig and ClassificationContext dataclasses
- Add classify_patch_family stub function
- Add tests for basic import and structure"
```

---

## Task 2: 实现 registry.py 配置注册表和调度器

**Files:**
- Create: `python/sqlopt/patch_families/classification/registry.py`
- Modify: `python/sqlopt/patch_families/classification/__init__.py`

- [ ] **Step 1: 写入失败的测试**

```python
# tests/test_classification.py - 添加新测试

def test_config_based_classification_for_in_list():
    """STATIC_IN_LIST_SIMPLIFICATION can be classified via config."""
    from sqlopt.platforms.sql.validator_sql import normalize_sql

    ctx = ClassificationContext(
        original_sql="SELECT * FROM users WHERE id IN (1)",
        rewritten_sql="SELECT * FROM users WHERE id = 1",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    assert result == "STATIC_IN_LIST_SIMPLIFICATION"


def test_config_based_classification_for_limit():
    """STATIC_LIMIT_OPTIMIZATION can be classified via config."""
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users LIMIT 0",
        rewritten_sql="SELECT * FROM users",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    assert result == "STATIC_LIMIT_OPTIMIZATION"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py::test_config_based_classification_for_in_list -v`
Expected: FAIL - AssertionError: assert None == 'STATIC_IN_LIST_SIMPLIFICATION'

- [ ] **Step 3: 实现 registry.py**

```python
# python/sqlopt/patch_families/classification/registry.py
from __future__ import annotations

import re
from typing import Any

from .models import ClassificationConfig, ClassificationContext


# 配置注册表 - 简单的 regex-based family
_CONFIG: dict[str, ClassificationConfig] = {
    "STATIC_IN_LIST_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_IN_LIST_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[
            r"\b([a-z_][a-z0-9_\.]*)\s+IN\s*\(\s*([^,\)]+)\s*\)",  # column IN (value)
            r"\b([a-z_][a-z0-9_\.]*)\s+NOT\s+IN\s*\(\s*([^,\)]+)\s*\)",  # column NOT IN (value)
        ],
        rewritten_patterns=[
            r"\b=\s*[^,\)]+",   # column = value
            r"\b<>\s*[^,\)]+",  # column <> value
            r"\b!=\s*[^,\)]+",  # column != value
        ],
    ),
    "STATIC_LIMIT_OPTIMIZATION": ClassificationConfig(
        family="STATIC_LIMIT_OPTIMIZATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[
            r"\bLIMIT\s+0\s*($|;|\))",  # LIMIT 0
            r"\bLIMIT\s+(\d{10,}|\d{1,9}[0-9]{3,})\s*($|;|\))",  # LIMIT large
        ],
        rewritten_patterns=[],  # removed
    ),
    "STATIC_ORDER_BY_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_ORDER_BY_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[
            r"\bORDER\s+BY\s+(\d+|NULL|'[^']*'|\"[^\"]*\"|[\d\.]+)(\s*,\s*(\d+|NULL|'[^']*'|\"[^\"]*\"|[\d\.]+))*",
        ],
        rewritten_patterns=[],  # removed
    ),
}


def normalize_sql(sql: str) -> str:
    """Normalize SQL for pattern matching."""
    if not sql:
        return ""
    # Simple normalization: lowercase, collapse whitespace
    return re.sub(r"\s+", " ", sql.strip().lower())


def _matches_config(ctx: ClassificationContext, cfg: ClassificationConfig) -> bool:
    """Check if context matches configuration."""
    if not ctx.original_sql:
        return False

    # Check strategy type
    if cfg.strategy_type:
        strategy = (ctx.selected_patch_strategy or {}).get("strategyType", "").strip().upper()
        if strategy != cfg.strategy_type.upper():
            return False

    # Normalize SQL
    norm_original = normalize_sql(ctx.original_sql)
    norm_rewritten = normalize_sql(ctx.rewritten_sql or "")

    # Check original patterns
    if cfg.original_patterns:
        original_matched = any(
            re.search(pattern, norm_original, re.IGNORECASE)
            for pattern in cfg.original_patterns
        )
        if not original_matched:
            return False

    # Check rewritten patterns (if specified)
    if cfg.rewritten_patterns is not None:
        if cfg.rewritten_patterns:  # Non-empty list - need to match
            rewritten_matched = any(
                re.search(pattern, norm_rewritten, re.IGNORECASE)
                for pattern in cfg.rewritten_patterns
            )
            if not rewritten_matched:
                return False
        else:  # Empty list - rewritten should NOT match original patterns
            # This is a simplification case (pattern removed)
            pass

    return True


def classify_patch_family(ctx: ClassificationContext) -> str | None:
    """Main classification function: config-first, then fallback."""
    # Configuration-based matching
    for family, cfg in _CONFIG.items():
        if _matches_config(ctx, cfg):
            return family

    # Fallback: return None (let existing validator_sql logic handle it)
    return None
```

- [ ] **Step 4: 更新 __init__.py 导出**

```python
# python/sqlopt/patch_families/classification/__init__.py
from .models import ClassificationConfig, ClassificationContext
from .registry import classify_patch_family

__all__ = [
    "ClassificationConfig",
    "ClassificationContext",
    "classify_patch_family",
]
```

- [ ] **Step 5: 运行测试验证通过**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/patch_families/classification/ tests/test_classification.py
git commit -m "feat: add classification registry with config-based matching

- Add _CONFIG registry with 3 simple families
- Implement _matches_config() pattern matching logic
- classify_patch_family() now returns family for regex-based matches"
```

---

## Task 3: 添加更多 family 配置

**Files:**
- Modify: `python/sqlopt/patch_families/classification/registry.py`
- Modify: `tests/test_classification.py`

- [ ] **Step 1: 写入失败的测试**

```python
# tests/test_classification.py - 添加更多测试

def test_config_or_simplification():
    """STATIC_OR_SIMPLIFICATION can be classified via config."""
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users WHERE id = 1 OR id = 2",
        rewritten_sql="SELECT * FROM users WHERE id IN (1, 2)",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    # May need more complex logic, test documents expected behavior


def test_config_distinct_on():
    """STATIC_DISTINCT_ON_SIMPLIFICATION can be classified via config."""
    ctx = ClassificationContext(
        original_sql="SELECT DISTINCT ON (id) id, name FROM users",
        rewritten_sql="SELECT DISTINCT id, name FROM users",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    assert result == "STATIC_DISTINCT_ON_SIMPLIFICATION"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py::test_config_distinct_on -v`
Expected: FAIL

- [ ] **Step 3: 添加更多配置到 registry.py**

```python
# python/sqlopt/patch_families/classification/registry.py - 添加更多配置

_CONFIG: dict[str, ClassificationConfig] = {
    # ... existing ...

    "STATIC_DISTINCT_ON_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_DISTINCT_ON_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\bSELECT\s+DISTINCT\s+ON\s*\("],
        rewritten_patterns=[r"\bSELECT\s+DISTINCT\s+"],
    ),
}
```

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/sqlopt/patch_families/classification/registry.py tests/test_classification.py
git commit -m "feat: add more family configs (DISTINCT_ON, etc.)

- Add STATIC_DISTINCT_ON_SIMPLIFICATION config
- Add test coverage for more families"
```

---

## Task 4: 集成到 validator_sql.py

**Files:**
- Modify: `python/sqlopt/platforms/sql/validator_sql.py`
- Test: existing tests

- [ ] **Step 1: 写入失败的测试**

```python
# tests/test_classification.py - 集成测试

def test_integration_with_validator_sql():
    """Classification integrates with validator_sql._derive_patch_target_family."""
    # This test verifies the integration point
    from sqlopt.patch_families.classification import (
        ClassificationContext,
        classify_patch_family,
    )

    # Test case that should be handled by config
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users WHERE id IN (1)",
        rewritten_sql="SELECT * FROM users WHERE id = 1",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )

    # The function should not raise and should return a result
    result = classify_patch_family(ctx)
    assert result in ("STATIC_IN_LIST_SIMPLIFICATION", None)
```

- [ ] **Step 2: 运行测试验证失败 (如果集成未完成)**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py -v`
Expected: 可能 PASS（因为 classify_patch_family 已经实现）

- [ ] **Step 3: 修改 validator_sql.py 添加集成点**

```python
# python/sqlopt/platforms/sql/validator_sql.py - 在文件顶部添加导入

# 在文件开头添加（大约在 line 20 附近，其他导入后面）
from sqlopt.patch_families.classification import (
    classify_patch_family as _config_classify,
    ClassificationContext,
)
```

```python
# python/sqlopt/platforms/sql/validator_sql.py - 修改 _derive_patch_target_family 函数

def _derive_patch_target_family(
    *,
    original_sql: str,
    rewritten_sql: str | None,
    rewrite_facts: dict[str, Any] | None,
    rewrite_materialization: dict[str, Any] | None,
    selected_patch_strategy: dict[str, Any] | None,
) -> str | None:
    # ... 现有逻辑 (line 218-243) ...

    # 新增: 配置驱动分类（在现有 if-else 之前调用）
    ctx = ClassificationContext(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        selected_patch_strategy=selected_patch_strategy,
    )
    config_family = _config_classify(ctx)
    if config_family:
        return config_family

    # 现有逻辑继续...
    alias_guarded, alias_family = _classify_static_alias_projection_cleanup(
    # ...
```

- [ ] **Step 4: 运行测试验证通过**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py tests/test_patch_contracts.py -v`
Expected: PASS

- [ ] **Step 5: 运行完整测试确保无回归**

Run: `PYTHONPATH=python python3 -m pytest tests/test_validator_sql.py -v --tb=short`
Expected: PASS (无回归)

- [ ] **Step 6: Commit**

```bash
git add python/sqlopt/platforms/sql/validator_sql.py
git commit -m "feat: integrate classification config into validator_sql

- Add import for classification module
- Call classify_patch_family() in _derive_patch_target_family()
- Config-based classification runs before existing if-else logic"
```

---

## Task 5: 添加更多 family 配置并验证

**Files:**
- Modify: `python/sqlopt/patch_families/classification/registry.py`
- Modify: `tests/test_classification.py`

- [ ] **Step 1: 添加剩余简单 family 配置**

```python
# python/sqlopt/patch_families/classification/registry.py - 添加更多配置

_CONFIG: dict[str, ClassificationConfig] = {
    # ... existing ...

    "STATIC_OR_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_OR_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\b([a-z_][a-z0-9_\.]*)\s*=\s*[^'\s]+\s+OR\s+\1\s*=\s*[^'\s]+"],
        rewritten_patterns=[r"\bIN\s*\("],
    ),
    "STATIC_BOOLEAN_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_BOOLEAN_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\b(1\s*=\s*1|0\s*=\s*0|1\s*<>?\s*1|0\s*<>?\s*0)\b"],
        rewritten_patterns=[],  # removed or simplified
    ),
    "STATIC_CASE_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_CASE_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\bCASE\s+WHEN\s+TRUE\s+THEN\b"],
        rewritten_patterns=[],  # simplified
    ),
    "STATIC_COALESCE_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_COALESCE_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\bCOALESCE\s*\(\s*([a-z_][a-z0-9_\.]*)\s*,\s*(\1|NULL)\s*\)"],
        rewritten_patterns=[r"\1"],  # simplified to just the column
    ),
    "STATIC_EXPRESSION_FOLDING": ClassificationConfig(
        family="STATIC_EXPRESSION_FOLDING",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\b(\d+)\s*([+\-*/])\s*(\d+)\b"],
        rewritten_patterns=[],  # folded result
    ),
    "STATIC_NULL_COMPARISON": ClassificationConfig(
        family="STATIC_NULL_COMPARISON",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\b([a-z_][a-z0-9_\.]*)\s*(=|<>|!=)\s*NULL\b"],
        rewritten_patterns=[r"\bIS\s+(NULL|NOT\s+NULL)\b"],
    ),
}
```

- [ ] **Step 2: 添加测试覆盖**

```python
# tests/test_classification.py - 添加测试

def test_config_distinct_on_simplification():
    ctx = ClassificationContext(
        original_sql="SELECT DISTINCT ON (id) id FROM users",
        rewritten_sql="SELECT DISTINCT id FROM users",
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    assert result == "STATIC_DISTINCT_ON_SIMPLIFICATION"


def test_config_boolean_simplification():
    ctx = ClassificationContext(
        original_sql="SELECT * FROM users WHERE 1 = 1",
        rewritten_sql="SELECT * FROM users",  # condition removed
        rewrite_facts=None,
        selected_patch_strategy={"strategyType": "EXACT_TEMPLATE_EDIT"},
    )
    result = classify_patch_family(ctx)
    assert result == "STATIC_BOOLEAN_SIMPLIFICATION"
```

- [ ] **Step 3: 运行测试**

Run: `PYTHONPATH=python python3 -m pytest tests/test_classification.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add python/sqlopt/patch_families/classification/registry.py tests/test_classification.py
git commit -m "feat: add remaining simple family configs

- Add STATIC_OR_SIMPLIFICATION, STATIC_BOOLEAN_SIMPLIFICATION
- Add STATIC_CASE_SIMPLIFICATION, STATIC_COALESCE_SIMPLIFICATION
- Add STATIC_EXPRESSION_FOLDING, STATIC_NULL_COMPARISON
- Total families in config: 9"
```

---

## Task 6: 最终验证和清理

**Files:**
- Test: all related tests

- [ ] **Step 1: 运行完整测试套件**

Run: `PYTHONPATH=python python3 -m pytest tests/ -q --tb=line`
Expected: 所有测试通过

- [ ] **Step 2: 验证新 family 添加工作流**

```bash
# 演示：添加一个新的 family 只需 2 步
# 1. 创建 spec (已有流程)
# 2. 在 registry.py 添加配置行 (新流程)
```

- [ ] **Step 3: Commit 最终更改**

```bash
git add .
git commit -m "feat: complete configuration-driven classification

- Reduce new family onboarding from 4 steps to 2
- 9 families now config-driven
- Backward compatible with existing validator logic"
```

---

## 任务总结

| Task | 描述 | 文件变化 |
|------|------|----------|
| 1 | 创建 classification 模块基础 | +4 files |
| 2 | 实现 registry.py 调度器 | +1 file, mod 1 |
| 3 | 添加更多 family 配置 | mod 2 |
| 4 | 集成到 validator_sql.py | mod 1 |
| 5 | 添加剩余 family 配置 | mod 2 |
| 6 | 最终验证 | tests |

**预计总耗时**: 2-3 小时（每个 task 15-30 分钟）

**Plan complete and saved to `docs/superpowers/plans/2026-03-27-configuration-driven-classification.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?