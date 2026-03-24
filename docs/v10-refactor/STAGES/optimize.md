# Optimize 阶段

> 生成优化建议，验证语义等价性

---

## 1. 阶段职责

**核心职责**：
1. 基于**整个 Mapper** 的上下文生成优化建议
2. 结合**表统计信息**（数据量、索引）判断优化价值
3. **验证优化建议**：
   - **语法级优化**：生成新 SQL，对比执行计划验证效果
   - **结构级优化**：无法验证，输出为用户建议

**两种优化类型**：

| 类型 | 示例 | 验证方式 | 输出 |
|------|------|----------|------|
| **语法级** | LIKE '%xxx' → LIKE 'xxx%' | 对比执行计划 | → Patch 阶段 |
| **结构级** | 建议建索引、建议分区 | 无法验证 | → Report 阶段 |

**关键洞察**：
- 优化不是针对单个 SQL，而是针对**整个 Mapper**
- 语法级优化可以被验证（对比执行计划），可以直接 Patch
- 结构级优化无法被验证，只能输出报告给用户决策

**输入**：
- `recognition/baselines.json` — Recognition 阶段的输出
- `parse/sql_units.json` — Parse 阶段的输出（用于获取原始 SQL 和 Mapper 上下文）
- `init/table_schemas.json` — 表统计信息（行数、索引等）

**输出**：
- `optimize/proposals.json` — 优化提案列表（带验证状态）
- `optimize/recommendations.json` — 无法验证的结构级建议（给用户看）

**不做什么**：
- ❌ 不展开动态 SQL（那是 Parse 的职责）
- ❌ 不执行 EXPLAIN（那是 Recognition 的职责）
- ❌ 不直接修改 XML（那是 Patch 的职责）

---

## 2. 数据契约

### 2.1 输入

#### 2.1.1 baselines.json（摘录）

```json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "executionTimeMs": 150.5,
    "rowsScanned": 10000,
    "executionPlan": {"nodeType": "Seq Scan", "cost": 500}
  }
]
```

#### 2.1.2 sql_units.json（摘录）

```json
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "branches": [
      {
        "id": 0,
        "sql": "SELECT * FROM users WHERE name LIKE '%' || #{name}",
        "type": "conditional"
      }
    ],
    "branchCount": 1
  }
]
```

#### 2.1.3 table_schemas.json（摘录）

```json
{
  "users": {
    "columns": [...],
    "indexes": [...],
    "database": "postgresql",
    "statistics": {
      "rowCount": 1520347,
      "totalSizeBytes": 104857600
    }
  }
}
```

**关键**：Optimize 需要知道表有多少行（`rowCount`）才能判断优化价值。

### 2.2 Mapper 级别上下文

**关键洞察**：Optimize 应该基于**整个 Mapper** 生成建议，而不是单个 SQL。

```json
// Optimize 输入的完整上下文
{
  "mapper": {
    "namespace": "com.example.UserMapper",
    "xmlPath": "/path/to/UserMapper.xml",
    "sqlCount": 5,
    "totalBranches": 12,
    "sqls": [
      {
        "sqlKey": "com.example.UserMapper.search",
        "branches": [...]
      },
      {
        "sqlKey": "com.example.UserMapper.findByEmail",
        "branches": [...]
      }
    ]
  },
  "tables": {
    "users": {
      "statistics": {"rowCount": 1520347}
    },
    "orders": {
      "statistics": {"rowCount": 8923456}
    }
  },
  "baselines": [...]
}
```

### 2.2 输出 Schema

#### 2.2.1 proposals.json（可验证的语法级优化 → Patch 阶段）

```json
// optimize/proposals.json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "mapperNamespace": "com.example.UserMapper",
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
            "Alias": "users",
            "Startup Cost": 0.00,
            "Total Cost": 568.32,
            "Plan Rows": 100,
            "Plan Width": 52,
            "Actual Startup Time": 120.500,
            "Actual Total Time": 150.500,
            "Actual Rows": 100,
            "Actual Loops": 1,
            "Filter": "(name ~~ '%'::text)",
            "Rows Removed by Filter": 1520347
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
            "Relation Name": "users",
            "Alias": "users",
            "Index Name": "idx_user_name",
            "Startup Cost": 0.43,
            "Total Cost": 8.45,
            "Plan Rows": 100,
            "Plan Width": 16,
            "Actual Startup Time": 0.021,
            "Actual Total Time": 5.200,
            "Actual Rows": 100,
            "Actual Loops": 1,
            "Index Cond": "(name ~~* (current_setting('param.name'::text)) || '%'::text)"
          }
        }
      }
    },
    "improvement": {
      "speedupRatio": 29.0,
      "executionTimeReduction": "145.3ms (96.5% faster)",
      "rowsScannedReduction": "1,520,247 → 100 (99.99% reduction)",
      "costReduction": "568.32 → 8.45 (98.5% reduction)"
    },
    "issues": ["PREFIX_WILDCARD"],
    "verdict": "ACTIONABLE",
    "validated": true,
    "confidence": "HIGH",
    "canPatch": true,
    "patchStrategy": "REPLACE_SQL_FRAGMENT"
  }
]
```

#### 2.2.2 recommendations.json（不可验证的结构级建议 → Report 阶段）

```json
// optimize/recommendations.json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "mapperNamespace": "com.example.UserMapper",
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
            "Filter": "(status = 1)",
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
    "requiresUserDecision": true,
    "alternativeActions": [
      "Create partial index on orders(status) WHERE status = 1",
      "Consider table partitioning by status",
      "Archive old data to reduce table size"
    ]
  }
]
```

### 2.3 关键字段说明

#### 2.3.1 主字段

| 字段 | 说明 |
|------|------|
| `sqlKey` | 分支唯一标识 |
| `mapperNamespace` | 所属 Mapper namespace |
| `optimizationType` | 优化类型：`SYNTAX`（语法级） 或 `STRUCTURAL`（结构级） |
| `baseline` | **原始 SQL 的完整基线**（包含执行计划） |
| `rewritten` | **优化后 SQL 的完整结果**（包含执行计划） |
| `improvement` | **改善数据汇总**（用于快速查看） |
| `tablesInvolved` | 涉及的表列表 |
| `tableRowCounts` | 这些表的行数（用于判断优化价值） |
| `issues` | 检测到的问题类型列表 |
| `verdict` | 评估结果：`ACTIONABLE`, `RECOMMENDATION`, `NOT_ACTIONABLE` |
| `validated` | 是否通过验证（语法级）或需要用户决策（结构级） |
| `confidence` | 置信度：`HIGH`, `MEDIUM`, `LOW` |
| `canPatch` | 是否可以直接 Patch |

#### 2.3.2 baseline/rewritten 字段（核心证据）

| 字段 | 说明 |
|------|------|
| `sql` | 实际执行的 SQL |
| `executionTimeMs` | 实际执行时间（毫秒） |
| `rowsScanned` | 扫描的行数 |
| `rowsReturned` | 返回的行数 |
| `explainPlan` | **完整的 EXPLAIN 输出**（JSON 格式） |
| `explainPlan.format` | 格式：`json` |
| `explainPlan.version` | 数据库版本 |
| `explainPlan.raw` | **原始 EXPLAIN 输出（完整版）** |

**关键**：`explainPlan.raw` 必须包含完整的执行计划，而不仅仅是摘要。

#### 2.3.3 improvement 字段（改善汇总）

| 字段 | 说明 |
|------|------|
| `speedupRatio` | 加速比（如 29.0 表示快 29 倍） |
| `executionTimeReduction` | 执行时间减少量（如 "145.3ms (96.5% faster)"） |
| `rowsScannedReduction` | 扫描行数减少（如 "1,520,247 → 100 (99.99% reduction)"） |
| `costReduction` | 代价减少（如 "568.32 → 8.45 (98.5% reduction)"） |

#### 2.3.4 recommendation 字段（结构级优化）

| 字段 | 说明 |
|------|------|
| `recommendation.type` | 建议类型：`CREATE_INDEX`, `PARTITION`, `ARCHIVE` |
| `recommendation.targetTable` | 目标表 |
| `recommendation.targetColumns` | 目标列 |
| `recommendation.reason` | 原因（基于 baseline 的实际数据） |
| `recommendation.estimatedImprovement` | 预估改善（量化） |
| `requiresUserDecision` | 是否需要用户决策（结构级 = true） |
| `alternativeActions` | 替代方案列表 |

---

## 3. 目录结构

```
optimize/
├── __init__.py
├── api.py                 # 阶段 API（必须）
│                          # - validate_input()
│                          # - run(baselines_file, sql_units_file, config) -> OptimizeResult
├── run.py                # 入口实现
├── rules_engine.py        # 规则引擎（核心）
├── llm_provider.py        # LLM 调用
├── semantic_check.py      # 语义等价检查
├── candidate_selector.py   # 候选选择
├── README.md             # 本文档
└── STAGE.md              # 阶段设计文档（详细）
```

---

## 4. 快速调测

### 4.1 准备测试环境

```bash
# 1. 创建测试输入文件
mkdir -p /tmp/sqlopt-test/runs/test-run/optimize
cat > /tmp/sqlopt-test/runs/test-run/recognition/baselines.json << 'EOF'
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "executionTimeMs": 150.5,
    "rowsScanned": 10000,
    "rowsReturned": 100,
    "executionPlan": {"nodeType": "Seq Scan", "indexUsed": null, "cost": 500}
  }
]
EOF

cat > /tmp/sqlopt-test/runs/test-run/parse/sql_units.json << 'EOF'
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "sql": "SELECT * FROM users WHERE name LIKE '%' || #{name}",
    "branches": [{"id": 0, "conditions": [], "sql": "SELECT * FROM users WHERE name LIKE '%' || #{name}"}]
  }
]
EOF

# 2. 创建测试配置
cat > /tmp/sqlopt-test/sqlopt.yml << 'EOF'
config_version: v1
llm:
  enabled: false
EOF

export SQLOPT_RUN_DIR=/tmp/sqlopt-test/runs/test-run
```

### 4.2 编写测试代码

```python
# /tmp/sqlopt-test/test_optimize.py
import sys
sys.path.insert(0, '/path/to/python')

from sqlopt.optimize.api import run, validate_input
from sqlopt.common.config import load_config
import json

# 验证输入
baselines_file = Path('/tmp/sqlopt-test/runs/test-run/recognition/baselines.json')
sql_units_file = Path('/tmp/sqlopt-test/runs/test-run/parse/sql_units.json')
errors = validate_input(baselines_file, sql_units_file)
if errors:
    print(f"Input errors: {errors}")
    sys.exit(1)

# 运行 Optimize
config = load_config('/tmp/sqlopt-test/sqlopt.yml')
result = run(baselines_file, sql_units_file, config)

# 检查结果
print(f"Success: {result.success}")
print(f"Proposals: {result.proposals_count}")
print(f"Actionable: {result.actionable_count}")
print(f"Errors: {result.errors}")

# 验证输出
with open(result.output_file) as f:
    proposals = json.load(f)
    for p in proposals:
        print(f"  {p['sqlKey']}: {p['verdict']}, {len(p['suggestions'])} suggestions")
```

### 4.3 运行测试

```bash
cd /tmp/sqlopt-test
python test_optimize.py

# 检查输出
cat /tmp/sqlopt-test/runs/test-run/optimize/proposals.json | python -m json.tool
```

### 4.4 预期输出

```json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "originalSql": "SELECT * FROM users WHERE name LIKE '%' || #{name}",
    "issues": ["PREFIX_WILDCARD"],
    "verdict": "ACTIONABLE",
    "validated": true,
    "confidence": "HIGH",
    "suggestions": [
      {
        "id": "prefix-like-fix",
        "rewrittenSql": "SELECT id, name FROM users WHERE name LIKE #{name} || '%'",
        "benefit": "Enable index usage"
      }
    ]
  }
]
```

---

## 5. 修改指南

### 5.1 改优化规则

**文件**：`rules_engine.py`

**原因**：需要添加/修改优化规则

**修改**：编辑 `rules_engine.py` 中的规则定义

```python
# rules_engine.py
OPTIMIZATION_RULES = [
    {
        "id": "prefix-wildcard",
        "name": "Prefix Wildcard",
        "detect": r"LIKE\s+'%",
        "rewrite": "...",  # 改这里
    },
    # 添加新规则...
]

def apply_rules(sql: str, baseline: dict) -> list[Suggestion]:
    ...
```

### 5.2 改 LLM 调用

**文件**：`llm_provider.py`

**原因**：需要修改 LLM 调用逻辑

**修改**：编辑 `llm_provider.py`

```python
# llm_provider.py
def generate_candidates(sql: str, context: dict, config: dict) -> list[Candidate]:
    # 这里是 LLM 调用逻辑
    # 如果调用不对，改这里
    ...
```

### 5.3 改语义检查

**文件**：`semantic_check.py`

**原因**：语义等价验证逻辑不对

**修改**：编辑 `semantic_check.py`

```python
# semantic_check.py
def check_equivalence(original: str, rewritten: str, config: dict) -> bool:
    # 这里是语义等价检查逻辑
    # 如果检查不对，改这里
    ...
```

---

## 6. API 定义

### 6.1 validate_input()

```python
def validate_input(
    baselines_file: Path,
    sql_units_file: Path
) -> list[str]:
    """
    验证输入文件是否有效
    
    Args:
        baselines_file: recognition/baselines.json 路径
        sql_units_file: parse/sql_units.json 路径
    
    Returns:
        错误列表，空表示输入有效
    """
```

### 6.2 run()

```python
@dataclass
class OptimizeResult:
    success: bool
    output_file: Path          # optimize/proposals.json
    proposals_count: int
    actionable_count: int
    errors: list[str]

def run(
    recognition_output: Path,
    parse_output: Path,
    config: dict,
) -> OptimizeResult:
    """
    运行 Optimize 阶段
    
    Args:
        recognition_output: recognition/baselines.json 路径
        parse_output: parse/sql_units.json 路径
        config: 配置字典
    
    Returns:
        OptimizeResult: 包含输出文件路径和统计信息
    """
```

---

## 7. 依赖关系

```
Optimize 阶段依赖：
├── common/contracts.py       # 契约验证
├── common/run_paths.py      # 路径管理
├── common/config.py         # 配置加载
├── common/errors.py         # 错误定义
│
├── recognition/baselines.json   # 输入（只读）
├── parse/sql_units.json        # 输入（只读）
│
└── optimize/               # 自有模块（禁止其他阶段 import）
    ├── rules_engine.py      # 规则引擎
    ├── llm_provider.py      # LLM 调用
    ├── semantic_check.py     # 语义检查
    └── candidate_selector.py  # 候选选择
```

**关键约束**：`rules_engine.py` `llm_provider.py` `semantic_check.py` **只被 Optimize 使用**，禁止其他阶段 import。

---

## 8. 常见问题

### Q: 优化建议不对？
**A**: 检查 `rules_engine.py` 中的规则定义

### Q: LLM 调用失败？
**A**: 检查 `llm_provider.py` 中的 API 配置

### Q: 语义等价验证失败？
**A**: 检查 `semantic_check.py` 中的验证逻辑
