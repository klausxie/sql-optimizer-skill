# 配置驱动分类架构设计

**日期**: 2026-03-27
**状态**: 设计中
**目标**: 简化 Patch Family 添加流程，消除重复性手工劳动

## 背景

当前添加新的 Patch Family 需要修改 4 个文件：

1. `specs/static_xxx.py` - 创建 spec 定义
2. `registry.py` - import + 注册
3. `validator_sql.py` - 添加 regex 模式 + 分类函数
4. `tests/test_patch_contracts.py` - 更新预期列表

每次添加 family 都需要在 `validator_sql.py` 中:
- 定义新的 regex 模式
- 编写 `_classify_static_xxx()` 函数
- 在 `_derive_patch_target_family()` 中添加 if 分支

这导致:
- 大量重复代码
- 容易遗漏或出错
- 添加一个 family 需要 30+ 分钟

## 目标

将添加 family 的工作量从 **4 步减少到 2 步**:
1. 创建 `specs/static_xxx.py`
2. 在配置表中添加一行配置

## 设计方案

### 1. 目录结构

```
python/sqlopt/patch_families/classification/
├── __init__.py           # 导出核心 API
├── models.py             # 配置数据模型
├── registry.py           # 配置注册表 + 调度器
├── patterns.py           # 预编译的 regex 模式
└── validators.py         # 复杂分类函数（保留现有逻辑）
```

### 2. 核心 API

```python
# __init__.py
from .registry import classify_patch_family, ClassificationContext
from .models import ClassificationConfig

__all__ = ["classify_patch_family", "ClassificationContext", "ClassificationConfig"]
```

### 3. 配置模型

```python
# models.py
from dataclasses import dataclass
from typing import Protocol, Any

@dataclass
class ClassificationConfig:
    """单个 family 的分类配置"""
    family: str                           # FAMILY_ID (e.g., "STATIC_IN_LIST_SIMPLIFICATION")
    strategy_type: str | None            # patch strategy type (e.g., "EXACT_TEMPLATE_EDIT")
    original_patterns: list[str] | None  # regex patterns to match original_sql
    rewritten_patterns: list[str] | None # regex patterns to match rewritten_sql
    validator_func: str | None           # fallback: validator function name
    requires_rewrite_facts: bool = False # 是否需要 rewrite_facts
    requires_dynamic_template: bool = False

@dataclass
class ClassificationContext:
    """分类上下文，封装所有输入参数"""
    original_sql: str
    rewritten_sql: str | None
    rewrite_facts: dict[str, Any] | None
    selected_patch_strategy: dict[str, Any] | None
```

### 4. 配置注册表

```python
# registry.py
from .models import ClassificationConfig, ClassificationContext

# ============ 简单模式配置（regex-based）============

_CONFIG: dict[str, ClassificationConfig] = {
    "STATIC_IN_LIST_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_IN_LIST_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[
            r"\bIN\s*\(\s*[\w']+\s*\)",      # IN (single_value)
            r"\bNOT\s+IN\s*\(\s*[\w']+\s*\)", # NOT IN (single_value)
        ],
        rewritten_patterns=[
            r"\b=\s*[\w']+",                  # column = value
            r"\b<>\s*[\w']+",                  # column <> value
            r"\b!=\s*[\w']+",                  # column != value
        ],
    ),
    "STATIC_LIMIT_OPTIMIZATION": ClassificationConfig(
        family="STATIC_LIMIT_OPTIMIZATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\bLIMIT\s+0\b", r"\bLIMIT\s+\d{7,}\b"],
        rewritten_patterns=[],  # 移除 LIMIT
    ),
    "STATIC_ORDER_BY_SIMPLIFICATION": ClassificationConfig(
        family="STATIC_ORDER_BY_SIMPLIFICATION",
        strategy_type="EXACT_TEMPLATE_EDIT",
        original_patterns=[r"\bORDER\s+BY\s+['\"]?\d+['\"]?"],  # ORDER BY constant
        rewritten_patterns=[],  # 移除 ORDER BY
    ),
    # ... 其他 regex-based family
}

# ============ 复杂函数注册 ============
_VALIDATORS: dict[str, callable] = {}

def register_validator(name: str, func: callable):
    _VALIDATORS[name] = func


def classify_patch_family(ctx: ClassificationContext) -> str | None:
    """主分类函数：配置优先，fallback 到 validator 函数"""

    # 1. 策略类型过滤
    strategy_type = (ctx.selected_patch_strategy or {}).get("strategyType", "").strip().upper()

    # 2. 配置匹配
    for family, cfg in _CONFIG.items():
        if cfg.strategy_type and cfg.strategy_type != strategy_type:
            continue
        if cfg.requires_rewrite_facts and not ctx.rewrite_facts:
            continue
        if _matches_config(ctx, cfg):
            return family

    # 3. Fallback: validator 函数
    for family, cfg in _CONFIG.items():
        if cfg.validator_func and cfg.validator_func in _VALIDATORS:
            validator = _VALIDATORS[cfg.validator_func]
            result = validator(
                original_sql=ctx.original_sql,
                rewritten_sql=ctx.rewritten_sql,
                rewrite_facts=ctx.rewrite_facts,
                selected_patch_strategy=ctx.selected_patch_strategy,
            )
            if result:
                return family

    return None


def _matches_config(ctx: ClassificationContext, cfg: ClassificationConfig) -> bool:
    """检查上下文是否匹配配置"""
    # 实现 pattern 匹配逻辑
    ...
```

### 5. 添加新 Family

**只需两步**:

```python
# 1. 创建 specs/static_xxx.py (现有流程)

# 2. 在 classification/registry.py 添加配置:
_CONFIG["STATIC_XXX_SIMPLIFICATION"] = ClassificationConfig(
    family="STATIC_XXX_SIMPLIFICATION",
    strategy_type="EXACT_TEMPLATE_EDIT",
    original_patterns=[r"\bPATTERN\b"],
    rewritten_patterns=[r"\bREPLACEMENT\b"],
)
```

### 6. 集成到 validator_sql.py

```python
# validator_sql.py
from sqlopt.patch_families.classification import (
    classify_patch_family as _config_classify,
    ClassificationContext,
)

def _derive_patch_target_family(...) -> str | None:
    # ... 现有逻辑 ...

    # 新增: 配置驱动分类
    ctx = ClassificationContext(
        original_sql=original_sql,
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        selected_patch_strategy=selected_patch_strategy,
    )
    config_family = _config_classify(ctx)
    if config_family:
        return config_family

    # Fallback: 现有 if-else 逻辑（保留兼容）
    ...
```

## 实施计划

### Phase 1: 基础设施搭建

1. 创建 `classification/` 目录结构
2. 实现 `models.py` - 配置数据模型
3. 实现 `registry.py` - 注册表 + 调度器
4. 迁移 5 个简单 regex-based family 到配置

### Phase 2: 验证和迭代

5. 集成到 validator_sql.py
6. 运行测试验证兼容性
7. 迁移剩余简单 family

### Phase 3: 优化（可选）

8. 移除旧的 if-else 逻辑（保留 fallback）
9. 添加自动化测试验证配置正确性

## 风险控制

- **向后兼容**: 现有逻辑作为 fallback，不删除
- **渐进迁移**: 逐个迁移 family，可随时回滚
- **测试覆盖**: 每迁移一个 family，运行相关测试

## 预期收益

| 指标 | 当前 | 目标 |
|------|------|------|
| 添加 family 步骤 | 4 步 | 2 步 |
| 预估时间 | 30 分钟 | 5 分钟 |
| validator_sql.py 代码行 | ~800 | ~600 |

## 开放问题

- [ ] 是否需要从 registry.py 自动发现配置？
- [ ] 如何处理需要多步验证的复杂 family？
- [ ] 配置是否需要版本管理和迁移？

---

**设计者**: Claude
**审核者**: 待定
**预计工期**: Phase 1 (1-2 小时), Phase 2 (1 ��时)