# 数据契约

## 目录结构

```
contracts/
├── README.md                    # 本文件
├── CHANGELOG.md                # 契约变更日志
├── versions.json               # 版本列表
├── schemas/                    # 当前版本契约定义
│   ├── sqlunit.schema.json
│   ├── optimization_proposal.schema.json
│   ├── baseline_result.schema.json
│   ├── acceptance_result.schema.json
│   ├── patch_result.schema.json
│   ├── verification_record.schema.json
│   ├── verification_summary.schema.json
│   ├── run_report.schema.json
│   ├── run_index.schema.json
│   ├── fragment_record.schema.json
│   ├── llm_candidate.schema.json
│   ├── llm_trace.schema.json
│   ├── policy.schema.json
│   ├── ops_topology.schema.json
│   ├── ops_health.schema.json
│   └── sql_artifact_index_row.schema.json
│
└── snapshots/                # 历史版本契约快照
    ├── v1.0.0/
    └── v1.1.0/
```

## V8 阶段契约

| 阶段 | 输入 Schema | 输出 Schema |
|------|------------|-------------|
| discovery | - | `sqlunit.schema.json` |
| branching | `sqlunit.schema.json` | `sqlunit.schema.json` (扩展branches) |
| pruning | `sqlunit.schema.json` | `risks.json` (自定义) |
| baseline | `sqlunit.schema.json` | `baseline_result.schema.json` |
| optimize | `baseline_result.schema.json` | `optimization_proposal.schema.json` |
| validate | `optimization_proposal.schema.json` | `acceptance_result.schema.json` |
| patch | `acceptance_result.schema.json` | `patch_result.schema.json` |

## 核心 Schema

### sqlunit.schema.json

Discovery 阶段输出的 SQL 单元。

```json
{
  "sqlKey": "com.example.UserMapper.findByEmail",
  "xmlPath": "/path/to/UserMapper.xml",
  "namespace": "com.example",
  "statementId": "findByEmail",
  "statementType": "SELECT",
  "variantId": "v1",
  "sql": "SELECT * FROM users WHERE email = #{email}",
  "parameterMappings": [],
  "paramExample": {"email": "test@example.com"},
  "locators": {"statementId": "findByEmail"},
  "riskFlags": ["DOLLAR_SUBSTITUTION"],
  "templateSql": "SELECT * FROM users WHERE email = #{email}",
  "dynamicFeatures": ["IF", "WHERE"],
  "branches": [...],
  "branchCount": 1
}
```

### baseline_result.schema.json

Baseline 阶段输出的执行计划。

```json
{
  "sqlKey": "com.example.UserMapper.findByEmail",
  "executionTimeMs": 12.5,
  "rowsExamined": 1000,
  "rowsReturned": 1,
  "explainPlan": {
    "plan_text": "...",
    "scan_type": "INDEX_RANGE_SCAN",
    "estimated_cost": 5.2,
    "estimated_rows": 1
  },
  "databasePlatform": "mysql",
  "sampleParams": {"email": "test@example.com"},
  "actualExecutionTimeMs": 12.5,
  "indexUsed": "idx_email"
}
```

### optimization_proposal.schema.json

Optimize 阶段生成的优化建议。

```json
{
  "sqlKey": "com.example.UserMapper.searchByName",
  "issues": ["PREFIX_WILDCARD"],
  "dbEvidenceSummary": {...},
  "planSummary": {...},
  "suggestions": [
    {
      "type": "INDEX_HINT",
      "originalSql": "SELECT * FROM users WHERE name LIKE '%' || #{name} || '%'",
      "suggestedSql": "SELECT * FROM users USE INDEX(idx_name) WHERE name LIKE #{name} || '%'",
      "rationale": "Remove leading wildcard to enable index usage"
    }
  ],
  "verdict": "ACTIONABLE",
  "estimatedBenefit": "HIGH",
  "confidence": "HIGH"
}
```

## Schema 验证

```python
from jsonschema import validate

# 验证 sqlunit
with open("contracts/schemas/sqlunit.schema.json") as f:
    schema = json.load(f)

validate(instance=sqlunit_data, schema=schema)
```

## 验证命令行

```bash
# 验证所有契约
python3 scripts/schema_validate_all.py

# 验证单个契约
python3 scripts/schema_validate.py contracts/schemas/sqlunit.schema.json
```

## 契约变更

当需要修改契约时：

1. 在 `CHANGELOG.md` 中记录变更
2. 更新 `schemas/` 中的定义
3. 如果是破坏性变更，创建新的 snapshot：`snapshots/v1.x.0/`
4. 更新 `versions.json`

## 优先级

当代码行为与文档冲突时：
1. `contracts/*.schema.json` (最高)
2. 当前代码实现
3. 历史文档
