# EXISTS 重写功能设计

**日期**: 2026-03-28
**状态**: 已批准
**功能**: 为 SQL Optimizer 添加 EXISTS 重写功能

---

## 1. 概述

### 1.1 目的

为 SQL Optimizer 添加 EXISTS 重写功能，支持将 EXISTS 查询转换为更高效的 IN 或 JOIN 形式。

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
| NOT EXISTS → NOT IN | `WHERE NOT EXISTS (SELECT 1 FROM t WHERE t.id = a.id)` | `WHERE a.id NOT IN (SELECT t.id FROM t)` |
| EXISTS → JOIN | `WHERE EXISTS (SELECT 1 FROM t WHERE t.id = a.id)` | 特定场景下转换为 JOIN |

### 2.2 关键约束

- **安全性优先**：平衡覆盖，但优先保证安全
- **语义验证**：必须通过 DB EXPLAIN 验证
- **回放验证**：必须通过模板回放验证
- **置信度**：要求 HIGH

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
    }
    """

def rewrite_exists_to_in(sql: str, pattern: dict) -> str | None:
    """将 EXISTS 重写为 IN"""

def rewrite_exists_to_join(sql: str, pattern: dict) -> str | None:
    """将 EXISTS 重写为 JOIN (谨慎使用)"""

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
        # 检查 EXISTS 模式
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

#### NOT EXISTS → NOT IN
```sql
-- 原始
SELECT * FROM a WHERE NOT EXISTS (SELECT 1 FROM b WHERE b.id = a.id)

-- 重写后
SELECT * FROM a WHERE a.id NOT IN (SELECT b.id FROM b)
```

#### EXISTS → JOIN
```sql
-- 原始
SELECT * FROM a WHERE EXISTS (SELECT 1 FROM b WHERE b.id = a.id)

-- 重写后 (仅在特定场景)
SELECT DISTINCT a.* FROM a INNER JOIN b ON b.id = a.id
```

### 4.2 安全性检查

```python
def validate_exists_rewrite_safety(original: str, rewritten: str) -> tuple[bool, str | None]:
    """EXISTS 重写安全性检查"""

    checks = [
        # 相关子查询检查
        ("correlation_required", not has_correlation(original),
         "CORRELATION_REQUIRED"),

        # NULL 语义检查 (NOT IN 可能产生不同结果)
        ("null_semantics", is_not_in and may_have_nulls(subquery),
         "NULL_SEMANTICS_MAY_DIFFER"),

        # JOIN 转换需要更严格验证
        ("join_complexity", is_join and is_complex_join(original),
         "JOIN_COMPLEXITY_TOO_HIGH"),
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
| test_rewrite_not_exists_to_not_in | NOT EXISTS → NOT IN 重写 |
| test_validate_exists_safety | 安全性验证 |

### 5.2 集成测试

| 测试用例 | 说明 |
|----------|------|
| test_capability_rule | Capability 规则测试 |
| test_patch_generation | Patch 生成测试 |

---

## 6. 工作量估算

| 任务 | 工作量 |
|------|--------|
| exists_utils.py 通用模块 | 1.5 天 |
| Capability 规则实现 | 1.5 天 |
| Family Spec 定义 | 0.5 天 |
| 注册策略和 Family | 0.5 天 |
| 单元测试 | 1 天 |
| 集成测试 | 1 天 |
| **总计** | **6 天 (~1.5 周)** |

---

## 7. 风险缓解

| 风险 | 缓解措施 |
|------|----------|
| NULL 语义差异 | NOT IN 转换需严格验证子查询无 NULL |
| JOIN 复杂度 | 仅在简单场景支持 EXISTS → JOIN |
| 相关子查询 | 必须存在关联条件才能转换 |
| 性能退化 | 强制 DB EXPLAIN 验证 |

---

## 8. 验收标准

- [ ] EXISTS → IN 重写正常工作
- [ ] NOT EXISTS → NOT IN 重写正常工作
- [ ] EXISTS → JOIN 重写正常工作
- [ ] 安全性检查通过
- [ ] 回放验证通过
- [ ] 单元测试覆盖主要场景
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

**设计批准日期**: 2026-03-28