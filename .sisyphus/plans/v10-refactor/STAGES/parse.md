# Parse 阶段

> 展开动态 SQL 生成分支，检测风险

---

## 1. 阶段职责

**核心职责**：
1. **解析 `<include>` 引用** — 根据 `refid` 查找对应的 `<sql>` 片段，替换到原位置
2. **展开动态 SQL** — 展开 `<if>`, `<choose>`, `<where>` 等标签，生成分支路径
3. **检测潜在风险** — 检测前缀通配符、函数包裹等风险

**输入**：
- `init/sql_units.json` — SQL 单元（含原始 XML 片段）
- `init/sql_fragments.json` — SQL 片段定义
- `init/xml_mappings.json` — 原始 XML 位置映射

**输出**：
- `parse/sql_units.json` — 覆盖 Init 输出，添加 `branches` 字段
- `parse/risks.json` — 风险检测报告
- `parse/xml_mappings.json` — **更新后的位置映射**（`include` 被替换后需要更新位置信息）

**不做什么**：
- ❌ 不扫描 XML 文件（那是 Init 的职责）
- ❌ 不查询表结构（那是 Init 的职责）
- ❌ 不执行 EXPLAIN（那是 Recognition 的职责）
- ❌ 不生成优化建议（那是 Optimize 的职责）

---

## 2. 数据契约

### 2.1 输入

#### 2.1.1 sql_units.json

```json
// init/sql_units.json
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "statementId": "search",
    "statementType": "SELECT",
    "xmlPath": "/path/to/UserMapper.xml",
    "xmlContent": "<select id=\"search\">\n  SELECT * FROM users WHERE 1=1\n  <if test=\"name != null\">AND name = #{name}</if>\n  <include refid=\"common/whereClause\"/>\n</select>",
    "parameterMappings": [...],
    "paramExample": {"name": "test", "status": 1},
    "dynamicFeatures": ["IF", "INCLUDE"]
  }
]
```

#### 2.1.2 sql_fragments.json

```json
// init/sql_fragments.json
[
  {
    "fragmentId": "common/whereClause",
    "xmlPath": "/path/to/UserMapper.xml",
    "xmlContent": "<sql id=\"whereClause\"><where><if test=\"_parameter != null\">${_parameter}</if></where></sql>"
  }
]
```

**关键**：Parse 阶段必须先解析 `<include refid="xxx">` 引用，替换为 `sql_fragments.json` 中对应的 `xmlContent`，然后再展开 `<if>` 等动态标签。

### 2.2 输出 Schema

#### 2.2.1 sql_units.json（覆盖）

**注意**：`xmlContent` 仍然保留（`<include>` 已被替换为实际内容），新增 `branches` 字段。

```json
// parse/sql_units.json
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

**关键变化**：
- `<include refid="common/whereClause"/>` 已被替换为 `<where>...</where>` 内容
- 新增 `branches` 字段，表示展开后的分支

#### 2.2.2 xml_mappings.json（更新）

**注意**：`include` 被替换后，内容变化但 XPath 不变（因为是同一个标签）。

```json
// parse/xml_mappings.json
{
  "files": [
    {
      "xmlPath": "/path/to/UserMapper.xml",
      "statements": [
        {
          "sqlKey": "com.example.UserMapper.search",
          "statementId": "search",
          "xpath": "/mapper/select[@id='search']",
          "tagName": "select",
          "idAttr": "search",
          "originalContent": "<select id=\"search\">...</select>",
          "patches": []  // 待 Result 阶段填充
        }
      ]
    }
  ]
}
```

**关键**：XPath 不变（因为标签本身没变），但 `originalContent` 可能更新了（include 被展开）。

#### 2.2.2 risks.json

```json
// parse/risks.json
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "risks": [
      {
        "riskType": "PREFIX_WILDCARD",
        "severity": "HIGH",
        "message": "Leading wildcard prevents index usage",
        "location": "WHERE clause",
        "branchIds": [1]
      }
    ],
    "prunedBranches": [],
    "recommendedForBaseline": true
  }
]
```

### 2.3 关键字段说明

| 字段 | 说明 |
|------|------|
| `branches` | 展开后的分支列表 |
| `branches[].id` | 分支 ID，从 0 开始 |
| `branches[].conditions` | 分支条件（来自 `<if test="...">` 的 test 属性） |
| `branches[].sql` | 该分支的实际 SQL |
| `branches[].type` | `static`（无条件分支）或 `conditional`（有条件分支） |
| `branchCount` | 总分支数 |
| `problemBranchCount` | 有问题的分支数 |

---

## 3. 目录结构

```
parse/
├── __init__.py
├── api.py                 # 阶段 API（必须）
│                          # - validate_input()
│                          # - run(input_file, fragments_file, config) -> ParseResult
├── run.py                 # 入口实现
├── include_resolver.py    # <include> 引用解析（核心步骤1）
├── branch_generator.py     # 分支展开（核心步骤2）
├── risk_detector.py       # 风险检测
├── sql_node.py           # SQL AST 节点
├── validator.py           # 输出验证
├── README.md             # 本文档
└── STAGE.md             # 阶段设计文档（详细）
```

**处理流程**：
1. `include_resolver.py` — 解析 `<include refid="xxx">`，替换为实际片段
2. `branch_generator.py` — 展开 `<if>` 等动态标签，生成分支
parse/
├── __init__.py
├── api.py                 # 阶段 API（必须）
│                          # - validate_input()
│                          # - run(input_file, config) -> ParseResult
├── run.py                 # 入口实现
├── branch_generator.py    # 分支展开（核心）
├── risk_detector.py       # 风险检测
├── sql_node.py           # SQL AST 节点
├── validator.py           # 输出验证
├── README.md             # 本文档
└── STAGE.md              # 阶段设计文档（详细）
```

---

## 4. 快速调测

### 4.1 准备测试环境

```bash
# 1. 创建测试输入文件
mkdir -p /tmp/sqlopt-test/runs/test-run/parse
cat > /tmp/sqlopt-test/runs/test-run/init/sql_units.json << 'EOF'
[
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "statementId": "search",
    "statementType": "SELECT",
    "xmlPath": "/tmp/sqlopt-test/UserMapper.xml",
    "sql": "SELECT * FROM users WHERE 1=1<if test='name != null'> AND name = #{name}</if><if test='status != null'> AND status = #{status}</if>",
    "parameterMappings": [
      {"name": "name", "jdbcType": "VARCHAR"},
      {"name": "status", "jdbcType": "INTEGER"}
    ],
    "paramExample": {"name": "test", "status": 1},
    "dynamicFeatures": ["IF"]
  }
]
EOF

# 2. 创建测试配置
cat > /tmp/sqlopt-test/sqlopt.yml << 'EOF'
config_version: v1
scan:
  mapper_globs:
    - /tmp/sqlopt-test/*.xml
EOF

export SQLOPT_RUN_DIR=/tmp/sqlopt-test/runs/test-run
```

### 4.2 编写测试代码

```python
# /tmp/sqlopt-test/test_parse.py
import sys
sys.path.insert(0, '/path/to/python')

from sqlopt.parse.api import run, validate_input
from sqlopt.common.config import load_config
import json

# 验证输入
input_file = Path('/tmp/sqlopt-test/runs/test-run/init/sql_units.json')
errors = validate_input(input_file)
if errors:
    print(f"Input errors: {errors}")
    sys.exit(1)

# 运行 Parse
result = run(input_file)

# 检查结果
print(f"Success: {result.success}")
print(f"SQL Units: {result.sql_units_count}")
print(f"Risks: {result.risks_count}")
print(f"Errors: {result.errors}")

# 验证输出
with open(result.sql_units_file) as f:
    data = json.load(f)
    for unit in data:
        print(f"  {unit['sqlKey']}: {unit['branchCount']} branches")

with open(result.risks_file) as f:
    risks = json.load(f)
    print(f"Risks: {len(risks)} SQL with risks")
```

### 4.3 运行测试

```bash
cd /tmp/sqlopt-test
python test_parse.py

# 检查输出
cat /tmp/sqlopt-test/runs/test-run/parse/sql_units.json | python -m json.tool
cat /tmp/sqlopt-test/runs/test-run/parse/risks.json | python -m json.tool
```

### 4.4 预期输出

```json
// parse/sql_units.json
[
  {
    "sqlKey": "com.example.UserMapper.search",
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
        "conditions": ["status IS NOT NULL"],
        "sql": "SELECT * FROM users WHERE 1=1 AND status = #{status}",
        "type": "conditional"
      },
      {
        "id": 3,
        "conditions": ["name IS NOT NULL", "status IS NOT NULL"],
        "sql": "SELECT * FROM users WHERE 1=1 AND name = #{name} AND status = #{status}",
        "type": "conditional"
      }
    ],
    "branchCount": 4,
    "problemBranchCount": 0
  }
]
```

---

## 5. 修改指南

### 5.1 改分支展开逻辑

**文件**：`branch_generator.py`

**原因**：分支展开不对，条件组合有误

**修改**：编辑 `branch_generator.py` 中的分支生成算法

```python
# branch_generator.py
def generate_branches(sql: str, dynamic_features: list[str]) -> list[Branch]:
    # 这里是分支展开逻辑
    # 如果展开不对，改这里
    ...
```

### 5.2 改风险检测规则

**文件**：`risk_detector.py`

**原因**：需要添加新的风险检测规则

**修改**：编辑 `risk_detector.py` 中的检测逻辑

```python
# risk_detector.py
RISK_RULES = [
    {"type": "PREFIX_WILDCARD", "pattern": r"LIKE\s+'%", "severity": "HIGH"},
    {"type": "FUNCTION_WRAP", "pattern": r"WHERE\s+\w+\(", "severity": "MEDIUM"},
    # 添加新规则...
]

def detect_risks(sql: str) -> list[Risk]:
    ...
```

### 5.3 改输出格式

**文件**：`api.py` + `STAGE.md` + `contracts/schemas/sqlunit.schema.json`

**修改流程**：
1. 编辑 `api.py` 中的数据结构
2. 更新 `STAGE.md` 中的 Schema 说明
3. 更新 `contracts/schemas/sqlunit.schema.json`

---

## 6. API 定义

### 6.1 validate_input()

```python
def validate_input(input_file: Path) -> list[str]:
    """
    验证输入文件是否有效
    
    Args:
        input_file: init/sql_units.json 路径
    
    Returns:
        错误列表，空表示输入有效
    """
```

### 6.2 run()

```python
@dataclass
class ParseResult:
    success: bool
    sql_units_file: Path      # parse/sql_units.json
    risks_file: Path          # parse/risks.json
    sql_units_count: int
    risks_count: int
    errors: list[str]

def run(
    init_output: Path,
    config: dict,
) -> ParseResult:
    """
    运行 Parse 阶段
    
    Args:
        init_output: init/sql_units.json 路径
        config: 配置字典
    
    Returns:
        ParseResult: 包含输出文件路径和统计信息
    """
```

---

## 7. 依赖关系

```
Parse 阶段依赖：
├── common/contracts.py    # 契约验证
├── common/run_paths.py    # 路径管理
├── common/config.py       # 配置加载
├── common/errors.py       # 错误定义
│
├── init/sql_units.json    # 输入（只读）
│
└── parse/                 # 自有模块
    ├── branch_generator.py  # 分支展开
    ├── risk_detector.py     # 风险检测
    └── sql_node.py          # SQL AST
```

**关键约束**：`branch_generator.py` `risk_detector.py` `sql_node.py` **只被 Parse 使用**，禁止其他阶段 import。

---

## 8. 常见问题

### Q: 分支数量不对？
**A**: 检查 `branch_generator.py` 中的条件组合算法

### Q: 风险检测漏报？
**A**: 检查 `risk_detector.py` 中的规则定义

### Q: 条件展开有误？
**A**: 检查 `sql_node.py` 中的 AST 解析逻辑
