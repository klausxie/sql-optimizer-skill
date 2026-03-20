# V9 阶段 API 契约

> 版本：V9 | 更新日期：2026-03-20

---

## 一、契约概述

本文档定义 V9 五个阶段的 API 契约，包括输入、输出、Schema 引用和完整 JSON 示例。

### 设计原则

1. **单一阶段边界**：每个阶段必须明确回答依赖、输入、产出
2. **契约优先**：阶段间传递的数据必须是结构化对象，可 JSON Schema 校验
3. **实现双形态**：`execute()` 批量处理 + `execute_one()` 单对象处理，语义一致

---

## 二、阶段总表

| 阶段 | 依赖阶段 | 主输入 Schema | 主输出 Schema |
|------|----------|--------------|---------------|
| **Init** | 无 | - | `sqlunit.schema.json` |
| **Parse** | Init | `sqlunit.schema.json` | `sqlunit.schema.json` (扩展) + `risks.schema.json` |
| **Recognition** | Parse | `sqlunit.schema.json` | `baseline_result.schema.json` |
| **Optimize** | Recognition | `baseline_result.schema.json` | `optimization_proposal.schema.json` |
| **Patch** | Optimize | `optimization_proposal.schema.json` | `patch_result.schema.json` |

---

## 三、阶段详细契约

## 3.1 Init 阶段

### 3.1.1 阶段职责

解析 MyBatis XML 映射文件，提取 SQL 语句单元。

### 3.1.2 依赖阶段

- 无

### 3.1.3 输入

| 类型 | 说明 |
|------|------|
| MyBatis XML 文件 | 通过 `mapper_globs` 配置扫描 |

### 3.1.4 输出文件

- `init/sql_units.json`

### 3.1.5 Schema 引用

```json
// contracts/schemas/sqlunit.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SqlUnit",
  "type": "object",
  "required": [
    "sqlKey", "xmlPath", "namespace", "statementId",
    "statementType", "variantId", "sql",
    "parameterMappings", "paramExample", "locators",
    "riskFlags"
  ],
  "properties": {
    "sqlKey": {"type": "string"},
    "xmlPath": {"type": "string"},
    "namespace": {"type": "string"},
    "statementId": {"type": "string"},
    "statementType": {"type": "string"},
    "variantId": {"type": "string"},
    "sql": {"type": "string"},
    "parameterMappings": {"type": "array"},
    "paramExample": {"type": "object"},
    "locators": {"type": "object"},
    "riskFlags": {"type": "array", "items": {"type": "string"}},
    "templateSql": {"type": "string"},
    "dynamicFeatures": {"type": "array", "items": {"type": "string"}},
    "branches": {"type": "array"},
    "branchCount": {"type": "integer"}
  }
}
```

### 3.1.6 完整 JSON 示例

```json
{
  "sqlKey": "com.example.UserMapper.selectByExample",
  "xmlPath": "/project/src/main/resources/mapper/UserMapper.xml",
  "namespace": "com.example.UserMapper",
  "statementId": "selectByExample",
  "statementType": "SELECT",
  "variantId": "v1",
  "sql": "SELECT * FROM users WHERE status = #{status}",
  "parameterMappings": [
    {"name": "status", "jdbcType": "INTEGER"}
  ],
  "paramExample": {"status": 1},
  "locators": {
    "statementXPath": "/mapper/select[@id='selectByExample']",
    "namespace": "com.example.UserMapper"
  },
  "riskFlags": [],
  "templateSql": "SELECT * FROM users WHERE status = #{status}",
  "dynamicFeatures": ["IF", "WHERE"],
  "branches": [],
  "branchCount": 0
}
```

### 3.1.7 Python 接口

```python
from pathlib import Path
from typing import Any

def execute_one(
    run_id: str,
    ctx: StageContext,
    mapper_path: str | Path,
) -> dict[str, Any]:
    """
    处理单个 Mapper XML 文件
    
    Args:
        run_id: 运行 ID
        ctx: 阶段上下文
        mapper_path: Mapper XML 文件路径
    
    Returns:
        SQL 单元字典列表
    """
    ...

def execute_batch(
    run_id: str,
    ctx: StageContext,
    mapper_paths: list[Path],
) -> StageResult:
    """
    批量处理多个 Mapper 文件
    
    Args:
        run_id: 运行 ID
        ctx: 阶段上下文
        mapper_paths: Mapper 文件路径列表
    
    Returns:
        StageResult
    """
    ...
```

---

## 3.2 Parse 阶段

### 3.2.1 阶段职责

展开动态 SQL 生成分支路径，同时进行风险检测。

### 3.2.2 依赖阶段

- Init

### 3.2.3 输入文件

- `init/sql_units.json`

### 3.2.4 Schema 引用

- 输入: `sqlunit.schema.json`
- 输出: `sqlunit.schema.json` (扩展 branches) + `risks.schema.json`

```json
// contracts/schemas/risks.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RiskIssue",
  "type": "object",
  "required": ["sqlKey", "risk_type", "severity"],
  "properties": {
    "sqlKey": {
      "type": "string",
      "description": "Unique identifier for the SQL statement"
    },
    "risk_type": {
      "type": "string",
      "description": "Type of risk (PREFIX_WILDCARD, FUNCTION_WRAP, etc.)"
    },
    "severity": {
      "type": "string",
      "enum": ["HIGH", "MEDIUM", "LOW"],
      "description": "Risk severity level"
    },
    "location": {
      "type": "object",
      "properties": {
        "line": {"type": "integer"},
        "column": {"type": "integer"}
      }
    },
    "suggestion": {
      "type": "string",
      "description": "Suggested fix or optimization"
    }
  }
}
```

### 3.2.5 输出文件

- `parse/sql_units_with_branches.json`
- `parse/risks.json`

### 3.2.6 完整 JSON 示例

**sql_units_with_branches.json 示例：**

```json
{
  "sqlKey": "com.example.UserMapper.search",
  "xmlPath": "/project/src/main/resources/mapper/UserMapper.xml",
  "namespace": "com.example.UserMapper",
  "statementId": "search",
  "statementType": "SELECT",
  "variantId": "v1",
  "sql": "SELECT * FROM users WHERE 1=1",
  "parameterMappings": [],
  "paramExample": {},
  "locators": {},
  "riskFlags": [],
  "templateSql": "SELECT * FROM users WHERE 1=1",
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
    },
    {
      "id": 2,
      "conditions": ["name IS NOT NULL", "status IS NOT NULL"],
      "sql": "SELECT * FROM users WHERE 1=1 AND name = #{name} AND status = #{status}",
      "type": "conditional"
    }
  ],
  "branchCount": 3,
  "problemBranchCount": 0
}
```

**risks.json 示例：**

```json
[
  {
    "sqlKey": "com.example.UserMapper.searchLike",
    "risk_type": "PREFIX_WILDCARD",
    "severity": "HIGH",
    "location": {"line": 3, "column": 15},
    "suggestion": "Remove leading wildcard or use full-text search"
  },
  {
    "sqlKey": "com.example.UserMapper.searchFunc",
    "risk_type": "FUNCTION_WRAP",
    "severity": "MEDIUM",
    "location": {"line": 2, "column": 22},
    "suggestion": "Apply index on UPPER(column) or restructure query"
  }
]
```

### 3.2.7 Python 接口

```python
from pathlib import Path
from typing import Any

def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    处理单个 SQL 单元，生成分支和风险
    
    Args:
        sql_unit: SQL 单元字典
        run_dir: 运行目录
        validator: 契约验证器
        config: 配置字典
    
    Returns:
        带分支的 SQL 单元
    """
    ...

def parse_risks_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    """
    检测单个 SQL 单元的风险
    
    Args:
        sql_unit: SQL 单元字典
        run_dir: 运行目录
    
    Returns:
        风险记录字典
    """
    ...
```

---

## 3.3 Recognition 阶段

### 3.3.1 阶段职责

采集当前 SQL 的执行计划作为性能基准。

### 3.3.2 依赖阶段

- Parse

### 3.3.3 输入文件

- `parse/sql_units_with_branches.json`

### 3.3.4 输出文件

- `recognition/baselines.json`

### 3.3.5 Schema 引用

```json
// contracts/schemas/baseline_result.schema.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "baseline_result",
  "type": "object",
  "required": [
    "sql_key", "execution_time_ms", "rows_scanned",
    "execution_plan", "result_hash"
  ],
  "properties": {
    "sql_key": {"type": "string"},
    "execution_time_ms": {"type": "number"},
    "rows_scanned": {"type": "integer"},
    "execution_plan": {
      "type": "object",
      "properties": {
        "node_type": {"type": "string"},
        "index_used": {"type": ["string", "null"]},
        "cost": {"type": ["number", "null"]}
      },
      "required": ["node_type"]
    },
    "result_hash": {"type": "string"},
    "rows_returned": {"type": "integer"},
    "database_platform": {"type": "string", "enum": ["postgresql", "mysql"]},
    "sample_params": {"type": "object"},
    "actual_execution_time_ms": {"type": ["number", "null"]},
    "buffer_hit_count": {"type": ["integer", "null"]},
    "buffer_read_count": {"type": ["integer", "null"]},
    "explain_plan": {"type": "object"},
    "trace": {
      "type": "object",
      "properties": {
        "stage": {"type": "string"},
        "sql_key": {"type": "string"},
        "executor": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"}
      }
    }
  }
}
```

### 3.3.6 完整 JSON 示例

```json
[
  {
    "sql_key": "com.example.UserMapper.selectByExample:branch:0",
    "execution_time_ms": 12.5,
    "rows_scanned": 1520,
    "execution_plan": {
      "node_type": "Seq Scan",
      "index_used": null,
      "cost": 43.21
    },
    "result_hash": "a1b2c3d4e5f6",
    "rows_returned": 20,
    "database_platform": "postgresql",
    "sample_params": {},
    "actual_execution_time_ms": 12.9,
    "buffer_hit_count": 110,
    "buffer_read_count": 7,
    "explain_plan": {
      "Plan": {
        "Node Type": "Seq Scan",
        "Relation Name": "users",
        "Filter": "(status = 1)",
        "Rows Removed by Filter": 1500
      }
    },
    "trace": {
      "stage": "recognition",
      "sql_key": "com.example.UserMapper.selectByExample:branch:0",
      "executor": "baseline_collector",
      "timestamp": "2026-03-20T10:30:00Z"
    }
  },
  {
    "sql_key": "com.example.UserMapper.selectByExample:branch:1",
    "execution_time_ms": 2.3,
    "rows_scanned": 150,
    "execution_plan": {
      "node_type": "Index Scan",
      "index_used": "idx_users_status",
      "cost": 25.5
    },
    "result_hash": "b2c3d4e5f6g7",
    "rows_returned": 20,
    "database_platform": "postgresql",
    "sample_params": {"status": 1},
    "actual_execution_time_ms": 2.1,
    "buffer_hit_count": 148,
    "buffer_read_count": 2,
    "explain_plan": {
      "Plan": {
        "Node Type": "Index Scan",
        "Index Name": "idx_users_status",
        "Rows Removed by Filter": 0
      }
    },
    "trace": {
      "stage": "recognition",
      "sql_key": "com.example.UserMapper.selectByExample:branch:1",
      "executor": "baseline_collector",
      "timestamp": "2026-03-20T10:30:01Z"
    }
  }
]
```

### 3.3.7 Python 接口

```python
from pathlib import Path
from typing import Any

def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    对单个 SQL 单元执行 EXPLAIN 采集基线
    
    Args:
        sql_unit: SQL 单元字典
        run_dir: 运行目录
        validator: 契约验证器
        config: 配置字典
    
    Returns:
        基线结果字典
    """
    ...

def execute_batch(
    run_id: str,
    ctx: StageContext,
    baseline_data: list[dict[str, Any]],
) -> StageResult:
    """
    批量执行基线采集
    
    Args:
        run_id: 运行 ID
        ctx: 阶段上下文
        baseline_data: 基线数据列表
    
    Returns:
        StageResult
    """
    ...
```

---

## 3.4 Optimize 阶段

### 3.4.1 阶段职责

生成优化建议并进行语义验证，支持迭代重试。

### 3.4.2 依赖阶段

- Recognition

### 3.4.3 输入文件

- `recognition/baselines.json`

### 3.4.4 输出文件

- `optimize/proposals.json`

### 3.4.5 Schema 引用

```json
// contracts/schemas/optimization_proposal.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "OptimizationProposal",
  "type": "object",
  "required": [
    "sqlKey", "issues", "dbEvidenceSummary",
    "planSummary", "suggestions", "verdict"
  ],
  "properties": {
    "sqlKey": {"type": "string"},
    "issues": {"type": "array"},
    "dbEvidenceSummary": {"type": "object"},
    "planSummary": {"type": "object"},
    "suggestions": {"type": "array"},
    "verdict": {"type": "string"},
    "estimatedBenefit": {"type": "string"},
    "confidence": {"type": "string"},
    "blockedBy": {"type": "array", "items": {"type": "string"}},
    "actionability": {
      "type": ["object", "null"],
      "properties": {
        "score": {"type": ["integer", "null"]},
        "tier": {"type": ["string", "null"]},
        "autoPatchLikelihood": {"type": ["string", "null"]},
        "reasons": {"type": ["array", "null"]},
        "blockedBy": {"type": ["array", "null"]}
      }
    },
    "recommendedSuggestionIndex": {"type": ["integer", "null"]},
    "triggeredRules": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "ruleId": {"type": "string"},
          "builtin": {"type": "string"},
          "severity": {"type": "string"},
          "sourceRef": {"type": ["string", "null"]},
          "blocksActionability": {"type": ["boolean", "null"]}
        }
      }
    },
    "llmCandidates": {"type": "array"},
    "llmTraceRefs": {"type": "array", "items": {"type": "string"}},
    "llmPromptStatus": {"type": "string"},
    "llmPromptFile": {"type": "string"},
    "candidateGenerationDiagnostics": {
      "type": ["object", "null"],
      "properties": {
        "degradationKind": {"type": ["string", "null"]},
        "recoveryAttempted": {"type": ["boolean", "null"]},
        "recoveryStrategy": {"type": ["string", "null"]},
        "recoverySucceeded": {"type": ["boolean", "null"]},
        "recoveryReason": {"type": ["string", "null"]},
        "rawCandidateCount": {"type": ["integer", "null"]},
        "validatedCandidateCount": {"type": ["integer", "null"]},
        "acceptedCandidateCount": {"type": ["integer", "null"]},
        "prunedLowValueCount": {"type": ["integer", "null"]},
        "lowValueCandidateCount": {"type": ["integer", "null"]},
        "recoveredCandidateCount": {"type": ["integer", "null"]},
        "rawRewriteStrategies": {"type": ["array", "null"]},
        "finalCandidateCount": {"type": ["integer", "null"]}
      }
    }
  }
}
```

### 3.4.6 完整 JSON 示例

```json
[
  {
    "sqlKey": "com.example.UserMapper.search:branch:0",
    "issues": ["FULL_SCAN", "PREFIX_WILDCARD"],
    "dbEvidenceSummary": {
      "rowsScanned": 1520,
      "nodeType": "Seq Scan",
      "indexUsed": null
    },
    "planSummary": {
      "before": "Seq Scan on users",
      "cost": 43.21
    },
    "suggestions": [
      {
        "id": "rule-prefix-like",
        "source": "rule",
        "title": "Remove leading wildcard",
        "originalSql": "SELECT * FROM users WHERE name LIKE '%' || #{name} || '%'",
        "rewrittenSql": "SELECT * FROM users WHERE name LIKE #{name} || '%'",
        "benefit": "Enable index usage",
        "risk": "LOW"
      },
      {
        "id": "llm-candidate-1",
        "source": "llm",
        "title": "Use covering index",
        "originalSql": "SELECT * FROM users WHERE name LIKE #{name} || '%'",
        "rewrittenSql": "SELECT id, name, status FROM users WHERE name LIKE #{name} || '%'",
        "benefit": "Reduce columns scanned",
        "risk": "MEDIUM"
      }
    ],
    "verdict": "ACTIONABLE",
    "estimatedBenefit": "HIGH",
    "confidence": "HIGH",
    "blockedBy": [],
    "actionability": {
      "score": 85,
      "tier": "HIGH",
      "autoPatchLikelihood": "HIGH",
      "reasons": ["Simple rewrite", "Low risk"],
      "blockedBy": null
    },
    "recommendedSuggestionIndex": 0,
    "triggeredRules": [
      {
        "ruleId": "prefix-wildcard",
        "builtin": "PREFIX_WILDCARD_RULE",
        "severity": "HIGH",
        "sourceRef": "builtin:rule:prefix_wildcard",
        "blocksActionability": false
      }
    ],
    "llmCandidates": [],
    "llmTraceRefs": [],
    "llmPromptStatus": "SKIPPED",
    "llmPromptFile": "",
    "candidateGenerationDiagnostics": {
      "degradationKind": null,
      "recoveryAttempted": false,
      "recoveryStrategy": null,
      "recoverySucceeded": null,
      "recoveryReason": null,
      "rawCandidateCount": 1,
      "validatedCandidateCount": 1,
      "acceptedCandidateCount": 1,
      "prunedLowValueCount": 0,
      "lowValueCandidateCount": 0,
      "recoveredCandidateCount": 0,
      "rawRewriteStrategies": ["prefix_wildcard_rewrite"],
      "finalCandidateCount": 1
    }
  }
]
```

### 3.4.7 Python 接口

```python
from pathlib import Path
from typing import Any

def execute_one(
    baseline_result: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator | None = None,
    db_reachable: bool = True,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    对单个基线结果生成优化提案
    
    包含内部迭代验证循环:
    1. 应用优化规则
    2. 语义验证
    3. 通过则接受，否则重试
    
    Args:
        baseline_result: 基线结果字典
        run_dir: 运行目录
        validator: 契约验证器
        db_reachable: 数据库是否可达
        config: 配置字典
    
    Returns:
        优化提案字典
    """
    ...

def apply_rules(
    baseline_result: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    应用优化规则生成候选
    
    Args:
        baseline_result: 基线结果
        config: 配置字典
    
    Returns:
        候选列表
    """
    ...

def semantic_check(
    candidate: dict[str, Any],
    db_validator: DbValidator | None = None,
) -> bool:
    """
    语义验证候选
    
    Args:
        candidate: 候选提案
        db_validator: 数据库验证器
    
    Returns:
        是否通过验证
    """
    ...
```

---

## 3.5 Patch 阶段

### 3.5.1 阶段职责

生成可应用的 XML 补丁。

### 3.5.2 依赖阶段

- Optimize

### 3.5.3 输入文件

- `optimize/proposals.json` (仅 validated=true 的提案)

### 3.5.4 输出文件

- `patch/patches.json`

### 3.5.5 Schema 引用

```json
// contracts/schemas/patch_result.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PatchResult",
  "type": "object",
  "required": [
    "sqlKey", "patchFiles", "diffSummary",
    "applyMode", "rollback"
  ],
  "properties": {
    "sqlKey": {"type": "string"},
    "statementKey": {"type": ["string", "null"]},
    "patchFiles": {"type": "array", "items": {"type": "string"}},
    "diffSummary": {
      "type": "object",
      "properties": {
        "filesChanged": {"type": "integer"},
        "hunks": {"type": "integer"},
        "summary": {"type": "string"}
      }
    },
    "applyMode": {"type": "string"},
    "rollback": {"type": "string"},
    "selectedCandidateId": {"type": ["string", "null"]},
    "candidatesEvaluated": {"type": ["integer", "null"]},
    "applicable": {"type": ["boolean", "null"]},
    "applyCheckError": {"type": ["string", "null"]},
    "selectionReason": {"type": ["object", "null"]},
    "rejectedCandidates": {"type": ["array", "null"]},
    "deliveryOutcome": {"type": ["object", "null"]},
    "repairHints": {"type": ["array", "null"]},
    "patchability": {"type": ["object", "null"]},
    "selectionEvidence": {"type": ["object", "null"]},
    "fallbackReasonCodes": {"type": ["array", "null"]},
    "strategyType": {"type": ["string", "null"]},
    "fallbackApplied": {"type": ["boolean", "null"]},
    "dynamicTemplateStrategy": {"type": ["string", "null"]},
    "dynamicTemplateBlockingReason": {"type": ["string", "null"]},
    "gates": {
      "type": ["object", "null"],
      "properties": {
        "semanticEquivalenceStatus": {"type": ["string", "null"]},
        "semanticEquivalenceBlocking": {"type": ["boolean", "null"]},
        "semanticConfidence": {"type": ["string", "null"]},
        "semanticEvidenceLevel": {"type": ["string", "null"]}
      }
    }
  }
}
```

### 3.5.6 完整 JSON 示例

```json
[
  {
    "sqlKey": "com.example.UserMapper.search:branch:0",
    "statementKey": "com.example.UserMapper.search",
    "patchFiles": [
      "runs/run_20260320_001/patch/com.example.UserMapper.search.patch"
    ],
    "diffSummary": {
      "filesChanged": 1,
      "hunks": 2,
      "summary": "Replace LIKE '%x%' with range predicate"
    },
    "applyMode": "manual",
    "rollback": "restore original mapper backup",
    "selectedCandidateId": "rule-prefix-like",
    "candidatesEvaluated": 2,
    "applicable": true,
    "applyCheckError": null,
    "selectionReason": {
      "rule": "prefix_wildcard",
      "confidence": "HIGH"
    },
    "rejectedCandidates": [
      {
        "id": "llm-candidate-1",
        "reason": "Higher risk"
      }
    ],
    "deliveryOutcome": {
      "status": "ready"
    },
    "repairHints": [],
    "patchability": {
      "canApply": true,
      "requiresApproval": true
    },
    "selectionEvidence": {
      "method": "rule_based",
      "triggeredRule": "prefix_wildcard"
    },
    "fallbackReasonCodes": [],
    "strategyType": "direct_rewrite",
    "fallbackApplied": false,
    "dynamicTemplateStrategy": null,
    "dynamicTemplateBlockingReason": null,
    "gates": {
      "semanticEquivalenceStatus": "PASS",
      "semanticEquivalenceBlocking": false,
      "semanticConfidence": "HIGH",
      "semanticEvidenceLevel": "STRUCTURED"
    }
  }
]
```

### 3.5.7 Python 接口

```python
from pathlib import Path
from typing import Any

def execute_one(
    proposal: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    对单个优化提案生成补丁
    
    Args:
        proposal: 优化提案字典
        run_dir: 运行目录
        validator: 契约验证器
        config: 配置字典
    
    Returns:
        补丁结果字典
    """
    ...

def generate_patch(
    proposal: dict[str, Any],
    original_xml_path: str,
) -> dict[str, Any]:
    """
    生成 XML 补丁
    
    Args:
        proposal: 优化提案
        original_xml_path: 原始 XML 文件路径
    
    Returns:
        补丁详情字典
    """
    ...

def apply_patch(
    patch: dict[str, Any],
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    应用补丁
    
    Args:
        patch: 补丁字典
        dry_run: 是否仅预览
    
    Returns:
        应用结果字典
    """
    ...
```

---

## 四、Stage 基类接口（参考）

V9 采用直接方法调用，但保留 Stage 接口供参考：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

class Stage(ABC):
    """阶段抽象基类（V9 不强制使用）"""
    
    name: str = "base"
    version: str = "1.0.0"
    dependencies: list[str] = []
    
    @abstractmethod
    def execute(self, context: StageContext) -> StageResult:
        """执行阶段逻辑"""
        pass
    
    @abstractmethod
    def get_input_contracts(self) -> list[str]:
        """返回输入契约列表"""
        pass
    
    @abstractmethod
    def get_output_contracts(self) -> list[str]:
        """返回输出契约列表"""
        pass

@dataclass
class StageContext:
    """阶段执行上下文"""
    run_id: str
    config: dict[str, Any]
    data_dir: Path
    cache_dir: Path | None = None
    metadata: dict[str, Any] = None

@dataclass
class StageResult:
    """阶段执行结果"""
    success: bool
    output_files: list[Path]
    artifacts: dict[str, Any]
    errors: list[str]
    warnings: list[str]
```

---

## 五、契约验证

### 5.1 验证器使用

```python
from sqlopt.contracts import ContractValidator

validator = ContractValidator(repo_root=Path("."))

# 验证阶段输入
validator.validate_stage_input("optimize", baseline_data)

# 验证阶段输出
validator.validate_stage_output("optimize", proposal_data)

# 直接验证 schema
validator.validate("sqlunit", sqlunit_data)
```

### 5.2 验证规则

1. **输入校验**：对每个输入对象逐条校验
2. **输出校验**：对每个输出对象逐条校验
3. **文件校验**：落盘文件必须可再次读取并通过 schema 校验

---

## 六、变更记录

### V9 契约变更 (2026-03-20)

1. **阶段合并**：
   - Discovery → Init
   - Branching + Pruning → Parse
   - Baseline → Recognition
   - Optimize + Validate → Optimize

2. **目录变更**：
   - 新增 `init/`、`parse/`、`recognition/` 目录
   - 移除 `validate/` 目录

3. **契约字段变更**：
   - `sqlunit` 新增 `branches`、`branchCount`、`problemBranchCount`
   - `optimization_proposal` 新增 `actionability`、`triggeredRules`、`candidateGenerationDiagnostics`

---

*本文档最后更新：2026-03-20*
