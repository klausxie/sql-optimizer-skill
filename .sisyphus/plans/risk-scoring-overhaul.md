# Risk Scoring System Overhaul — ULW 执行计划

**生成日期**: 2026-04-01
**设计文档**: `docs/decisions/DECISION-006-risk-scoring-overhaul.md`
**状态**: Proposed

---

## 1. 背景与目标

### 核心目标

用完全可解释的 severity-tiered 系统替代当前任意的 sigmoid 评分 + 0.7/0.4 阈值。

### 需要解决的问题

| 问题 | 当前状态 | 目标状态 |
|------|---------|---------|
| P1: 阈值无设计来源 | HIGH >= 0.7, MEDIUM >= 0.4 是"拍脑袋"值 | severity presence 规则驱动 |
| P2: sigmoid 掩盖真实风险 | 5 条规则和 10 条规则都被压缩到 0.83-0.91 | composite_score 由 severity 计数推导 |
| P3: 风险因素不可解释 | `score_reasons` 只返回内部 tag | 每个因子包含 explanation + remediation |
| P4: 元数据与语法混用量表 | `large table (+2.0)` 和 `SELECT_STAR (+2.0)` 等权 | 条件性 severity 升级规则 |
| P5: 分类结果无业务语义 | `score >= 0.7 → HIGH` 无法回答业务含义 | risk_level 有明确业务含义 |

### 约束

- **向后兼容**: ParseOutput contract 只增不减，`risk_score` 字段必须保留
- **`score_reasons` 格式不变**: 继续由 factor code 填充
- **Commit 格式**: 中文提交信息
- **ULW 模式**: Large 级别任务，Final Wave 四维度验收

---

## 2. 文件归属表

| 文件 | 所有者任务 | 其他任务 | 状态 |
|------|-----------|---------|------|
| `common/risk_assessment.py` (NEW) | Task 2a | - | 待创建 |
| `common/rules.py` | Task 2b | Task 3a (只读) | 待修改 |
| `stages/branching/risk_scorer.py` | Task 3a | - | 待修改 |
| `stages/branching/branch_generator.py` | Task 3b | - | 待修改 |
| `contracts/parse.py` | Task 4a | Task 3a, 3b (只读) | 待修改 |
| `common/stage_report_generator.py` | Task 5a | - | 待修改 |
| `stages/parse/stage.py` | Task 4b | - | 待修改 |
| `common/parse_stats.py` | Task 5b | - | 待修改 |

---

## 3. Wave/Phase 分解

```
Wave 1 (并行): 基础设施
├── Task 1: lint 配置初始化
└── Task 2a: common/risk_assessment.py (RiskFactor, RiskAssessment, Severity, Domain, ImpactType, RISK_FACTOR_REGISTRY)

Wave 2 (串行，依赖 Wave 1 Task 2a):
├── Task 2b: common/rules.py 重构 (RiskFactor 注册表替代 RiskRule，删除 sigmoid)
└── Task 3a: stages/branching/risk_scorer.py 重构 (返回 RiskAssessment)

Wave 3 (并行，依赖 Task 2b, 3a):
├── Task 3b: stages/branching/branch_generator.py (消费 RiskAssessment)
├── Task 4a: contracts/parse.py (SQLBranch 新增 risk_factors, risk_level)
└── Task 4b: stages/parse/stage.py (RiskAssessment 序列化)

Wave 4 (并行，依赖 Task 4a, 4b):
├── Task 5a: common/stage_report_generator.py (渲染因子卡片，使用 risk_level)
└── Task 5b: common/parse_stats.py (使用 risk_level 替代 >= 0.7 阈值)

Wave FINAL: 验收
└── Task 6: Final Wave 验收 (F1-F4)
```

---

## 4. 任务详情

### Task 1: lint 配置初始化

**What to do**:
- 确认 `lint-init` skill 已加载
- 验证 Python lint 配置正确
- 运行 `ruff check python/sqlopt/common/risk_assessment.py` 等新文件时有正确规则

**Acceptance Criteria**:
- [ ] ruff 配置覆盖新增文件
- [ ] 无新增 lint 错误

**Recommended Agent Profile**:
- **Category**: quick
- **Skills**: lint-init

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1
- **Blocks**: None

**QA Scenarios**:
```
Scenario: lint 配置验证
Steps:
  1. 运行 ruff check python/sqlopt/common/risk_assessment.py
  2. 确认无 import 错误
Expected Result: lint 通过
```

---

### Task 2a: 新建 `common/risk_assessment.py`

**What to do**:
创建以下内容：
```python
# Enums
class Severity(Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"

class Domain(Enum):
    SYNTACTIC = "SYNTACTIC"
    METADATA = "METADATA"

class ImpactType(Enum):
    FULL_SCAN = "full_scan"
    INDEX_BYPASS = "index_bypass"
    ROW_AMPLIFICATION = "row_amplification"
    MEMORY_PRESSURE = "memory_pressure"
    IO_SPIKE = "io_spike"

# RiskFactor dataclass
@dataclass
class RiskFactor:
    code: str
    severity: Severity
    domain: Domain
    weight: float
    explanation_template: str
    impact_type: ImpactType
    remediation_template: str
    context: dict = field(default_factory=dict)
    mysql_note: str = ""
    postgresql_note: str = ""

    def render_explanation(self) -> str: ...
    def render_remediation(self) -> str: ...

# RISK_FACTOR_REGISTRY — 包含设计文档中所有因子
# LIKE_PREFIX, FUNCTION_ON_INDEXED_COLUMN, NO_INDEX_ON_FILTER, NOT_IN_LARGE_TABLE (CRITICAL)
# DEEP_OFFSET, SUBQUERY, JOIN_WITHOUT_INDEX, IN_CLAUSE_LARGE, UNION_WITHOUT_ALL, SKEWED_DISTRIBUTION (WARNING)
# SELECT_STAR, DISTINCT, HIGH_NULL_RATIO, LOW_CARDINALITY (INFO)

# RiskAssessment dataclass
@dataclass
class RiskAssessment:
    factors: list[RiskFactor]

    @property
    def critical_count(self) -> int: ...
    @property
    def warning_count(self) -> int: ...
    @property
    def info_count(self) -> int: ...
    @property
    def composite_score(self) -> float: ...  # 0.95/0.80/0.70/0.50/0.30/0.10 分段
    @property
    def risk_level(self) -> str: ...  # HIGH/MEDIUM/LOW
    @property
    def worst_factor(self) -> RiskFactor | None: ...

# resolve_severity() 函数 — severity 升级规则
# INFO → WARNING: 大表 (table_size == "large") 或 row_count > 100,000
# WARNING → CRITICAL: 大表 + 无索引 或 row_count > 1,000,000
```

**Acceptance Criteria**:
- [ ] `Severity`, `Domain`, `ImpactType` 枚举正确
- [ ] `RiskFactor` 包含所有必需字段
- [ ] `RiskAssessment.composite_score` 分段正确
- [ ] `RiskAssessment.risk_level` 规则正确
- [ ] `resolve_severity()` 升级规则正确
- [ ] `RISK_FACTOR_REGISTRY` 包含设计文档中所有 14 个因子

**Recommended Agent Profile**:
- **Category**: deep
- **Skills**: 无特殊需求

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1
- **Blocks**: Task 2b, Task 3a

**QA Scenarios**:
```
Scenario: RiskAssessment.composite_score 分段验证
Steps:
  1. 创建 2 个 CRITICAL 因子
  2. 验证 composite_score == 0.95
Expected Result: 分数正确

Scenario: RiskAssessment.risk_level 验证
Steps:
  1. 创建 1 个 CRITICAL 因子
  2. 验证 risk_level == "HIGH"
  3. 创建 2 个 WARNING 因子
  4. 验证 risk_level == "MEDIUM"
Expected Result: 等级正确

Scenario: resolve_severity 升级验证
Steps:
  1. SELECT_STAR (INFO) + table_size="large" → WARNING
  2. DEEP_OFFSET (WARNING) + table_size="large" + has_index=False → CRITICAL
Expected Result: 升级正确
```

---

### Task 2b: `common/rules.py` 重构

**What to do**:
- 保留 `RiskRule` 类（向后兼容）但不作为主要风险检测
- 创建 `_detect_factors()` 函数，使用 `RISK_FACTOR_REGISTRY` 进行检测
- 删除 `sigmoid` 归一化（`normalized_score = 1.0 - 1.0 / (1.0 + score)`）
- 保留 `evaluate_phase1()` 和 `evaluate_phase2()` 返回格式（向后兼容）
- 新增 `_detect_factors()` 返回 `list[RiskFactor]`

**Acceptance Criteria**:
- [ ] `evaluate_phase2()` 内部使用 `RISK_FACTOR_REGISTRY` 检测
- [ ] 删除 sigmoid 归一化
- [ ] `RiskRuleRegistry` 向后兼容，不破坏现有调用方
- [ ] Phase 1 和 Phase 2 规则映射到新的 RiskFactor code

**Recommended Agent Profile**:
- **Category**: deep
- **Skills**: 无特殊需求

**Parallelization**:
- **Can Run In Parallel**: NO (依赖 Task 2a)
- **Parallel Group**: Wave 2
- **Blocks**: Task 3a

**QA Scenarios**:
```
Scenario: evaluate_phase2 返回 RiskFactor 列表
Steps:
  1. 调用 evaluate_phase2("SELECT * FROM users WHERE name LIKE '%test'", [], {})
  2. 验证返回的因子包含 SELECT_STAR 和 LIKE_PREFIX
Expected Result: 因子检测正确

Scenario: sigmoid 归一化已删除
Steps:
  1. 检查 rules.py 源代码
  2. 确认不存在 "1.0 - 1.0 / (1.0 + score)" 模式
Expected Result: sigmoid 已删除
```

---

### Task 3a: `stages/branching/risk_scorer.py` 重构

**What to do**:
- `score_branch()` 返回 `RiskAssessment` 而非 `tuple[float, list[str]]`
- 新增 `score_branch_ex()` 方法返回完整 `RiskAssessment`（含因子列表）
- 保留 `score_branch()` 向后兼容版本（调用新方法，仅返回旧格式）
- `score_dimension()` 仍返回 `float`（Phase 1 无需变更）

**Acceptance Criteria**:
- [ ] `score_branch()` 返回 `RiskAssessment` 对象
- [ ] `RiskAssessment` 包含 `factors`, `composite_score`, `risk_level`, `worst_factor`
- [ ] 向后兼容：`score_branch()` 仍可通过属性访问 `composite_score` 和 `score_reasons`（从 factors 派生）

**Recommended Agent Profile**:
- **Category**: deep
- **Skills**: 无特殊需求

**Parallelization**:
- **Can Run In Parallel**: NO (依赖 Task 2b)
- **Parallel Group**: Wave 2
- **Blocks**: Task 3b

**QA Scenarios**:
```
Scenario: score_branch 返回 RiskAssessment
Steps:
  1. 调用 score_branch("SELECT * FROM users", [], [])
  2. 验证返回类型是 RiskAssessment
  3. 验证 composite_score 和 risk_level 属性存在
Expected Result: 类型正确

Scenario: 向后兼容验证
Steps:
  1. 调用 score_branch()
  2. 验证可以访问 .composite_score 属性
  3. 验证可以访问 .score_reasons 属性（从 factors 派生）
Expected Result: 兼容
```

---

### Task 3b: `stages/branching/branch_generator.py` 消费 RiskAssessment

**What to do**:
- `generate()` 方法中调用 `scorer.score_branch()` 获取 `RiskAssessment`
- 填充 `branch["risk_score"] = assessment.composite_score`（向后兼容）
- 填充 `branch["score_reasons"] = [f.code for f in assessment.factors]`（向后兼容）
- **新增**: 填充 `branch["risk_factors"] = [f.to_dict() for f in assessment.factors]`
- **新增**: 填充 `branch["risk_level"] = assessment.risk_level`

**Acceptance Criteria**:
- [ ] 分支字典包含 `risk_score`, `score_reasons`（向后兼容）
- [ ] 分支字典包含 `risk_factors` (list[dict])
- [ ] 分支字典包含 `risk_level` (str)
- [ ] `risk_factors` 每项包含: code, severity, domain, explanation, remediation, context, impact_type

**Recommended Agent Profile**:
- **Category**: deep
- **Skills**: 无特殊需求

**Parallelization**:
- **Can Run In Parallel**: NO (依赖 Task 3a)
- **Parallel Group**: Wave 3
- **Blocks**: Task 4a, 4b

**QA Scenarios**:
```
Scenario: branch 字典包含新字段
Steps:
  1. 生成包含 LIKE_PREFIX 的分支
  2. 验证 branch["risk_level"] == "HIGH"
  3. 验证 branch["risk_factors"] 包含 LIKE_PREFIX 因子
  4. 验证 branch["risk_factors"][0]["explanation"] 非空
Expected Result: 字段完整
```

---

### Task 4a: `contracts/parse.py` 新增字段

**What to do**:
- `SQLBranch` 新增 `risk_factors: list[dict] = field(default_factory=list)`
- `SQLBranch` 新增 `risk_level: str | None = None`
- 更新 `to_json()` 序列化新字段
- 更新 `from_json()` 反序列化新字段（使用 `.get()` 回退）

**Acceptance Criteria**:
- [ ] `SQLBranch` 包含 `risk_factors` 和 `risk_level` 字段
- [ ] `to_json()` 正确序列化
- [ ] `from_json()` 反序列化时旧 JSON 仍可工作（`.get()` 回退）
- [ ] 向后兼容：现有 JSON 文件无需修改

**Recommended Agent Profile**:
- **Category**: deep
- **Skills**: 无特殊需求

**Parallelization**:
- **Can Run In Parallel**: NO (依赖 Task 3b)
- **Parallel Group**: Wave 3
- **Blocks**: Task 5a, 5b

**QA Scenarios**:
```
Scenario: 向后兼容验证
Steps:
  1. 用旧 JSON（无 risk_factors/risk_level）调用 from_json()
  2. 验证返回的 SQLBranch risk_factors == []
  3. 验证返回的 SQLBranch risk_level is None
Expected Result: 回退正确

Scenario: 新字段序列化验证
Steps:
  1. 创建包含 risk_factors 和 risk_level 的 SQLBranch
  2. 调用 to_json()
  3. 再调用 from_json()
  4. 验证 risk_factors 和 risk_level 一致
Expected Result: 序列化正确
```

---

### Task 4b: `stages/parse/stage.py` 序列化 RiskAssessment

**What to do**:
- `_to_sql_branch()` 函数将分支字典转换为 `SQLBranch` 时，填充新字段
- `_write_output()` 序列化时包含 `risk_factors` 和 `risk_level`

**Acceptance Criteria**:
- [ ] `_to_sql_branch()` 处理 `risk_factors` 和 `risk_level`
- [ ] `_write_output()` 写入的 JSON 包含新字段
- [ ] 单元 JSON 文件格式正确

**Recommended Agent Profile**:
- **Category**: deep
- **Skills**: 无特殊需求

**Parallelization**:
- **Can Run In Parallel**: NO (依赖 Task 3b)
- **Parallel Group**: Wave 3
- **Blocks**: Task 5a, 5b

**QA Scenarios**:
```
Scenario: 解析阶段输出验证
Steps:
  1. 运行 parse stage（mock 模式）
  2. 检查输出的 unit JSON 文件
  3. 验证分支包含 risk_factors 和 risk_level
Expected Result: JSON 正确
```

---

### Task 5a: `common/stage_report_generator.py` 渲染因子卡片

**What to Do**:
- 新增 HTML CSS: `.risk-factor`, `.severity-badge`, `.factor-explanation`, `.factor-remediation`, `.metadata-upgraded`
- 修改 `generate_parse_report()` 中的分支渲染逻辑
- 使用 `risk_level` 替代阈值判断（`risk.level === 'HIGH'` 而非 `risk_score >= 0.7`）
- 渲染每个因子的独立卡片（包含 explanation + remediation）
- 显示 severity 升级标注（如 "↑ upgraded from WARNING: large table"）

**Acceptance Criteria**:
- [ ] 风险卡片使用 `.risk-card` + `.risk-level-{level}` class
- [ ] 每个因子独立展示，包含 explanation 和 remediation
- [ ] `risk_level` 显示而非 `>= 0.7` 阈值判断
- [ ] CRITICAL/WARNING/INFO 使用不同颜色 badge
- [ ] 升级因子显示 "(↑ upgraded from WARNING: large table)" 标注

**Recommended Agent Profile**:
- **Category**: deep
- **Skills**: 无特殊需求

**Parallelization**:
- **Can Run In Parallel**: NO (依赖 Task 4a, 4b)
- **Parallel Group**: Wave 4
- **Blocks**: Task 6

**QA Scenarios**:
```
Scenario: HTML 报告因子卡片渲染
Steps:
  1. 生成包含多个因子的 parse report HTML
  2. 检查 HTML 包含 .risk-factor 元素
  3. 验证每个因子包含 explanation 和 remediation
Expected Result: HTML 正确

Scenario: risk_level 而非阈值判断
Steps:
  1. 检查 HTML 源代码
  2. 确认不存在 "score >= 0.7" 或 "score >= 0.4" 模式
  3. 确认使用 risk_level 属性判断
Expected Result: 使用 risk_level
```

---

### Task 5b: `common/parse_stats.py` 使用 risk_level

**What to Do**:
- `build_parse_stage_stats()` 中 `high_risk_branches`/`medium_risk_branches`/`low_risk_branches` 改用 `risk_level` 判断
- 删除 `>= 0.7` 和 `>= 0.4` 的阈值判断
- 其他统计逻辑不变

**Acceptance Criteria**:
- [ ] `high_risk_branches` 使用 `risk_level == "HIGH"` 判断
- [ ] `medium_risk_branches` 使用 `risk_level == "MEDIUM"` 判断
- [ ] `low_risk_branches` 使用 `risk_level == "LOW"` 判断
- [ ] 删除所有 `>= 0.7` 和 `>= 0.4` 的阈值判断代码

**Recommended Agent Profile**:
- **Category**: deep
- **Skills**: 无特殊需求

**Parallelization**:
- **Can Run In Parallel**: NO (依赖 Task 4a, 4b)
- **Parallel Group**: Wave 4
- **Blocks**: Task 6

**QA Scenarios**:
```
Scenario: risk_level 判断验证
Steps:
  1. 检查 parse_stats.py 源代码
  2. 确认不存在 ">= 0.7" 或 ">= 0.4" 模式
  3. 确认使用 risk_level 属性
Expected Result: 使用 risk_level
```

---

### Task 6: Final Wave 验收

**F1: Plan Compliance Audit** (执行者: oracle)
- [ ] 所有 Must Have 已实现
- [ ] 所有 Must NOT Have 未实现（无破坏性更改）
- [ ] 向后兼容保持

**F2: Code Quality Review** (执行者: unspecified-high)
- [ ] ruff check 通过
- [ ] 无新增 type error
- [ ] 17 个 pre-existing Pyright 错误未增加

**F3: Manual QA** (执行者: unspecified-high + playwright)
- [ ] 运行 `sqlopt run 2` 验证 parse stage 正常
- [ ] 检查生成的 HTML 报告包含因子卡片
- [ ] 验证 risk_level 正确显示

**F4: Scope Fidelity Check** (执行者: deep)
- [ ] 无功能蔓延
- [ ] 变更范围与设计文档一致

---

## 5. 开放问题决策（实施前必须确认）

| # | 问题 | 当前设计 | 需确认 |
|---|------|---------|--------|
| Q1 | SELECT_STAR 在大表上报 WARNING 还是 INFO？ | INFO → WARNING（大表时） | 确认是否按设计文档 |
| Q2 | LIKE_PREFIX 在有全文索引列上报 CRITICAL 还是 WARNING？ | 总是 CRITICAL | 确认是否按设计文档 |
| Q3 | 是否需要支持自定义 RiskFactor 注册（YAML/JSON）？ | 硬编码注册表 | 确认本次范围 |
| Q4 | composite_score 分段边界是否合适？ | 0.95/0.80/0.70/0.50/0.30/0.10 | 确认是否按设计文档 |

---

## 6. 实施顺序

```
1. Task 1 (Wave 1, Quick)
   └─ lint 配置确认

2. Task 2a (Wave 1, 并行)
   └─ 创建 risk_assessment.py

3. Task 2b (Wave 2, 串行)
   └─ 重构 rules.py

4. Task 3a (Wave 2, 串行)
   └─ 重构 risk_scorer.py

5. Task 3b (Wave 3, 并行)
   └─ 修改 branch_generator.py

6. Task 4a (Wave 3, 并行)
   └─ 修改 contracts/parse.py

7. Task 4b (Wave 3, 并行)
   └─ 修改 stages/parse/stage.py

8. Task 5a (Wave 4, 并行)
   └─ 修改 stage_report_generator.py

9. Task 5b (Wave 4, 并行)
   └─ 修改 parse_stats.py

10. Task 6 (Final Wave)
    └─ Final Wave 验收
```

---

## 7. 依赖关系图

```
Task 1 ──────────────────┐
                        │
Task 2a ──┬────────────┤
          │            │
Task 2b ──┴──→ Task 3a ┴──→ Task 3b ──┬──→ Task 4a ──┬──→ Task 5a ─┐
                                        │              │             │
                                        └──→ Task 4b ──┘             │
                                                                         │
                                                                    Task 6 (Final)
```

---

## 8. 测试策略

| 任务 | 测试文件 | 关键验证点 |
|------|---------|-----------|
| Task 2a | `tests/unit/test_risk_assessment.py` (NEW) | composite_score 分段, risk_level 规则, resolve_severity 升级 |
| Task 2b | `tests/unit/test_rules.py` | 因子检测正确, sigmoid 已删除 |
| Task 3a | `tests/unit/test_risk_scorer.py` | 返回 RiskAssessment 类型 |
| Task 3b | `tests/unit/test_branch_generator.py` | 分支包含新字段 |
| Task 4a | `tests/unit/test_parse.py` (existing) | 向后兼容 |
| Task 4b | `tests/unit/test_parse_stage.py` (existing) | JSON 输出正确 |
| Task 5a | 手动验证 | HTML 渲染正确 |
| Task 5b | `tests/unit/test_parse_stats.py` (existing) | 统计正确 |
