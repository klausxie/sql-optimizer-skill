# Recognition 阶段

> 对每个分支执行 EXPLAIN，采集性能基线

---

## 1. 阶段职责

**核心职责**：对每个 SQL 分支执行 `EXPLAIN`，采集执行计划和时间等性能数据

**输入**：
- `parse/sql_units.json` — Parse 阶段的输出（含 branches）

**输出**：
- `recognition/baselines.json` — 性能基线列表

**不做什么**：
- ❌ 不展开动态 SQL（那是 Parse 的职责）
- ❌ 不生成优化建议（那是 Optimize 的职责）
- ❌ 不生成补丁（那是 Patch 的职责）

---

## 2. 数据契约

### 2.1 输入

```json
// parse/sql_units.json（摘录）
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "branches": [
      {"id": 0, "conditions": [], "sql": "SELECT * FROM users WHERE 1=1", "type": "static"},
      {"id": 1, "conditions": ["name IS NOT NULL"], "sql": "SELECT * FROM users WHERE name = #{name}", "type": "conditional"}
    ],
    "branchCount": 2
  }
]
```

### 2.2 输出 Schema

#### 2.2.1 baselines.json

```json
// recognition/baselines.json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "executionTimeMs": 12.5,
    "rowsScanned": 1520,
    "rowsReturned": 10,
    "executionPlan": {
      "nodeType": "Seq Scan",
      "relationName": "users",
      "alias": "users",
      "startupCost": 0.00,
      "totalCost": 43.21,
      "estimatedRows": 1000,
      "actualRows": 1520,
      "outputColumns": ["id", "name", "email", "status"],
      "filter": null,
      "indexUsed": null,
      "indexName": null,
      "mergeJoinUsed": false,
      "bitmapHeapScanUsed": false,
      "nestedLoopUsed": false,
      "hashJoinUsed": false
    },
    "databasePlatform": "postgresql",
    "sampleParams": {"name": "test"},
    "bufferHits": 100,
    "bufferReads": 20,
    "executionTimeMs": 12.5,
    "resultHash": "a1b2c3d4e5f6",
    "explainPlan": {
      "format": "json",
      "raw": {
        "Plan": {
          "Node Type": "Seq Scan",
          "Relation Name": "users",
          "Alias": "users",
          "Startup Cost": 0.00,
          "Total Cost": 43.21,
          "Plan Rows": 1000,
          "Plan Width": 84,
          "Actual Startup Time": 0.012,
          "Actual Total Time": 0.015,
          "Actual Rows": 1520,
          "Actual Loops": 1,
          "Output": ["id", "name", "email", "status"],
          "Buffers": {
            "shared hit": 100,
            "read": 20
          }
        }
      }
    }
  },
  {
    "sqlKey": "com.example.UserMapper:branch:1",
    "executionTimeMs": 5.2,
    "rowsScanned": 100,
    "rowsReturned": 5,
    "executionPlan": {
      "nodeType": "Index Scan",
      "relationName": "users",
      "alias": "users",
      "startupCost": 0.11,
      "totalCost": 5.34,
      "estimatedRows": 50,
      "actualRows": 100,
      "outputColumns": ["id", "name", "email", "status"],
      "filter": null,
      "indexUsed": true,
      "indexName": "idx_user_name",
      "mergeJoinUsed": false,
      "bitmapHeapScanUsed": false,
      "nestedLoopUsed": true,
      "hashJoinUsed": false
    },
    "databasePlatform": "postgresql",
    "sampleParams": {"name": "test"},
    "bufferHits": 95,
    "bufferReads": 5,
    "executionTimeMs": 5.2,
    "resultHash": "f6e5d4c3b2a1",
    "explainPlan": {
      "format": "json",
      "raw": {
        "Plan": {
          "Node Type": "Index Scan",
          "Relation Name": "users",
          "Alias": "users",
          "Startup Cost": 0.11,
          "Total Cost": 5.34,
          "Plan Rows": 50,
          "Plan Width": 84,
          "Actual Startup Time": 0.008,
          "Actual Total Time": 0.012,
          "Actual Rows": 100,
          "Actual Loops": 1,
          "Index Name": "idx_user_name",
          "Output": ["id", "name", "email", "status"],
          "Buffers": {
            "shared hit": 95,
            "read": 5
          }
        }
      }
    }
  }
]
```

### 2.3 关键字段说明

#### 2.3.1 主字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `sqlKey` | 分支唯一标识 | `com.example.UserMapper:branch:0` |
| `executionTimeMs` | 执行时间（毫秒） | `12.5` |
| `rowsScanned` | 实际扫描行数 | `1520` |
| `rowsReturned` | 实际返回行数 | `10` |
| `databasePlatform` | 数据库平台 | `postgresql`, `mysql` |
| `sampleParams` | 执行时使用的参数 | `{"name": "test"}` |
| `resultHash` | 结果哈希（去重用） | `a1b2c3d4e5f6` |

#### 2.3.2 executionPlan 字段（简化版）

| 字段 | 说明 | 示例 |
|------|------|------|
| `nodeType` | 节点类型 | `Seq Scan`, `Index Scan`, `Bitmap Heap Scan` |
| `relationName` | 扫描的表名 | `users` |
| `alias` | 表别名 | `users` |
| `startupCost` | 启动代价 | `0.00` |
| `totalCost` | 总代价 | `43.21` |
| `estimatedRows` | 估算行数 | `1000` |
| `actualRows` | 实际行数 | `1520` |
| `outputColumns` | 输出列 | `["id", "name", "email"]` |
| `indexUsed` | 是否使用索引 | `true`, `false` |
| `indexName` | 使用的索引名 | `idx_user_name` |
| `filter` | Filter 条件 | `NULL` |
| `mergeJoinUsed` | 是否使用 Merge Join | `true`, `false` |
| `bitmapHeapScanUsed` | 是否使用 Bitmap Heap Scan | `true`, `false` |
| `nestedLoopUsed` | 是否使用 Nested Loop | `true`, `false` |
| `hashJoinUsed` | 是否使用 Hash Join | `true`, `false` |

#### 2.3.3 explainPlan 字段（完整原始）

| 字段 | 说明 | 示例 |
|------|------|------|
| `explainPlan.format` | EXPLAIN 输出格式 | `json`, `text` |
| `explainPlan.raw` | **原始完整输出** | PostgreSQL JSON / MySQL JSON |

**注意**：`explainPlan.raw` 包含数据库返回的**完整原始输出**，用于调试和对账。不同的数据库平台输出格式不同。

---

## 3. 目录结构

```
recognition/
├── __init__.py
├── api.py                 # 阶段 API（必须）
│                          # - validate_input()
│                          # - run(input_file, config) -> RecognitionResult
├── run.py                # 入口实现
├── explain_collector.py   # EXPLAIN 采集（核心）
├── baseline_runner.py     # 基线执行
├── db_connector.py       # 数据库连接
├── plan_parser.py        # 执行计划解析
├── README.md            # 本文档
└── STAGE.md             # 阶段设计文档（详细）
```

---

## 4. 快速调测

### 4.1 准备测试环境

```bash
# 1. 创建测试输入文件
mkdir -p /tmp/sqlopt-test/runs/test-run/recognition
cat > /tmp/sqlopt-test/runs/test-run/parse/sql_units.json << 'EOF'
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "statementId": "search",
    "sql": "SELECT * FROM users WHERE name = #{name}",
    "branches": [
      {
        "id": 0,
        "conditions": [],
        "sql": "SELECT * FROM users",
        "type": "static"
      },
      {
        "id": 1,
        "conditions": ["name IS NOT NULL"],
        "sql": "SELECT * FROM users WHERE name = #{name}",
        "type": "conditional"
      }
    ],
    "branchCount": 2
  }
]
EOF

# 2. 创建测试配置
cat > /tmp/sqlopt-test/sqlopt.yml << 'EOF'
config_version: v1
db:
  platform: postgresql
  dsn: postgresql://user:password@localhost:5432/testdb
EOF

export SQLOPT_RUN_DIR=/tmp/sqlopt-test/runs/test-run
```

### 4.2 编写测试代码

```python
# /tmp/sqlopt-test/test_recognition.py
import sys
sys.path.insert(0, '/path/to/python')

from sqlopt.recognition.api import run, validate_input
from sqlopt.common.config import load_config
import json

# 验证输入
input_file = Path('/tmp/sqlopt-test/runs/test-run/parse/sql_units.json')
errors = validate_input(input_file)
if errors:
    print(f"Input errors: {errors}")
    sys.exit(1)

# 运行 Recognition
config = load_config('/tmp/sqlopt-test/sqlopt.yml')
result = run(input_file, config)

# 检查结果
print(f"Success: {result.success}")
print(f"Baselines: {result.baselines_count}")
print(f"Errors: {result.errors}")

# 验证输出
with open(result.output_file) as f:
    baselines = json.load(f)
    for b in baselines:
        print(f"  {b['sqlKey']}: {b['executionTimeMs']}ms, {b['rowsScanned']} rows")
```

### 4.3 运行测试

```bash
cd /tmp/sqlopt-test
python test_recognition.py

# 检查输出
cat /tmp/sqlopt-test/runs/test-run/recognition/baselines.json | python -m json.tool
```

### 4.4 预期输出

```json
[
  {
    "sqlKey": "com.example.UserMapper:branch:0",
    "executionTimeMs": 15.3,
    "rowsScanned": 10000,
    "rowsReturned": 100,
    "executionPlan": {
      "nodeType": "Seq Scan",
      "indexUsed": null,
      "cost": 123.45
    },
    "databasePlatform": "postgresql",
    "sampleParams": {}
  },
  {
    "sqlKey": "com.example.UserMapper:branch:1",
    "executionTimeMs": 2.1,
    "rowsScanned": 100,
    "rowsReturned": 10,
    "executionPlan": {
      "nodeType": "Index Scan",
      "indexUsed": "idx_user_name",
      "cost": 5.32
    },
    "databasePlatform": "postgresql",
    "sampleParams": {"name": "test"}
  }
]
```

---

## 5. 修改指南

### 5.1 改 EXPLAIN 采集逻辑

**文件**：`explain_collector.py`

**原因**：EXPLAIN 执行方式不对，平台兼容性问题

**修改**：编辑 `explain_collector.py` 中的采集逻辑

```python
# explain_collector.py
def collect_explain(sql: str, db_config: dict) -> ExecutionPlan:
    # 这里是 EXPLAIN 采集逻辑
    # 如果采集不对，改这里
    ...
```

### 5.2 改执行计划解析

**文件**：`plan_parser.py`

**原因**：不同数据库平台的 EXPLAIN 输出格式解析不对

**修改**：编辑 `plan_parser.py` 中的解析逻辑

```python
# plan_parser.py
def parse_plan(raw_output: str, platform: str) -> ExecutionPlan:
    if platform == "postgresql":
        # PostgreSQL 解析
        ...
    elif platform == "mysql":
        # MySQL 解析
        ...
```

### 5.3 改数据库连接

**文件**：`db_connector.py`（在 common/ 下）

**原因**：数据库连接配置不对

**修改**：编辑 `common/db_connector.py`

---

## 6. API 定义

### 6.1 validate_input()

```python
def validate_input(input_file: Path) -> list[str]:
    """
    验证输入文件是否有效
    
    Args:
        input_file: parse/sql_units.json 路径
    
    Returns:
        错误列表，空表示输入有效
    """
```

### 6.2 run()

```python
@dataclass
class RecognitionResult:
    success: bool
    output_file: Path         # recognition/baselines.json
    baselines_count: int
    errors: list[str]

def run(
    parse_output: Path,
    config: dict,
) -> RecognitionResult:
    """
    运行 Recognition 阶段
    
    Args:
        parse_output: parse/sql_units.json 路径
        config: 配置字典，包含 db 连接信息
    
    Returns:
        RecognitionResult: 包含输出文件路径和统计信息
    """
```

---

## 7. 依赖关系

```
Recognition 阶段依赖：
├── common/contracts.py       # 契约验证
├── common/run_paths.py      # 路径管理
├── common/config.py         # 配置加载
├── common/errors.py         # 错误定义
├── common/db_connector.py   # 数据库连接
│
├── parse/sql_units.json     # 输入（只读）
│
└── recognition/            # 自有模块
    ├── explain_collector.py  # EXPLAIN 采集
    ├── baseline_runner.py   # 基线执行
    └── plan_parser.py       # 执行计划解析
```

---

## 8. 常见问题

### Q: EXPLAIN 执行超时？
**A**: 检查 `db_connector.py` 中的超时配置

### Q: 执行计划解析失败？
**A**: 检查 `plan_parser.py` 是否支持该数据库平台

### Q: 连接数据库失败？
**A**: 检查配置中的 `dsn` 格式是否正确
