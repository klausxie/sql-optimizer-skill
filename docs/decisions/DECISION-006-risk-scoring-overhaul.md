# DECISION-006: 风险评分与分级系统重构

**日期**: 2026-04-01
**状态**: Proposed
**决策者**: 待定
**评审**: 待定

---

## 背景与问题

当前风险评分系统存在以下根本性缺陷：

### 问题 1: 阈值无设计来源

HIGH/MEDIUM/LOW 分类阈值 `0.7 / 0.4` 无任何设计文档依据。这些数字在代码中出现时即无注释、无决策记录，属于工程实现时的"拍脑袋"值。

### 问题 2: sigmoid 归一化掩盖真实风险

```python
# rules.py:413 — 当前实现
normalized_score = 1.0 - 1.0 / (1.0 + raw_score)
```

- raw_score=1.0 → norm=0.50（中）
- raw_score=2.0 → norm=0.67（接近 HIGH 边界）
- raw_score=3.0 → norm=0.75（HIGH）
- raw_score=5.0 → norm=0.83（HIGH）
- raw_score=10.0 → norm=0.91（HIGH）

5 条规则和 10 条规则的分值都被压缩到 0.83-0.91 区间，无法区分"多条中等风险"和"少数严重风险"。

### 问题 3: 风险因素不可解释

当前 `score_reasons` 只返回内部 tag（如 `"like_prefix"`、`"select_star"`），用户无法理解：
- 这条 SQL 究竟有什么问题？
- 为什么这条 SQL 比另一条分数高？
- 元数据（如表大小、索引缺失）如何影响分数？

### 问题 4: 元数据因素与语法因素混用同一量表

`large table (+2.0)` 和 `SELECT_STAR (+2.0)` 使用相同的权重体系，但前者是条件性危险（取决于数据量），后者是确定性危险。

### 问题 5: 分类结果无法给出业务解释

`score >= 0.7 → HIGH` 无法回答："这条 SQL 被判定为 HIGH 的业务含义是什么？预期性能影响是多少？"

---

## 决策

### 核心原则

1. **Severity-tier 分类** — 用 CRITICAL/WARNING/INFO 三层 severity 替代数值阈值。分类由"这条 SQL 实际会造成什么数据库行为"决定，不由分数区间决定。
2. **Fully explainable** — 每个风险因素自文档化，包含：问题描述、数据库影响、修复建议。
3. **Severity band 分数** — composite score 由 severity 计数推导，不是 sigmoid 压缩后的原始权重和。
4. **元数据升级** — 同样的语法风险，在大表/无索引场景下自动升级 severity。
5. **向后兼容** — ParseOutput contract 只增不减，现有 JSON 反序列化不受影响。

---

## 新设计方案

### 1. RiskFactor 数据结构

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class Severity(Enum):
    CRITICAL = "CRITICAL"  # 必然全表扫描或索引绕过
    WARNING = "WARNING"    # 低效，随数据增长而恶化
    INFO = "INFO"          # 次优，无即时危险

class Domain(Enum):
    SYNTACTIC = "SYNTACTIC"  # SQL 结构问题（确定）
    METADATA = "METADATA"     # Schema/数据分布问题（条件性）

class ImpactType(Enum):
    FULL_SCAN = "full_scan"         # 全表扫描
    INDEX_BYPASS = "index_bypass"   # 索引绕过
    ROW_AMPLIFICATION = "row_amplification"  # 行放大
    MEMORY_PRESSURE = "memory_pressure"       # 内存压力
    IO_SPIKE = "io_spike"           # IO 突增

@dataclass
class RiskFactor:
    """一个完整的、可解释的风险发现。"""
    code: str                    # 内部标识: "LIKE_PREFIX", "NO_INDEX_ON_FILTER"
    severity: Severity           # 严重等级
    domain: Domain               # 证据来源
    weight: float                # 原始权重（保留用于兼容）

    # 自文档化信息
    explanation_template: str    # 人类可读的问题描述（含占位符）
    impact_type: ImpactType      # 数据库影响类型

    # 修复建议
    remediation_template: str     # 如何修复（含占位符）

    # 运行时填充的上下文
    context: dict = field(default_factory=dict)
    #   e.g. {"column": "search_condition", "table": "users", "table_size": "large"}

    # 引擎特定提示（可选）
    mysql_note: str = ""
    postgresql_note: str = ""

    def render_explanation(self) -> str:
        """用运行时上下文渲染 explanation_template。"""
        return self.explanation_template.format(**self.context)

    def render_remediation(self) -> str:
        """用运行时上下文渲染 remediation_template。"""
        return self.remediation_template.format(**self.context)
```

### 2. 风险因子注册表（替代当前散落的 RiskRule）

```python
RISK_FACTOR_REGISTRY: dict[str, RiskFactor] = {

    # ═══ CRITICAL ═══
    "LIKE_PREFIX": RiskFactor(
        code="LIKE_PREFIX",
        severity=Severity.CRITICAL,
        domain=Domain.SYNTACTIC,
        weight=3.0,
        impact_type=ImpactType.INDEX_BYPASS,
        explanation_template=(
            "LIKE with leading wildcard ('%...') on column `{column}` "
            "prevents index usage. Database must scan every row."
        ),
        remediation_template=(
            "MySQL: Consider full-text index. "
            "PostgreSQL: Use pg_trgm GIN index or reverse the pattern."
        ),
        mysql_note="Full-text search: MATCH(col) AGAINST('keyword')",
        postgresql_note="CREATE INDEX USING gin (col gin_trgm_ops)",
    ),

    "FUNCTION_ON_INDEXED_COLUMN": RiskFactor(
        code="FUNCTION_ON_INDEXED_COLUMN",
        severity=Severity.CRITICAL,
        domain=Domain.SYNTACTIC,
        weight=3.0,
        impact_type=ImpactType.INDEX_BYPASS,
        explanation_template=(
            "Function `{function_name}()` wraps column `{column}` in WHERE clause. "
            "This prevents the optimizer from using any index on `{column}`."
        ),
        remediation_template=(
            "Extract function result into a subquery or use expression index. "
            "Alternatively, refactor to: WHERE {column} = 'value' (pre-computed)."
        ),
    ),

    "NO_INDEX_ON_FILTER": RiskFactor(
        code="NO_INDEX_ON_FILTER",
        severity=Severity.CRITICAL,
        domain=Domain.METADATA,
        weight=3.0,
        impact_type=ImpactType.FULL_SCAN,
        explanation_template=(
            "Column `{column}` is used in WHERE/JOIN clause but has no index. "
            "Every query will perform a full table scan on `{table}` "
            "(est. {row_count:,} rows)."
        ),
        remediation_template=(
            "Add index: CREATE INDEX idx_{table}_{column} ON {table}({column})."
        ),
    ),

    "NOT_IN_LARGE_TABLE": RiskFactor(
        code="NOT_IN_LARGE_TABLE",
        severity=Severity.CRITICAL,
        domain=Domain.SYNTACTIC,
        weight=3.0,
        impact_type=ImpactType.FULL_SCAN,
        explanation_template=(
            "NOT IN on subquery result forces a nested loop scan. "
            "For large result sets, this is equivalent to a cross join."
        ),
        remediation_template="Replace with NOT EXISTS or LEFT JOIN WHERE NULL.",
    ),

    # ═══ WARNING ═══
    "DEEP_OFFSET": RiskFactor(
        code="DEEP_OFFSET",
        severity=Severity.WARNING,
        domain=Domain.SYNTACTIC,
        weight=2.0,
        impact_type=ImpactType.ROW_AMPLIFICATION,
        explanation_template=(
            "OFFSET pagination scans and discards {offset_value} rows before "
            "returning results. Performance degrades linearly with page number. "
            "Users typically request pages 1-10; page 10000 still scans 10000 rows."
        ),
        remediation_template=(
            "Replace with keyset pagination: WHERE id > {last_seen_id} LIMIT 10. "
            "This gives consistent ~0ms response regardless of page number."
        ),
    ),

    "SUBQUERY": RiskFactor(
        code="SUBQUERY",
        severity=Severity.WARNING,
        domain=Domain.SYNTACTIC,
        weight=2.0,
        impact_type=ImpactType.ROW_AMPLIFICATION,
        explanation_template=(
            "Correlated subquery executes once per outer row. "
            "Cost = O(outer_rows × inner_rows). "
            "At scale, this causes N+1-like amplification."
        ),
        remediation_template="Rewrite as a JOIN. Most correlated subqueries can be refactored.",
    ),

    "JOIN_WITHOUT_INDEX": RiskFactor(
        code="JOIN_WITHOUT_INDEX",
        severity=Severity.WARNING,
        domain=Domain.METADATA,
        weight=2.0,
        impact_type=ImpactType.ROW_AMPLIFICATION,
        explanation_template=(
            "JOIN on `{column}` lacks a matching index. "
            "Cost grows as O(M×N) where M and N are table sizes. "
            "On large tables this causes nested-loop scans."
        ),
        remediation_template=(
            "Add index on join column: CREATE INDEX idx_{table}_{column} ON {table}({column})."
        ),
    ),

    "IN_CLAUSE_LARGE": RiskFactor(
        code="IN_CLAUSE_LARGE",
        severity=Severity.WARNING,
        domain=Domain.SYNTACTIC,
        weight=2.0,
        impact_type=ImpactType.MEMORY_PRESSURE,
        explanation_template=(
            "IN clause with {value_count}+ values may cause query plan instability. "
            "The optimizer may choose different plans as value count changes."
        ),
        remediation_template=(
            "Use a temp table for the IN values and replace IN with EXISTS or JOIN. "
            "Alternatively, batch large IN clauses into multiple queries."
        ),
    ),

    "UNION_WITHOUT_ALL": RiskFactor(
        code="UNION_WITHOUT_ALL",
        severity=Severity.WARNING,
        domain=Domain.SYNTACTIC,
        weight=2.0,
        impact_type=ImpactType.IO_SPIKE,
        explanation_template=(
            "UNION (without ALL) adds an implicit DISTINCT sort. "
            "This requires memory for the sort buffer and CPU for sorting. "
            "If duplicates are acceptable, UNION ALL is significantly faster."
        ),
        remediation_template="Use UNION ALL if duplicates are acceptable.",
    ),

    "SKEWED_DISTRIBUTION": RiskFactor(
        code="SKEWED_DISTRIBUTION",
        severity=Severity.WARNING,
        domain=Domain.METADATA,
        weight=2.0,
        impact_type=ImpactType.FULL_SCAN,
        explanation_template=(
            "Column `{column}` is highly skewed: top value `{top_value}` "
            "appears in {skew_pct}% of rows. "
            "The optimizer may choose a suboptimal plan for common values."
        ),
        remediation_template=(
            "Consider a partial index or histogram-based statistics. "
            "For extreme skew, investigate whether the data model is correct."
        ),
    ),

    # ═══ INFO ═══
    "SELECT_STAR": RiskFactor(
        code="SELECT_STAR",
        severity=Severity.INFO,
        domain=Domain.SYNTACTIC,
        weight=1.0,
        impact_type=ImpactType.IO_SPIKE,
        explanation_template=(
            "SELECT * retrieves all columns including those not needed by the application. "
            "It also breaks when schema changes (new columns added). "
            "Explicit column lists are more maintainable."
        ),
        remediation_template=(
            "Replace SELECT * with explicit column list. "
            "Future-proofs the code against schema changes."
        ),
    ),

    "DISTINCT": RiskFactor(
        code="DISTINCT",
        severity=Severity.INFO,
        domain=Domain.SYNTACTIC,
        weight=1.0,
        impact_type=ImpactType.MEMORY_PRESSURE,
        explanation_template=(
            "DISTINCT triggers a hash or sort operation to deduplicate results. "
            "Verify that duplicates are actually possible from your query structure."
        ),
        remediation_template=(
            "If duplicates cannot occur, remove DISTINCT. "
            "If they can, ensure the application needs all duplicate rows."
        ),
    ),

    "HIGH_NULL_RATIO": RiskFactor(
        code="HIGH_NULL_RATIO",
        severity=Severity.INFO,
        domain=Domain.METADATA,
        weight=1.0,
        impact_type=ImpactType.INDEX_BYPASS,
        explanation_template=(
            "Column `{column}` has {null_pct}% NULL values. "
            "Most B-tree indexes exclude NULLs, reducing index effectiveness "
            "for queries like WHERE {column} = 'value'."
        ),
        remediation_template=(
            "Consider a partial index WHERE {column} IS NOT NULL "
            "if most queries filter out NULLs."
        ),
    ),

    "LOW_CARDINALITY": RiskFactor(
        code="LOW_CARDINALITY",
        severity=Severity.INFO,
        domain=Domain.METADATA,
        weight=1.0,
        impact_type=ImpactType.INDEX_BYPASS,
        explanation_template=(
            "Column `{column}` has only {distinct_count} distinct values. "
            "A B-tree index has low selectivity — full table scan is often faster."
        ),
        remediation_template=(
            "Low cardinality indexes rarely help. "
            "Consider composite indexes that include high-selectivity columns first."
        ),
    ),
}
```

### 3. Severity 升级规则

同一个语法风险，在不同元数据环境下 severity 不同：

```python
def resolve_severity(
    base_factor: RiskFactor,
    context: dict,  # {"table_size": "large", "row_count": 2_400_000, "has_index": False, ...}
) -> RiskFactor:
    """基于元数据上下文，返回实际使用的 RiskFactor（可能升级 severity）。"""

    # 不能降级，只能升级
    if base_factor.severity == Severity.CRITICAL:
        return base_factor

    # WARNING → CRITICAL: 大表 + 无索引/索引失效
    if base_factor.severity == Severity.WARNING:
        if context.get("table_size") == "large" and not context.get("has_index", True):
            return upgrade_severity(base_factor, Severity.CRITICAL)
        if context.get("row_count", 0) > 1_000_000:
            return upgrade_severity(base_factor, Severity.CRITICAL)

    # INFO → WARNING: 大表
    if base_factor.severity == Severity.INFO:
        if context.get("table_size") == "large":
            return upgrade_severity(base_factor, Severity.WARNING)
        if context.get("row_count", 0) > 100_000:
            return upgrade_severity(base_factor, Severity.WARNING)

    return base_factor
```

### 4. RiskAssessment 聚合结构

```python
@dataclass
class RiskAssessment:
    """一个分支或 SQL 单元的聚合风险评估。"""
    factors: list[RiskFactor]  # 所有匹配到的因子（含上下文）

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.factors if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.factors if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.factors if f.severity == Severity.INFO)

    @property
    def composite_score(self) -> float:
        """
        Severity 计数推导的 0.0-1.0 分。
        替代 sigmoid 归一化。
        """
        if self.critical_count >= 2:
            return 0.95
        if self.critical_count == 1:
            return 0.80 + min(self.warning_count * 0.05, 0.15)   # 0.80–0.95
        if self.warning_count >= 3:
            return 0.70 + min(self.info_count * 0.02, 0.10)     # 0.70–0.80
        if self.warning_count >= 1:
            return 0.50 + min(self.warning_count * 0.05, 0.20)  # 0.50–0.70
        if self.info_count >= 2:
            return 0.30 + min(self.info_count * 0.05, 0.20)     # 0.30–0.50
        return 0.10 + min(self.info_count * 0.10, 0.20)        # 0.10–0.30

    @property
    def risk_level(self) -> str:
        """HIGH / MEDIUM / LOW — 替代 0.7/0.4 阈值判断。"""
        if self.critical_count > 0:
            return "HIGH"
        if self.warning_count >= 2:
            return "MEDIUM"
        return "LOW"

    @property
    def worst_factor(self) -> RiskFactor | None:
        """分数最高的因子（用于报告中的"主要问题"标注）。"""
        if not self.factors:
            return None
        return max(self.factors, key=lambda f: f.weight)
```

### 5. 分类的业务语义

| 等级 | 触发条件 | 业务含义 | 行动 |
|------|---------|---------|------|
| **HIGH** | ≥1 个 CRITICAL | 这条 SQL **必然**导致全表扫描或索引绕过。预计性能比有索引查询慢 10x 以上。 | **必须在发布前修复** |
| **MEDIUM** | ≥2 个 WARNING 或 1 个 WARNING + 表较大 | 这条 SQL 效率低下，随数据增长会持续恶化。10x 数据量时预期慢 3-5x。 | **当前 sprint 安排优化** |
| **LOW** | 仅 INFO 因子 | 轻微次优模式，无即时性能风险。 | **代码审查时顺便修复** |

---

## 向后兼容策略

### ParseOutput Contract 扩展

```python
# contracts/parse.py — SQLBranch dataclass
class SQLBranch:
    # 现有字段（不变）
    path_id: str
    condition: str | None
    expanded_sql: str
    is_valid: bool
    risk_flags: list[str] = field(default_factory=list)
    active_conditions: list[str] = field(default_factory=list)
    risk_score: float | None = None
    score_reasons: list[str] = field(default_factory=list)
    branch_type: str | None = None

    # 新增字段（可选，反序列化时 .get() 回退）
    risk_factors: list[dict] = field(default_factory=list)
    #   每项: {"code": str, "severity": str, "domain": str,
    #          "explanation": str, "remediation": str,
    #          "context": dict, "impact_type": str}

    risk_level: str | None = None  # "HIGH" | "MEDIUM" | "LOW"
```

**兼容性保证**：
- `risk_score` 字段保留，由 `RiskAssessment.composite_score` 填充
- `score_reasons` 继续由 factor code 填充（向后兼容下游阶段）
- `risk_flags` 不变
- 旧 JSON 文件无 `risk_factors` 时 `.get("risk_factors", [])` 安全回退

---

## 报告展示设计

### 分支详情卡片

```html
<div class="risk-card risk-level-HIGH">
  <div class="risk-header">
    <span class="severity-badge critical">CRITICAL</span>
    <span class="composite-score">0.87</span>
    <span class="risk-level">HIGH</span>
  </div>

  <div class="risk-factors">
    <!-- 每个因子独立展示 -->
    <div class="risk-factor critical">
      <div class="factor-header">
        <span class="factor-code">LIKE_PREFIX</span>
        <span class="factor-domain">SYNTACTIC</span>
        <span class="factor-impact">Index Bypass</span>
      </div>
      <div class="factor-explanation">
        LIKE with leading wildcard (<code>'%keyword'</code>) on column
        <code>search_condition</code> prevents index usage.
        Database must scan every row in <code>users</code> (est. 2,400,000 rows).
      </div>
      <div class="factor-remediation">
        <strong>Fix:</strong> PostgreSQL: <code>CREATE INDEX USING gin (search_condition gin_trgm_ops)</code>
      </div>
    </div>

    <div class="risk-factor critical metadata-upgraded">
      <div class="factor-header">
        <span class="factor-code">NO_INDEX_ON_FILTER</span>
        <span class="factor-domain">METADATA</span>
        <span class="factor-severity-note">(↑ upgraded from WARNING: large table)</span>
      </div>
      <div class="factor-explanation">
        Column <code>status</code> is used in WHERE clause but has no index.
        Full table scan on <code>users</code> (2,400,000 rows) on every query.
      </div>
      <div class="factor-remediation">
        <strong>Fix:</strong> <code>CREATE INDEX idx_users_status ON users(status)</code>
      </div>
    </div>

    <div class="risk-factor info">
      <div class="factor-header">
        <span class="factor-code">SELECT_STAR</span>
        <span class="factor-domain">SYNTACTIC</span>
      </div>
      <div class="factor-explanation">
        SELECT * retrieves all columns. This is not immediately dangerous
        on small tables but breaks when schema changes.
      </div>
    </div>
  </div>

  <div class="risk-summary">
    <strong>Why HIGH:</strong> 2 CRITICAL factors guarantee full table scans
    regardless of data volume. Expected query time: >500ms on current data.
  </div>
</div>
```

### SQL 单元汇总

```
UserMapper.findUsers
├── path_001 (all conditions)   → HIGH  (2 CRITICAL, 1 INFO)
├── path_002 (search active)   → HIGH  (1 CRITICAL, 2 WARNING)
├── path_003 (status filter)   → MEDIUM (2 WARNING)
└── path_004 (baseline)        → LOW   (1 INFO)

Worst branch: path_001 — drives unit-level classification to HIGH
Unit-level HIGH reason: LIKE_PREFIX (full scan on users, 2.4M rows) + NO_INDEX_ON_FILTER
```

---

## 实施影响分析

### 需要修改的文件

| 文件 | 修改内容 |
|------|---------|
| `common/rules.py` | 用 `RiskFactor` 注册表替代 `RiskRule` 注册表；删除 sigmoid |
| `common/risk_assessment.py` (新增) | `RiskFactor`, `RiskAssessment`, `Severity`, `Domain`, `ImpactType` |
| `stages/branching/risk_scorer.py` | 返回 `RiskAssessment` 而非 `(float, list[str])` |
| `stages/branching/branch_generator.py` | 调用 `risk_scorer.score_branch()` 获取 `RiskAssessment` |
| `contracts/parse.py` | `SQLBranch` 新增 `risk_factors`, `risk_level` 字段 |
| `common/stage_report_generator.py` | 用 `risk_factors` 渲染因子卡片；用 `risk_level` 替代阈值判断 |
| `stages/parse/stage.py` | 将 `RiskAssessment` 序列化到分支 JSON |
| `common/parse_stats.py` | 用 `risk_level` 替代 `>= 0.7` 阈值统计 |

### 不需要修改的消费者

| 文件 | 原因 |
|------|------|
| `stages/branching/branch_validator.py` | 用 `risk_score` 排序，新 `composite_score` 填充同一字段 |
| `stages/result/stage.py` (部分) | `score_reasons` 继续由 factor code 填充 |
| 已有 runs/ 的 JSON 文件 | `risk_factors` / `risk_level` 使用 `.get()` 回退 |

---

## 替代方案

### 替代 1: 保留 sigmoid，仅调整阈值
- 优点：改动最小
- 缺点：问题 2、3、4、5 不解决

### 替代 2: 纯元数据评分（只用表大小/索引/分布）
- 优点：评分完全基于真实数据库行为
- 缺点：忽略 SQL 结构风险（如 LIKE_PREFIX 无论表大小都很危险）

### 替代 3: OWASP Risk Rating 框架（可能性 × 严重度 × 可利用性）
- 优点：学术框架
- 缺点：对于 SQL 性能问题，过度复杂，不直接适用

---

## 决策（已确认）

1. **SELECT_STAR 大表上升为 WARNING**
   - 决定：INFO → WARNING（大表时）
   - 理由：`SELECT *` 在大表上有网络传输、内存压力、schema 变更三大风险

2. **LIKE_PREFIX 有全文索引列降为 WARNING**
   - 决定：有全文索引时降为 WARNING，否则保持 CRITICAL
   - 实现：在 `resolve_severity()` 中增加降级逻辑
   - 理由：全文索引确实能加速 `LIKE '%keyword'`，标 CRITICAL 产生误报

3. **不实现自定义 RiskFactor 注册**
   - 决定：硬编码注册表
   - 理由：YAML/JSON 注册是过度工程，14 个因子覆盖主要场景

4. **调整 composite_score 分段边界**
   - 决定：
     ```python
     if critical_count >= 2: return 0.95
     if critical_count == 1: return 0.85 + min(warning_count * 0.03, 0.10)  # 0.85–0.95
     if warning_count >= 3:  return 0.70 + min(info_count * 0.02, 0.10)       # 0.70–0.80
     if warning_count >= 1:  return 0.50 + min(warning_count * 0.05, 0.20)   # 0.50–0.70
     if info_count >= 2:     return 0.30 + min(info_count * 0.05, 0.20)     # 0.30–0.50
     ```
   - 理由：WARNING 贡献减半，1 CRITICAL + N WARNING 上界收到 0.95（留空间给 2 CRITICAL 的 0.95）

---

## 参考

- Snyk Risk Classification: https://snyk.io/security-risk-levels/
- OWASP Risk Rating: https://owasp.org/www-community/OWASP_Risk_Rating_Methodology
- SQL Server Database Engine Tuning Advisor: severity classification
- Snyk "Critical = will result in system compromise" vs "High = significant impact"
