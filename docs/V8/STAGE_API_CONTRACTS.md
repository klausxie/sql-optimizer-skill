# SQL Optimizer V8 阶段 API 与数据契约规范

> 状态：**目标规范（Target Spec）**  
> 版本：v1  
> 适用范围：Discovery → Branching → Pruning → Baseline → Optimize → Validate → Patch（以及可选 Report）

---

## 1. 文档目的

本文档用于把 **V8 七阶段工作流的接口定义、输入输出契约、阶段依赖和样例数据** 明确写成一份统一规范，后续实现、重构、测试和验收均应以本文档为目标。

**这份文档的定位是“目标实现规范”，不是对当前代码现状的被动描述。**

也就是说：

- 如果当前代码行为与本文档不一致，**应以后续代码收敛到本文档为准**。
- 如果 `contracts/schemas/*.json` 与本文档有冲突，**优先以 schema 和本文档共同约束来调整实现**。
- 如果某个阶段在运行期需要额外产物文件，可以增加内部文件，但**阶段边界的输入/输出契约必须稳定且可验证**。

---

## 2. 设计原则

## 2.1 单一阶段边界

每个阶段都必须明确回答 4 个问题：

1. **依赖哪些上游阶段**
2. **读取什么输入契约**
3. **产出什么输出契约**
4. **输出写到哪里，如何被下游消费**

## 2.2 契约优先

阶段之间传递的数据必须是：

- 结构化对象
- 可落盘
- 可做 JSON Schema 校验
- 可被下游稳定读取

## 2.3 阶段职责单一

- 一个阶段只负责一个明确的职责边界
- 阶段可以读多个上游文件，但必须有**主输入契约**
- 阶段不得把“临时计算细节”混成对外契约

## 2.4 可恢复执行

每个阶段的输出都应当可独立落盘，且能够支持：

- `run`
- `resume`
- `status`
- `report rebuild`

## 2.5 实现双形态统一

V8 中允许两种实现入口，但语义必须一致：

1. **阶段级 API**：`Stage.execute(context) -> StageResult`
2. **单对象 API**：`execute_one(...) -> dict`

约束如下：

- `execute_one()` 负责“处理一个边界对象”
- `Stage.execute()` 负责“批量读取输入、循环调用 execute_one、持久化输出、汇总 StageResult”
- 两者的输入输出语义必须一致

---

## 3. 核心接口总览

## 3.1 Stage 抽象接口

所有阶段统一实现以下接口：

```python
class Stage(ABC):
    name: str
    version: str
    dependencies: list[str]

    @abstractmethod
    def execute(self, context: StageContext) -> StageResult:
        ...

    @abstractmethod
    def get_input_contracts(self) -> list[str]:
        ...

    @abstractmethod
    def get_output_contracts(self) -> list[str]:
        ...
```

### 语义说明

- `name`: 阶段名，必须与工作流中的阶段名一致
- `version`: 阶段实现版本
- `dependencies`: 上游依赖阶段名列表
- `execute`: 阶段级批处理入口
- `get_input_contracts`: 输入契约名列表
- `get_output_contracts`: 输出契约名列表

---

## 3.2 StageContext

```python
@dataclass
class StageContext:
    run_id: str
    config: dict
    data_dir: Path
    cache_dir: Path
    metadata: dict
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `run_id` | 是 | 当前运行 ID |
| `config` | 是 | 已加载配置 |
| `data_dir` | 是 | 当前 run 目录 |
| `cache_dir` | 否 | 可选缓存目录 |
| `metadata` | 否 | 运行时上下文，例如 `db_reachable`、`selected_sql_keys` |

---

## 3.3 StageResult

```python
@dataclass
class StageResult:
    success: bool
    output_files: list[Path]
    artifacts: dict
    errors: list[str]
    warnings: list[str]
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `success` | 阶段整体是否成功 |
| `output_files` | 本阶段写出的关键文件 |
| `artifacts` | 供状态页/报告消费的摘要信息 |
| `errors` | 阶段错误列表 |
| `warnings` | 阶段警告列表 |

---

## 4. 阶段总表

| 阶段 | 依赖阶段 | 主输入契约 | 主输出契约 | 典型输出文件 |
|------|----------|------------|------------|--------------|
| `discovery` | 无 | 无 | `sqlunit` | `scan.sqlunits.jsonl` |
| `branching` | `discovery` | `sqlunit` | `sqlunit`（补充分支信息） | `scan.sqlunits.jsonl` 或 `branches.jsonl` |
| `pruning` | `branching` | `sqlunit` | `risk_record`（内部文件）+ `sqlunit` 补充风险摘要 | `pruning/risks.jsonl` |
| `baseline` | `branching`, `pruning` | `sqlunit` | `baseline_result` | `baseline.results.jsonl` |
| `optimize` | `baseline` | `baseline_result` | `optimization_proposal` | `proposals.jsonl` |
| `validate` | `optimize` | `optimization_proposal` | `acceptance_result` | `acceptance.jsonl` |
| `patch` | `validate` | `acceptance_result` | `patch_result` | `patches.jsonl` |
| `report`（可选） | `patch` | 聚合读取各阶段结果 | `run_report` | `report.json`, `report.md` |

> 注：`risk_record` 可作为内部契约文件存在，即使当前还没有单独 schema，也应保留“可结构化、可校验”的设计方向。

---

## 5. 统一文件约定

为避免阶段实现分叉，建议统一以下产物命名：

```text
runs/<run_id>/
├── supervisor/
│   ├── meta.json
│   ├── plan.json
│   ├── state.json
│   └── results/
├── scan.sqlunits.jsonl
├── pruning/
│   └── risks.jsonl
├── baseline.results.jsonl
├── proposals.jsonl
├── acceptance.jsonl
├── patches.jsonl
├── report.json
├── report.md
└── report.summary.md
```

### 命名规则

- 阶段边界对象如果是“逐条记录”，优先使用 **JSONL**
- 如果是“单次汇总报表”，使用 **JSON**
- 下游消费时应优先读取边界文件，不要依赖内部临时文件格式

---

## 6. 阶段详细规范

## 6.1 Discovery

### 6.1.1 职责

Discovery 负责：

- 扫描 Mapper XML
- 解析语句定义
- 生成 SQL 单元（`sqlunit`）
- 为后续阶段提供统一的 SQL 边界对象

### 6.1.2 依赖

- 无

### 6.1.3 阶段 API

```python
def execute(self, context: StageContext) -> StageResult
```

```python
def execute_one(
    run_id: str,
    ctx: StageContext,
    mapper_path: str | Path,
) -> dict[str, Any]
```

### 6.1.4 输入契约

- 无

### 6.1.5 输出契约

- 主输出：`sqlunit`
- 落盘文件：`scan.sqlunits.jsonl`
- 写入规则：**每行一个 `sqlunit` 对象**

### 6.1.6 `sqlunit` 最小样例

```json
{
  "sqlKey": "com.example.UserMapper.selectById",
  "xmlPath": "src/main/resources/mapper/UserMapper.xml",
  "namespace": "com.example.UserMapper",
  "statementId": "selectById",
  "statementType": "SELECT",
  "variantId": "base",
  "sql": "SELECT id, name FROM user WHERE id = #{id}",
  "parameterMappings": [
    {"name": "id", "jdbcType": "BIGINT"}
  ],
  "paramExample": {"id": 1001},
  "locators": {
    "statementXPath": "/mapper/select[@id='selectById']"
  },
  "riskFlags": []
}
```

### 6.1.7 成功标准

- 每个可识别 SQL 语句都生成一个合法 `sqlunit`
- 所有 `sqlunit` 均通过 `sqlunit.schema.json` 校验
- `StageResult.artifacts` 至少包含：`sql_unit_count`、`mapper_count`

---

## 6.2 Branching

### 6.2.1 职责

Branching 负责：

- 对动态 SQL 进行分支展开
- 将分支信息补充回 `sqlunit`
- 不改变 `sqlunit` 的身份字段，只增强其执行分支信息

### 6.2.2 依赖

- `discovery`

### 6.2.3 阶段 API

```python
def execute(self, context: StageContext) -> StageResult
```

```python
def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]
```

### 6.2.4 输入契约

- `sqlunit`

### 6.2.5 输出契约

- `sqlunit`（增强版）
- 允许新增字段：`branches`、`branchCount`、`problemBranchCount`
- **输出仍必须保留原有 `sqlunit` 的所有必填字段**

### 6.2.6 输出样例

```json
{
  "sqlKey": "com.example.UserMapper.search",
  "xmlPath": "src/main/resources/mapper/UserMapper.xml",
  "namespace": "com.example.UserMapper",
  "statementId": "search",
  "statementType": "SELECT",
  "variantId": "base",
  "sql": "SELECT * FROM user",
  "parameterMappings": [],
  "paramExample": {},
  "locators": {
    "statementXPath": "/mapper/select[@id='search']"
  },
  "riskFlags": [],
  "branches": [
    {
      "id": 1,
      "conditions": [],
      "sql": "SELECT id, name FROM user",
      "type": "static"
    },
    {
      "id": 2,
      "conditions": ["name != null"],
      "sql": "SELECT id, name FROM user WHERE name LIKE CONCAT('%', #{name}, '%')",
      "type": "conditional"
    }
  ],
  "branchCount": 2,
  "problemBranchCount": 1
}
```

### 6.2.7 成功标准

- 每个输入 `sqlunit` 都得到一个对应输出 `sqlunit`
- `branches[*]` 结构与 `sqlunit.schema.json` 中 `branches` 定义一致
- `StageResult.artifacts` 至少包含：`sql_unit_count`、`total_branch_count`

---

## 6.3 Pruning

### 6.3.1 职责

Pruning 负责：

- 检测风险模式
- 形成风险记录
- 给 `sqlunit` 增补风险摘要
- 为 Baseline 阶段提供“哪些 SQL / 哪些分支值得执行”的依据

### 6.3.2 依赖

- `branching`

### 6.3.3 阶段 API

```python
def execute(self, context: StageContext) -> StageResult
```

```python
def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]
```

### 6.3.4 输入契约

- `sqlunit`（含分支信息）

### 6.3.5 输出契约

Pruning 有两类输出：

1. **边界输出（推荐）**：`risk_record` JSONL
2. **增强输出（可选）**：把风险摘要补回 `sqlunit.riskFlags`

### 6.3.6 `risk_record` 样例

```json
{
  "sqlKey": "com.example.UserMapper.search",
  "risks": [
    {
      "riskType": "prefix_wildcard",
      "severity": "HIGH",
      "message": "LIKE '%x%' may disable index usage",
      "branchIds": [2]
    }
  ],
  "prunedBranches": [2],
  "recommendedForBaseline": true,
  "trace": {
    "stage": "pruning",
    "executor": "risk_detector"
  }
}
```

### 6.3.7 成功标准

- 所有高风险模式均结构化记录
- 需要进入 Baseline 的对象可被明确识别
- `StageResult.artifacts` 至少包含：`sql_unit_count`、`risk_count`

---

## 6.4 Baseline

### 6.4.1 职责

Baseline 负责：

- 执行 EXPLAIN / EXPLAIN ANALYZE / 兼容性采集
- 记录原始 SQL 的执行基线
- 形成可供优化决策使用的 `baseline_result`

### 6.4.2 依赖

- `branching`
- `pruning`

### 6.4.3 阶段 API

```python
def execute(self, context: StageContext) -> StageResult
```

```python
def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]
```

### 6.4.4 输入契约

- `sqlunit`
- 输入对象必须是单个 `sqlunit`，不能用空字典代替阶段输入校验

### 6.4.5 输出契约

- `baseline_result`
- 落盘文件：`baseline.results.jsonl`

### 6.4.6 `baseline_result` 样例

```json
{
  "sql_key": "com.example.UserMapper.search",
  "execution_time_ms": 12.4,
  "rows_scanned": 1520,
  "execution_plan": {
    "node_type": "Seq Scan",
    "index_used": null,
    "cost": 43.21
  },
  "result_hash": "a1b2c3d4e5f6",
  "rows_returned": 20,
  "database_platform": "postgresql",
  "sample_params": {"name": "tom"},
  "actual_execution_time_ms": 12.9,
  "buffer_hit_count": 110,
  "buffer_read_count": 7,
  "explain_plan": {
    "Plan": {"Node Type": "Seq Scan"}
  },
  "trace": {
    "stage": "baseline",
    "sql_key": "com.example.UserMapper.search",
    "executor": "baseline_collector",
    "timestamp": "2026-03-20T00:00:00Z"
  }
}
```

### 6.4.7 成功标准

- 每条进入 baseline 的 SQL 都产出一个合法 `baseline_result`
- 所有结果都通过 `baseline_result.schema.json` 校验
- `StageResult.artifacts` 至少包含：`baseline_count`、`error_count`

---

## 6.5 Optimize

### 6.5.1 职责

Optimize 负责：

- 基于 baseline 证据形成问题诊断
- 生成规则建议和 LLM 候选
- 输出统一的 `optimization_proposal`

### 6.5.2 依赖

- `baseline`

### 6.5.3 阶段 API

```python
def execute(self, context: StageContext) -> StageResult
```

```python
def execute_one(
    baseline_result: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]
```

> 注意：如果实现内部仍需要 `sqlunit` 原文，可通过 `sql_key` 回查，但阶段主输入语义依旧是 `baseline_result`。

### 6.5.4 输入契约

- `baseline_result`

### 6.5.5 输出契约

- `optimization_proposal`
- 落盘文件：`proposals.jsonl`

### 6.5.6 `optimization_proposal` 样例

```json
{
  "sqlKey": "com.example.UserMapper.search",
  "issues": [
    "PREFIX_WILDCARD",
    "FULL_SCAN"
  ],
  "dbEvidenceSummary": {
    "rowsScanned": 1520,
    "nodeType": "Seq Scan",
    "indexUsed": null
  },
  "planSummary": {
    "before": "Seq Scan on user",
    "cost": 43.21
  },
  "suggestions": [
    {
      "id": "rule-prefix-like",
      "source": "rule",
      "title": "将前缀模糊匹配改写为可索引条件",
      "rewrittenSql": "SELECT id, name FROM user WHERE name >= #{namePrefix} AND name < #{namePrefixNext}",
      "benefit": "减少全表扫描概率",
      "risk": "MEDIUM"
    }
  ],
  "verdict": "ACTIONABLE",
  "confidence": "medium",
  "estimatedBenefit": "medium"
}
```

### 6.5.7 成功标准

- 输出必须满足 `optimization_proposal.schema.json`
- `issues`、`dbEvidenceSummary`、`planSummary`、`suggestions`、`verdict` 不能为空缺
- `StageResult.artifacts` 至少包含：`proposal_count`、`actionable_count`

---

## 6.6 Validate

### 6.6.1 职责

Validate 负责：

- 对优化建议进行语义等价性检查
- 做性能对比或说明无法对比的原因
- 汇总安全与交付判断
- 输出 `acceptance_result`

### 6.6.2 依赖

- `optimize`

### 6.6.3 阶段 API

```python
def execute(self, context: StageContext) -> StageResult
```

```python
def execute_one(
    proposal: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    db_reachable: bool,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]
```

### 6.6.4 输入契约

- `optimization_proposal`

### 6.6.5 输出契约

- `acceptance_result`
- 落盘文件：`acceptance.jsonl`

### 6.6.6 `acceptance_result` 样例

```json
{
  "sqlKey": "com.example.UserMapper.search",
  "status": "PASS",
  "rewrittenSql": "SELECT id, name FROM user WHERE name >= #{namePrefix} AND name < #{namePrefixNext}",
  "equivalence": {
    "checked": true,
    "method": "semantic_checker",
    "rowCount": {"before": 20, "after": 20},
    "keySetHash": {"before": "abc", "after": "abc"},
    "rowSampleHash": null,
    "evidenceRefs": ["verification/search/equiv.json"]
  },
  "perfComparison": {
    "checked": true,
    "method": "explain_compare",
    "beforeSummary": {"cost": 43.21},
    "afterSummary": {"cost": 5.32},
    "reasonCodes": [],
    "improved": true,
    "error": null,
    "evidenceRefs": ["verification/search/perf.json"]
  },
  "securityChecks": {
    "sqlInjectionRisk": "PASS",
    "unsafeFunctionRewrite": "PASS"
  },
  "semanticRisk": "LOW",
  "regressionSignals": [],
  "warnings": [],
  "riskFlags": [],
  "selectedCandidateSource": "rule",
  "candidateEvaluations": []
}
```

### 6.6.7 成功标准

- 输出必须满足 `acceptance_result.schema.json`
- 至少保证 `equivalence`、`perfComparison`、`securityChecks` 三大块完整存在
- `StageResult.artifacts` 至少包含：`pass_count`、`fail_count`

---

## 6.7 Patch

### 6.7.1 职责

Patch 负责：

- 读取已通过验证的优化结果
- 生成可交付的补丁
- 记录可应用性、回滚信息、交付说明
- 输出 `patch_result`

### 6.7.2 依赖

- `validate`

### 6.7.3 阶段 API

```python
def execute(self, context: StageContext) -> StageResult
```

```python
def execute_one(
    acceptance: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]
```

### 6.7.4 输入契约

- `acceptance_result`

> 输入契约名必须统一使用 `acceptance_result`，不要再使用 `acceptance` 这样的别名作为阶段边界名。

### 6.7.5 输出契约

- `patch_result`
- 落盘文件：`patches.jsonl`

### 6.7.6 `patch_result` 样例

```json
{
  "sqlKey": "com.example.UserMapper.search",
  "statementKey": "com.example.UserMapper.search",
  "patchFiles": [
    "runs/run_20260320_001/patches/com.example.UserMapper.search.patch"
  ],
  "diffSummary": {
    "filesChanged": 1,
    "hunks": 1,
    "summary": "replace LIKE '%x%' with range predicate"
  },
  "applyMode": "manual",
  "rollback": "restore original mapper backup",
  "selectedCandidateId": "rule-prefix-like",
  "candidatesEvaluated": 1,
  "applicable": true,
  "applyCheckError": null
}
```

### 6.7.7 成功标准

- 输出必须满足 `patch_result.schema.json`
- 必须能够定位补丁文件
- 必须给出 `rollback` 描述
- `StageResult.artifacts` 至少包含：`patch_count`、`applicable_count`

---

## 6.8 Report（可选重建阶段）

### 6.8.1 职责

Report 负责：

- 聚合各阶段结果
- 生成 JSON / Markdown 报告
- 不改变前 7 阶段的边界对象

### 6.8.2 依赖

- `patch`

### 6.8.3 输入

- 聚合读取：`scan.sqlunits.jsonl`、`baseline.results.jsonl`、`proposals.jsonl`、`acceptance.jsonl`、`patches.jsonl`

### 6.8.4 输出契约

- `run_report`

### 6.8.5 `run_report` 最小样例

```json
{
  "run_id": "run_20260320_001",
  "mode": "run",
  "policy": {
    "require_perf_improvement": true,
    "cost_threshold_pct": 10,
    "allow_seq_scan_if_rows_below": 100,
    "semantic_strict_mode": true
  },
  "stats": {
    "sql_units": 10,
    "proposals": 4,
    "acceptance_pass": 2,
    "acceptance_fail": 2,
    "patch_files": 2
  },
  "items": {
    "units": [],
    "proposals": [],
    "acceptance": [],
    "patches": []
  }
}
```

---

## 7. 统一校验规则

## 7.1 阶段边界校验规则

每个阶段在正式处理前后必须做如下校验：

1. **输入校验**：对每个输入对象逐条校验，不允许拿 `{}` 代替真实边界对象
2. **输出校验**：对每个输出对象逐条校验
3. **文件校验**：落盘文件必须可再次读取并通过 schema 校验

## 7.2 错误处理规则

- 单条对象失败：记录错误，允许阶段继续处理下一条
- 阶段级依赖文件缺失：阶段失败
- 输出对象整体不符合 schema：阶段失败

## 7.3 JSONL 读写规则

- 写入：统一使用 JSON / JSONL
- 读取：统一使用 `json.loads()`，**禁止使用 `eval()` 读取 JSONL**

---

## 8. 阶段依赖图

```text
Discovery
  └─ produces sqlunit
       ↓
Branching
  └─ consumes sqlunit
  └─ produces enriched sqlunit
       ↓
Pruning
  └─ consumes enriched sqlunit
  └─ produces risk_record (+ risk summary)
       ↓
Baseline
  └─ consumes sqlunit
  └─ produces baseline_result
       ↓
Optimize
  └─ consumes baseline_result
  └─ produces optimization_proposal
       ↓
Validate
  └─ consumes optimization_proposal
  └─ produces acceptance_result
       ↓
Patch
  └─ consumes acceptance_result
  └─ produces patch_result
       ↓
Report (optional rebuild)
  └─ consumes aggregated stage outputs
  └─ produces run_report
```

---

## 9. 面向实现的落地约束清单

后续代码实现、重构、验收建议按以下顺序收敛：

1. **统一契约名**：`sqlunit` / `baseline_result` / `optimization_proposal` / `acceptance_result` / `patch_result`
2. **统一文件格式**：边界对象优先 JSONL，一行一个对象
3. **统一 execute / execute_one 语义**
4. **统一工作流执行入口**：工作流应优先调用 Stage，而不是维护一套平行但不等价的 `_run_*` 协议
5. **所有阶段都以本文档中的样例结构作为最小兼容目标**

---

## 10. 一句话总结

**本文档定义的不是“现在代码刚好做了什么”，而是“V8 阶段 API 与数据契约应该稳定成什么样子”。后续实现应以这份规范为收敛目标。**
