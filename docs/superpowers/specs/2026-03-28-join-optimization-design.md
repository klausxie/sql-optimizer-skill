# JOIN 优化特性设计

## 概述

实现 4 种 JOIN 优化 family，采用 LLM 主导、规则安全门的架构。

### 实现顺序

A → B → C → D（先实现简单的转换，再逐步深入）

| 特性 | 名称 | 说明 |
|------|------|------|
| A | LEFT→INNER | 当 WHERE 保证非空时，将 LEFT JOIN 转为 INNER JOIN |
| B | JOIN 消除 | 移除不必要的 JOIN |
| C | JOIN 重排 | 优化多个表的 JOIN 顺序 |
| D | JOIN 合并 | 合并多个小表的 JOIN |

---

## 架构设计

### LLM 主导模式

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Capability     │     │  LLM            │     │  Validation     │
│  Rules (安全门) │────▶│  (决策生成)     │────▶│  (DB验证)       │
│                 │     │                 │     │                 │
│ - 检测 JOIN     │     │ - 分析上下文    │     │ - 语义等价检查  │
│ - 安全检查     │     │ - 选择优化策略  │     │ - 性能对比      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Capability Rules（安全门）

只做基本检测和拦截，不做优化决策：

| Rule | 功能 |
|------|------|
| `JOIN_PRESENT` | 检测 SQL 是否包含 JOIN |
| `JOIN_COMPLEXITY_CHECK` | 检查 JOIN 复杂度是否在可处理范围内 |
| `JOIN_SAFETY_GATE` | 检查是否有明显的危险模式（如 FULL OUTER JOIN） |
| `JOIN_TEMPLATE_CHECK` | 检查 JOIN 是否涉及动态模板 |

---

## 特性 A：LEFT→INNER JOIN 转换

### 功能

当 WHERE 子句保证非空时，将 LEFT JOIN 转换为 INNER JOIN

### 触发条件

- **IS NOT NULL 检测**：WHERE 子句对被 JOIN 表的列有 `IS NOT NULL`、`!= NULL`、`<> NULL` 检查
- **主键/唯一键检测**：被 JOIN 的表使用主键或唯一键进行 JOIN，且该列有 NOT NULL 约束（需结合元数据）
- **业务逻辑判断**：LLM 判断业务逻辑是否保证了非空关系（如外键关联且启用了外键约束）

### 示例

```sql
-- 原始
SELECT * FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE u.id IS NOT NULL

-- 优化后
SELECT * FROM orders o INNER JOIN users u ON o.user_id = u.id
```

### Family Spec

- **名称**：`STATIC_JOIN_LEFT_TO_INNER`
- **策略**：`SAFE_JOIN_LEFT_TO_INNER`
- **状态**：MVP_STATIC_BASELINE

---

## 特性 B：JOIN 消除

### 功能

移除不必要的 JOIN

### 触发条件

- **未使用列**：被 JOIN 的表列未在 SELECT、WHERE、ORDER BY、GROUP BY、HAVING 中使用
- **只做过滤**：被 JOIN 的表只用于 WHERE 条件过滤，不输出任何列
- **主键关联**：两表通过主键 JOIN，且只需要主表数据

### 示例

```sql
-- 原始（users 表只在 WHERE 中用于过滤，未输出任何列）
SELECT o.id, o.amount FROM orders o
LEFT JOIN users u ON o.user_id = u.id
WHERE u.status = 'active'

-- 优化后（转化为 EXISTS）
SELECT o.id, o.amount FROM orders o
WHERE EXISTS (SELECT 1 FROM users WHERE id = o.user_id AND status = 'active')
```

### Family Spec

- **名称**：`STATIC_JOIN_ELIMINATION`
- **策略**：`SAFE_JOIN_ELIMINATION`
- **状态**：MVP_STATIC_BASELINE

---

## 特性 C：JOIN 重排

### 功能

优化多个表的 JOIN 顺序

### 策略：规则 + LLM 混合

1. **规则预筛选**：
   - 排除无法移动的 JOIN（有不安全条件的表）
   - 标记可以提前的候选表（小表、有索引的表）
2. **LLM 决策**：分析业务逻辑和查询意图，决定最优顺序

### 示例

```sql
-- 原始（假设 users 是小表，orders 是大表）
SELECT * FROM orders o
JOIN users u ON o.user_id = u.id
JOIN products p ON o.product_id = p.id

-- 优化后（调整顺序，小表先行）
SELECT * FROM users u
JOIN orders o ON u.id = o.user_id
JOIN products p ON o.product_id = p.id
```

### Family Spec

- **名称**：`STATIC_JOIN_REORDERING`
- **策略**：`SAFE_JOIN_REORDERING`
- **状态**：MVP_STATIC_BASELINE

---

## 特性 D：JOIN 合并

### 功能

合并多个小表的 JOIN 操作

### 触发条件

- **相同主键**：多个表都通过相同的主键连接到主表
- **依次连接**：多个小表依次 JOIN 到同一个主表（如 A→B→C 都 JOIN 到 A）
- **子查询转 JOIN**：将子查询重写为 JOIN

### 示例

```sql
-- 原始（三个小表依次 JOIN 到主表）
SELECT * FROM main_table m
LEFT JOIN small_table1 s1 ON m.id = s1.ref_id
LEFT JOIN small_table2 s2 ON m.id = s2.ref_id
LEFT JOIN small_table3 s3 ON m.id = s3.ref_id

-- 优化后（合并为子查询）
SELECT * FROM main_table m
LEFT JOIN (
    SELECT ref_id,
           MAX(col1) as col1,
           MAX(col2) as col2,
           MAX(col3) as col3
    FROM (
        SELECT ref_id, col1, NULL as col2, NULL as col3 FROM small_table1
        UNION ALL
        SELECT ref_id, NULL as col1, col2, NULL as col3 FROM small_table2
        UNION ALL
        SELECT ref_id, NULL as col1, NULL as col2, col3 FROM small_table3
    ) combined
    GROUP BY ref_id
) merged ON m.id = merged.ref_id
```

### Family Spec

- **名称**：`STATIC_JOIN_CONSOLIDATION`
- **策略**：`SAFE_JOIN_CONSOLIDATION`
- **状态**：MVP_STATIC_BASELINE

---

## 文件结构

每个优化特性对应 4 个文件：

```
python/sqlopt/platforms/sql/
├── join_utils.py                    # 通用 JOIN 工具函数
├── patch_capability_rules/
│   ├── safe_join_left_to_inner.py  # A
│   ├── safe_join_elimination.py     # B
│   ├── safe_join_reordering.py      # C
│   └── safe_join_consolidation.py   # D

python/sqlopt/patch_families/specs/
├── static_join_left_to_inner.py     # A
├── static_join_elimination.py       # B
├── static_join_reordering.py        # C
└── static_join_consolidation.py     # D
```

---

## LLM Prompt 增强

在 optimize 阶段给 LLM 提供 JOIN 优化提示：

```
当前 SQL 包含 JOIN，请考虑以下优化选项：
1. LEFT→INNER：如果 WHERE 条件保证非空
2. JOIN 消除：如果 JOIN 的表未被使用
3. JOIN 重排：如果 JOIN 顺序可以优化
4. JOIN 合并：如果多个小表可以合并

请选择最适合的优化策略，或保持原样。
```

---

## 验证策略

所有 JOIN 优化都必须在 validate 阶段通过：

1. **语义等价检查**：使用 EXPLAIN 和结果比对验证语义等价
2. **性能对比**：确保优化后的查询性能不下降
3. **安全回归测试**：确保优化不改变查询结果

---

## 优先级

| 特性 | 优先级 | 说明 |
|------|--------|------|
| A | 270 | 最高，规则简单明确 |
| B | 265 | 较高，需要静态分析支持 |
| C | 260 | 中等，需要 LLM 决策 |
| D | 255 | 较低，复杂度最高 |

---

## 演进性设计

为支持未来功能扩展，设计时考虑以下演进点：

### 1. JOIN 类型扩展

```python
# join_utils.py 中的 JOIN 类型枚举，可扩展
class JoinType(Enum):
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL OUTER"
    CROSS = "CROSS"
    # 未来可扩展
    CROSS_APPLY = "CROSS APPLY"
    LATERAL = "LATERAL"
```

### 2. Capability Rule 模块化

每个 capability rule 独立实现，可单独启用/禁用：

```python
# patch_capability_rules/join_registry.py
JOIN_CAPABILITIES = {
    "SAFE_JOIN_LEFT_TO_INNER": SafeJoinLeftToInnerCapability,
    "SAFE_JOIN_ELIMINATION": SafeJoinEliminationCapability,
    "SAFE_JOIN_REORDERING": SafeJoinReorderingCapability,
    "SAFE_JOIN_CONSOLIDATION": SafeJoinConsolidationCapability,
    # 未来可扩展
}
```

### 3. Family 状态演进

| 状态 | 含义 | 触发条件 |
|------|------|----------|
| `MVP_STATIC_BASELINE` | 最小可行产品 | 实现初期 |
| `EXPERIMENTAL` | 实验性 | 经过充分测试后 |
| `FROZEN_AUTO_PATCH` | 冻结稳定 | 经过生产验证后 |

### 4. LLM Prompt 版本化

```python
# 支持 prompt 版本化，便于升级
JOIN_OPTIMIZE_PROMPTS = {
    "v1": "...",
    "v2": "...",  # 未来改进版本
}
```

### 5. 数据库特定优化

```python
# database_specific.py
class JoinOptimization:
    @classmethod
    def get_optimizations(cls, platform: str) -> list[str]:
        # 不同数据库支持不同的优化
        if platform == "postgresql":
            return ["MERGE", "LATERAL"]
        elif platform == "mysql":
            return ["STRAIGHT_JOIN"]
        return []
```

### 6. 分析模块可扩展

```python
# join_analyzer.py
class JoinAnalyzer:
    def __init__(self):
        self.detectors: list[JoinDetector] = []
        # 运行时可注册新的 detector
        self.register(OuterJoinDetector())
        self.register(JoinConditionDetector())

    def analyze(self, sql: str) -> JoinAnalysisResult:
        # 组合多个 detector 的结果
        pass
```

---

## 待定问题

- [ ] JOIN 复杂度的具体阈值？如最大表数量？
- [ ] 是否需要支持跨数据库的 JOIN 优化差异？
- [ ] 如何处理动态模板中的 JOIN？