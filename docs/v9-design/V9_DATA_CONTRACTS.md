# V9 数据契约

> 版本：V9 | 更新日期：2026-03-20

---

## 一、契约优先级

当代码行为与文档冲突时，按以下优先级：
1. `contracts/schemas/*.schema.json` (最高)
2. 当前代码实现 (`python/sqlopt/`)
3. 历史文档 (`docs/`)

---

## 二、V9 阶段映射

V9 将原来的 7 阶段简化为 **5 阶段**：

| V9 阶段 | 输入 Schema | 输出 Schema | 说明 |
|----------|-------------|-------------|------|
| `init` | - | `sqlunit.schema.json` | XML解析、SQL提取 |
| `parse` | `sqlunit.schema.json` | `sqlunit.schema.json` (扩展branches) + risks | 分支展开+风险检测 |
| `recognition` | `sqlunit.schema.json` | `baseline_result.schema.json` | EXPLAIN采集 |
| `optimize` | `baseline_result.schema.json` | `optimization_proposal.schema.json` | 优化+验证(迭代) |
| `patch` | `optimization_proposal.schema.json` | `patch_result.schema.json` | XML补丁生成 |

---

## 三、目录结构

```
runs/<run_id>/
│
├── supervisor/                      # 运行状态
│   ├── meta.json                  # 运行元信息
│   ├── state.json                  # 阶段状态
│   ├── v8_state.json              # V8兼容状态
│   └── results/                    # 各阶段结果
│
├── init/                           # [阶段1] 初始化
│   └── sql_units.json              # SQL单元列表
│
├── parse/                          # [阶段2] 解析(分支+风险)
│   ├── sql_units_with_branches.json # 带分支的SQL单元
│   └── risks.json                  # 风险报告
│
├── recognition/                     # [阶段3] 性能基线
│   └── baselines.json              # EXPLAIN结果
│
├── optimize/                       # [阶段4] 优化(含验证)
│   └── proposals.json              # 优化提案(含验证状态)
│
└── patch/                         # [阶段5] 补丁
    └── patches.json                # 最终补丁
```

---

## 四、数据契约详解

### 4.1 init → parse: `sqlunit.schema.json`

**来源**：Discovery 阶段解析 MyBatis XML 生成

**Schema**：
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SQLUnit",
  "type": "object",
  "required": ["sqlKey", "statementType", "sql"],
  "properties": {
    "sqlKey": {
      "type": "string",
      "description": "唯一标识: namespace.statementId"
    },
    "namespace": {"type": "string"},
    "statementId": {"type": "string"},
    "statementType": {
      "type": "string",
      "enum": ["SELECT", "INSERT", "UPDATE", "DELETE"]
    },
    "xmlPath": {"type": "string"},
    "sql": {"type": "string"},
    "templateSql": {"type": "string"},
    "parameterMappings": {
      "type": "array",
      "items": {"type": "object"}
    },
    "dynamicTags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "动态标签: #{param}, ${param}"
    },
    "riskFlags": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

**示例**：
```json
{
  "sqlKey": "com.example.UserMapper.selectByExample",
  "namespace": "com.example",
  "statementId": "selectByExample",
  "statementType": "SELECT",
  "xmlPath": "/path/to/UserMapper.xml",
  "sql": "SELECT * FROM users WHERE status = #{status}",
  "templateSql": "SELECT * FROM users WHERE status = #{status}",
  "parameterMappings": [{"name": "status", "type": "INTEGER"}],
  "dynamicTags": ["#{status}"],
  "riskFlags": []
}
```

---

### 4.2 parse → recognition: `branches` (扩展 sqlunit)

**来源**：Parse 阶段在 sqlunit 基础上扩展 branches 字段

**Branches 结构**：
```json
{
  "sqlKey": "com.example.UserMapper.selectByExample",
  "sql": "SELECT * FROM users WHERE 1=1",
  "branches": [
    {
      "branch_id": "branch_0",
      "active_conditions": [],
      "sql": "SELECT * FROM users WHERE 1=1",
      "condition_count": 0,
      "risk_flags": []
    },
    {
      "branch_id": "branch_1",
      "active_conditions": ["status IS NOT NULL"],
      "sql": "SELECT * FROM users WHERE 1=1 AND status = #{status}",
      "condition_count": 1,
      "risk_flags": []
    }
  ],
  "branchCount": 2
}
```

---

### 4.3 parse → recognition: `risks.json`

**来源**：Parse 阶段的风险检测结果

**Schema**：
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "sqlKey": {"type": "string"},
      "branchId": {"type": "string"},
      "risks": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "riskType": {
              "type": "string",
              "enum": [
                "prefix_wildcard",
                "suffix_wildcard_only",
                "function_wrap",
                "concat_wildcard",
                "select_star"
              ]
            },
            "severity": {
              "type": "string",
              "enum": ["HIGH", "MEDIUM", "LOW"]
            },
            "location": {"type": "string"},
            "description": {"type": "string"}
          }
        }
      },
      "prunedBranches": {
        "type": "array",
        "items": {"type": "string"}
      }
    }
  }
}
```

**风险类型定义**：

| riskType | 模式 | Severity | 影响 |
|----------|------|----------|------|
| `prefix_wildcard` | `'%'+column` | HIGH | 无法使用索引 |
| `suffix_wildcard_only` | `column+'%'` | LOW | 可用索引 |
| `concat_wildcard` | `CONCAT('%',column)` | HIGH | 全表扫描 |
| `function_wrap` | `UPPER(col)` | MEDIUM | 索引失效 |
| `select_star` | `SELECT *` | MEDIUM | 读取冗余列 |

**示例**：
```json
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "branchId": "branch_2",
    "risks": [
      {
        "riskType": "prefix_wildcard",
        "severity": "HIGH",
        "location": "WHERE name LIKE",
        "description": "前缀通配符导致全表扫描"
      }
    ],
    "prunedBranches": []
  }
]
```

---

### 4.4 recognition → optimize: `baseline_result.schema.json`

**来源**：Recognition 阶段采集的 EXPLAIN 结果

**Schema**：
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "required": ["sqlKey", "executionPlan"],
    "properties": {
      "sqlKey": {"type": "string"},
      "branchId": {"type": "string"},
      "sql": {"type": "string"},
      "executionPlan": {
        "type": "object",
        "properties": {
          "operation": {"type": "string"},
          "relation": {"type": "string"},
          "rows": {"type": "integer"},
          "cost": {"type": "number"},
          "usedIndex": {"type": "string"}
        }
      },
      "performanceMetrics": {
        "type": "object",
        "properties": {
          "estimatedRows": {"type": "integer"},
          "actualRows": {"type": "integer"},
          "executionTimeMs": {"type": "number"}
        }
      },
      "databasePlatform": {
        "type": "string",
        "enum": ["postgresql", "mysql"]
      }
    }
  }
}
```

**示例**：
```json
[
  {
    "sqlKey": "com.example.UserMapper.selectByExample:branch:1",
    "branchId": "branch_1",
    "sql": "SELECT * FROM users WHERE status = 1",
    "executionPlan": {
      "operation": "Index Scan",
      "relation": "users",
      "rows": 150,
      "cost": 25.5,
      "usedIndex": "idx_users_status"
    },
    "performanceMetrics": {
      "estimatedRows": 150,
      "actualRows": 148,
      "executionTimeMs": 2.3
    },
    "databasePlatform": "postgresql"
  }
]
```

---

### 4.5 optimize → patch: `optimization_proposal.schema.json`

**来源**：Optimize 阶段生成的优化提案（含验证状态）

**Schema**：
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "required": ["sqlKey", "originalSql", "ruleName", "optimizedSql"],
    "properties": {
      "sqlKey": {"type": "string"},
      "originalSql": {"type": "string"},
      "ruleName": {"type": "string"},
      "optimizedSql": {"type": "string"},
      "improvement": {
        "type": "object",
        "properties": {
          "estimatedCostReduction": {"type": "string"},
          "columnsReduced": {"type": "integer"}
        }
      },
      "iterations": {"type": "integer"},
      "validated": {"type": "boolean"},
      "confidence": {
        "type": "number",
        "minimum": 0,
        "maximum": 1
      }
    }
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `sqlKey` | string | SQL唯一标识 |
| `originalSql` | string | 原始SQL |
| `ruleName` | string | 应用的优化规则名 |
| `optimizedSql` | string | 优化后SQL |
| `iterations` | integer | 迭代次数 |
| `validated` | boolean | 是否通过语义验证 |
| `confidence` | number | 验证置信度 0-1 |

**示例**：
```json
[
  {
    "sqlKey": "com.example.UserMapper.selectByExample:branch:1",
    "originalSql": "SELECT * FROM users WHERE status = 1",
    "ruleName": "select_minimize",
    "optimizedSql": "SELECT id, name, status FROM users WHERE status = 1",
    "improvement": {
      "estimatedCostReduction": "35%",
      "columnsReduced": 5
    },
    "iterations": 2,
    "validated": true,
    "confidence": 0.95
  }
]
```

---

### 4.6 patch: `patch_result.schema.json`

**来源**：Patch 阶段生成的最终补丁

**Schema**：
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "required": ["sqlKey", "ruleName", "status"],
    "properties": {
      "sqlKey": {"type": "string"},
      "ruleName": {"type": "string"},
      "status": {
        "type": "string",
        "enum": ["ready", "applied", "rolled_back"]
      },
      "applied": {"type": "boolean"},
      "patch": {
        "type": "object",
        "properties": {
          "before": {"type": "string"},
          "after": {"type": "string"}
        }
      }
    }
  }
}
```

---

## 五、CLI 命令与阶段映射

| CLI 命令 | 执行阶段 | V9 支持 |
|---------|---------|---------|
| `sqlopt-cli run --config sqlopt.yml` | 1-5 全部 | ✅ |
| `sqlopt-cli run --config sqlopt.yml --stage <stage>` | 指定阶段 | ✅ |
| `sqlopt-cli diagnose` | 1-2 (init+parse) | ✅ |
| `sqlopt-cli recognition --mapper <path> --dsn <dsn>` | 3 | ✅ |
| `sqlopt-cli optimize --config sqlopt.yml [--sql-key <key>]` | 4 | ⚠️ 需更新 |
| `sqlopt-cli verify --run-id <id> --sql-key <key>` | 4 结果查询 | ✅ |
| `sqlopt-cli apply --run-id <id>` | 5 | ✅ |
| `sqlopt-cli status --run-id <id>` | - | ✅ |
| `sqlopt-cli resume --run-id <id>` | 断点恢复 | ✅ |

---

## 六、阶段接口定义

### 6.1 Stage 基类接口

```python
class Stage(ABC):
    name: str = "base"           # 阶段名称
    version: str = "1.0.0"       # 阶段版本
    dependencies: list[str] = []  # 依赖阶段列表

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
```

### 6.2 StageContext 上下文

```python
@dataclass
class StageContext:
    run_id: str                  # 运行ID
    config: dict                 # 配置字典
    data_dir: Path               # 数据目录
    cache_dir: Path              # 缓存目录
    metadata: dict               # 元数据字典
```

### 6.3 StageResult 结果

```python
@dataclass
class StageResult:
    success: bool                # 是否成功
    output_files: list[Path]     # 输出文件列表
    artifacts: dict              # 产物字典
    errors: list[str]            # 错误列表
    warnings: list[str]          # 警告列表
```

### 6.4 阶段注册

```python
@stage_registry.register
class MyStage(Stage):
    name: str = "my_stage"
    version: str = "1.0.0"
    dependencies: list[str] = ["init", "recognition"]

    def execute(self, context: StageContext) -> StageResult:
        # 实现...
        pass

    def get_input_contracts(self) -> list[str]:
        return ["sqlunit", "baseline_result"]

    def get_output_contracts(self) -> list[str]:
        return ["my_output"]
```

---

## 七、ContractValidator 验证

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

---

## 八、变更记录

### V9 变更 (2026-03-20)

1. **阶段合并**：
   - Discovery → Init (重命名)
   - Branching + Pruning → Parse (合并)
   - Optimize + Validate → Optimize (合并为迭代)

2. **目录变更**：
   - 新增 `init/` 目录
   - 新增 `parse/` 目录 (原 branching + pruning)
   - 移除 `validate/` 目录

3. **契约变更**：
   - `optimization_proposal` 新增 `validated`, `iterations`, `confidence` 字段
   - 合并 branches 和 risks 到 `parse/` 阶段

---

*本文档最后更新：2026-03-20*
