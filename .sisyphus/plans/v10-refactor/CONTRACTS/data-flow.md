# 阶段间数据流详解

---

## 1. 数据流总览

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              V10 五阶段数据流                                    │
│                                                                                 │
│   ┌─────────┐     ┌─────────┐     ┌────────────┐     ┌──────────┐     ┌─────┐│
│   │  Init   │────▶│  Parse  │────▶│Recognition │────▶│ Optimize │────▶│Result ││
│   └─────────┘     └─────────┘     └────────────┘     └──────────┘     └─────┘│
│        │               │                │                 │                  │    │
│        ▼               ▼                ▼                 ▼                  ▼    │
│   init/           parse/          recognition/        optimize/           result/ │
│   ├─sql_units.json   ├─sql_units.json   baselines.json     proposals.json     patches.json
│   ├─sql_fragments.json  ├─xml_mappings.json                                      │
│   ├─xml_mappings.json   └─risks.json        (仅阶段内部使用)                     │
│   └─table_schemas.json                                                      │
│   (原始XML片段+位置)   (include已解析+更新位置)                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              V10 五阶段数据流                                    │
│                                                                                 │
│   ┌─────────┐     ┌─────────┐     ┌────────────┐     ┌──────────┐     ┌─────┐│
│   │  Init   │────▶│  Parse  │────▶│Recognition │────▶│ Optimize │────▶│Result ││
│   └─────────┘     └─────────┘     └────────────┘     └──────────┘     └─────┘│
│        │               │                │                 │                  │    │
│        ▼               ▼                ▼                 ▼                  ▼    │
│   init/           parse/          recognition/        optimize/           result/ │
│   sql_units.json  sql_units.json   baselines.json     proposals.json     patches.json
│   (纯净SQL)       (带branches)    (性能基线)         (优化建议)          (补丁)   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 各阶段数据详情

### 2.1 Init → Parse（完整示例）

#### Init 输出文件

**文件 1**：`init/sql_units.json`

```json
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "statementId": "search",
    "statementType": "SELECT",
    "xmlPath": "/path/to/UserMapper.xml",
    "xmlContent": "<select id=\"search\">\n  SELECT * FROM users WHERE 1=1\n  <if test=\"name != null\">AND name = #{name}</if>\n  <include refid=\"common/whereClause\"/>\n</select>",
    "parameterMappings": [
      {"name": "name", "jdbcType": "VARCHAR"},
      {"name": "status", "jdbcType": "INTEGER"}
    ],
    "paramExample": {"name": "test", "status": 1},
    "dynamicFeatures": ["IF", "INCLUDE"]
  }
]
```

**文件 2**：`init/sql_fragments.json`

```json
[
  {
    "fragmentId": "common/whereClause",
    "xmlPath": "/path/to/UserMapper.xml",
    "xmlContent": "<sql id=\"whereClause\">\n  <where>\n    <if test=\"_parameter != null\">\n      ${_parameter}\n    </if>\n  </where>\n</sql>"
  }
]
```

**文件 3**：`init/table_schemas.json`

```json
{
  "users": {
    "columns": [...],
    "indexes": [...],
    "database": "postgresql"
  }
}
```

---

#### Parse 输入（直接复用 Init 输出）

Parse 阶段读取：
- `init/sql_units.json` — SQL 单元（含 `<include>` 标签）
- `init/sql_fragments.json` — 片段定义（用于解析 `<include>`）

---

#### Parse 输出文件

**文件 1**：`parse/sql_units.json`（覆盖）

```json
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "statementId": "search",
    "statementType": "SELECT",
    "xmlPath": "/path/to/UserMapper.xml",
    "xmlContent": "<select id=\"search\">\n  SELECT * FROM users WHERE 1=1\n  <if test=\"name != null\">AND name = #{name}</if>\n  <where>\n    <if test=\"_parameter != null\">\n      ${_parameter}\n    </if>\n  </where>\n</select>",
    "parameterMappings": [...],
    "paramExample": {...},
    "dynamicFeatures": ["IF", "WHERE"],
    "branches": [
      {
        "id": 0,
        "conditions": [],
        "sql": "SELECT * FROM users WHERE 1=1",
        "type": "static"
      },
      {
        "id": 1,
        "conditions": ["name IS NOT NULL"],
        "sql": "SELECT * FROM users WHERE 1=1 AND name = #{name}",
        "type": "conditional"
      }
    ],
    "branchCount": 2,
    "problemBranchCount": 0
  }
]
```

**文件 2**：`parse/risks.json`

```json
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "risks": [...],
    "prunedBranches": [],
    "recommendedForBaseline": true
  }
]
```

---

#### Init → Parse 数据变换

| 变换 | 说明 |
|------|------|
| `xmlContent` | `<include refid="xxx">` 被替换为实际片段内容 |
| 新增 `branches` | `<if>` 标签被展开为多个分支 |
| `dynamicFeatures` | `INCLUDE` 被移除，新增 `WHERE`（如果片段中有） |
| `sql_fragments.json` | 不再需要（已在 `xmlContent` 中展开） |

---

### 2.2 Parse → Recognition

**文件**：`parse/sql_units.json`（覆盖 Init 输出，添加 branches）

**内容**：SQL 单元列表（带展开后的分支）

```json
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "statementId": "search",
    "sql": "SELECT * FROM users WHERE 1=1",
    "branches": [
      {
        "id": 0,
        "conditions": [],
        "sql": "SELECT * FROM users WHERE 1=1",
        "type": "static"
      },
      {
        "id": 1,
        "conditions": ["name IS NOT NULL"],
        "sql": "SELECT * FROM users WHERE 1=1 AND name = #{name}",
        "type": "conditional"
      }
    ],
    "branchCount": 2,
    "problemBranchCount": 0
  }
]
```

**Recognition 对 Parse 的期望**：
| 字段 | 必须 | 说明 |
|------|------|------|
| `sqlKey` | ✅ | 用于生成 `sqlKey:branch:Id` 格式 |
| `branches` | ✅ | 分支列表 |
| `branches[].sql` | ✅ | 该分支的实际 SQL |
| `branches[].id` | ✅ | 分支 ID |

---

### 2.3 Recognition → Optimize

**文件**：
- `recognition/baselines.json` — 性能基线
- `parse/sql_units.json` — SQL 单元（含 Mapper 上下文）
- `init/table_schemas.json` — **表统计信息（行数）**

**内容**：性能基线列表

```json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "executionTimeMs": 12.5,
    "rowsScanned": 1520,
    "rowsReturned": 1,
    "executionPlan": {
      "nodeType": "Seq Scan",
      "indexUsed": null,
      "cost": 43.21
    },
    "databasePlatform": "postgresql",
    "sampleParams": {}
  }
]
```

**表统计信息**（用于判断优化价值）：

```json
// init/table_schemas.json
{
  "users": {
    "statistics": {
      "rowCount": 1520347
    }
  }
}
```

**Optimize 对 Recognition 的期望**：
| 字段 | 必须 | 说明 |
|------|------|------|
| `sqlKey` | ✅ | 格式必须是 `key:branch:Id` |
| `executionTimeMs` | ✅ | 执行时间 |
| `rowsScanned` | ✅ | 扫描行数 |
| `executionPlan` | ✅ | 执行计划 |

**Optimize 对 table_schemas 的期望**：
| 字段 | 必须 | 说明 |
|------|------|------|
| `statistics.rowCount` | ✅ | 表行数（判断优化价值） |

---

### 2.4 Optimize → Result

**文件**：
- `optimize/proposals.json` — 可验证的语法级优化（→ Patch）
- `optimize/recommendations.json` — 不可验证的结构级建议（→ Report）

**内容**：`proposals.json`（语法级优化 → Patch）

```json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "optimizationType": "SYNTAX",
    "baseline": {
      "sql": "SELECT * FROM users WHERE name LIKE '%' || #{name}",
      "executionTimeMs": 150.5,
      "rowsScanned": 1520347,
      "rowsReturned": 100,
      "explainPlan": {
        "format": "json",
        "version": "PostgreSQL 15",
        "raw": {
          "Plan": {
            "Node Type": "Seq Scan",
            "Relation Name": "users",
            "Actual Rows": 100,
            "Actual Time": 150.500
          }
        }
      }
    },
    "rewritten": {
      "sql": "SELECT id, name FROM users WHERE name LIKE #{name} || '%'",
      "executionTimeMs": 5.2,
      "rowsScanned": 100,
      "rowsReturned": 100,
      "explainPlan": {
        "format": "json",
        "version": "PostgreSQL 15",
        "raw": {
          "Plan": {
            "Node Type": "Index Scan",
            "Index Name": "idx_user_name",
            "Actual Rows": 100,
            "Actual Time": 5.200
          }
        }
      }
    },
    "improvement": {
      "speedupRatio": 29.0,
      "executionTimeReduction": "145.3ms (96.5% faster)"
    },
    "issues": ["PREFIX_WILDCARD"],
    "verdict": "ACTIONABLE",
    "validated": true,
    "confidence": "HIGH",
    "canPatch": true
  }
]
```

**内容**：`recommendations.json`（结构级优化 → Report）

```json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "optimizationType": "STRUCTURAL",
    "baseline": {
      "sql": "SELECT * FROM orders WHERE status = 1",
      "executionTimeMs": 5200.0,
      "rowsScanned": 8934567,
      "rowsReturned": 1500,
      "explainPlan": {
        "format": "json",
        "version": "PostgreSQL 15",
        "raw": {
          "Plan": {
            "Node Type": "Seq Scan",
            "Relation Name": "orders",
            "Actual Rows": 1500,
            "Actual Time": 5200.000
          }
        }
      }
    },
    "tablesInvolved": ["orders"],
    "tableRowCounts": {"orders": 8934567},
    "issues": ["FULL_TABLE_SCAN"],
    "verdict": "RECOMMENDATION",
    "confidence": "MEDIUM",
    "recommendation": {
      "type": "CREATE_INDEX",
      "targetTable": "orders",
      "targetColumns": ["status", "created_at"],
      "reason": "Table has 8.9M rows, current query performs full table scan (Seq Scan)",
      "estimatedImprovement": "90% reduction in execution time (5.2s → 0.5s)"
    },
    "canPatch": false,
    "requiresUserDecision": true
  }
]
```

**Result 对 Optimize 的期望**：
| 字段 | 必须 | 说明 |
|------|------|------|
| `proposals[].canPatch = true` | ✅ | 才能进入 Patch 流程 |
| `recommendations[].canPatch = false` | ✅ | 进入 Report 流程 |

---

## 3. 特殊数据流

### 3.1 Optimize 需要 Parse 的输出

**原因**：Optimize 需要原始 SQL 生成优化建议

**方式**：Optimize 读取两个文件：
1. `recognition/baselines.json` — 性能数据
2. `parse/sql_units.json` — 原始 SQL

**数据映射**：
```python
# 在 Optimize 阶段
baselines = load_json("recognition/baselines.json")
sql_units = load_json("parse/sql_units.json")
table_schemas = load_json("init/table_schemas.json")

# 通过 sqlKey 关联
# baselines 中的 "com.example.UserMapper:branch:0"
# 对应 sql_units 中的 sqlKey + branch id

# 获取表行数判断优化价值
table_row_count = table_schemas["users"]["statistics"]["rowCount"]
```

---

## 4. 文件传递检查清单

| 阶段 | 生产文件 | 消费阶段 | 必须字段 |
|------|---------|---------|---------|
| Init | `init/sql_units.json` | Parse | sqlKey, xmlContent, dynamicFeatures |
| Init | `init/sql_fragments.json` | Parse | fragmentId, xmlContent |
| Init | `init/table_schemas.json` | **Optimize** | **statistics.rowCount** (表行数，判断优化价值) |
| Init | `init/xml_mappings.json` | Parse → Patch | **xpath**, tagName, idAttr, originalContent |
| Parse | `parse/sql_units.json` | Recognition, Optimize | sqlKey, xmlContent, branches |
| Parse | `parse/xml_mappings.json` | Patch | **xpath**, tagName, idAttr, originalContent |
| Parse | `parse/risks.json` | (内部使用) | - |
| Recognition | `recognition/baselines.json` | Optimize | sqlKey, executionTimeMs, rowsScanned, **explainPlan.raw** (完整) |
| Optimize | `optimize/proposals.json` | Patch | sqlKey, **baseline.explainPlan.raw**, **rewritten.explainPlan.raw**, improvement, canPatch=true |
| Optimize | `optimize/recommendations.json` | Report | sqlKey, **baseline.explainPlan.raw**, recommendation, canPatch=false |
| Parse | `parse/sql_units.json` | Optimize | sqlKey, branches[].sql |

**关键点**：
- `table_schemas.json` 中的 `statistics.rowCount` 是 Optimize 判断**优化价值**的关键
- 100 行的表优化意义小，1000 万行的表优化意义大
- Optimize 阶段综合考虑：表行数 × 当前扫描行数 × 执行时间
- **`explainPlan.raw` 必须包含完整执行计划**：这是作为"证据"的关键，用户可以追溯每一步推理
- **`improvement` 字段提供可读汇总**：speedupRatio、executionTimeReduction 等让人快速理解改善幅度

---

## 5. 契约完整性验证

每次阶段输出前，必须验证契约：

```python
from common.contracts import ContractValidator

validator = ContractValidator()

# Init 输出前验证
init_data = load_json("init/sql_units.json")
errors = validator.validate(init_data, "sqlunit.schema.json")
assert errors == [], f"Init output validation failed: {errors}"

# Parse 输出前验证
parse_data = load_json("parse/sql_units.json")
errors = validator.validate(parse_data, "sqlunit.schema.json")
assert errors == [], f"Parse output validation failed: {errors}"

# Recognition 输出前验证
baselines_data = load_json("recognition/baselines.json")
errors = validator.validate(baselines_data, "baseline_result.schema.json")
assert errors == [], f"Recognition output validation failed: {errors}"

# Optimize 输出前验证
proposals_data = load_json("optimize/proposals.json")
errors = validator.validate(proposals_data, "optimization_proposal.schema.json")
assert errors == [], f"Optimize output validation failed: {errors}"

# Result 输出前验证
patches_data = load_json("result/patches.json")
errors = validator.validate(patches_data, "patch_result.schema.json")
assert errors == [], f"Result output validation failed: {errors}"
```
