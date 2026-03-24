# Init 阶段

> 扫描 MyBatis XML 文件，提取 SQL 单元

---

## 1. 阶段职责

**核心职责**：
1. 扫描 MyBatis XML 映射文件，提取 SQL 语句单元
2. 提取所有 `<sql id="">` 片段定义
3. **记录每个片段在原始 XML 文件中的位置**（用于后续 Patch 生成补丁）
4. **根据 SQL 中的表名，查询数据库获取表结构和索引信息**

**输入**：
- 配置文件 `scan.mapper_globs`（文件路径模式）
- 数据库连接（用于查询表结构）

**输出**：
- `init/sql_units.json` — SQL 单元列表（含原始 XML 片段）
- `init/sql_fragments.json` — SQL 片段定义（含原始位置）
- `init/table_schemas.json` — 表结构信息（列、索引等）
- `init/xml_mappings.json` — 原始 XML 文件位置映射（用于 Patch 生成补丁）

**不做什么**：
- ❌ 不展开动态标签（那是 Parse 的职责）
- ❌ 不检测风险（那是 Parse 的职责）
- ❌ 不执行 EXPLAIN（那是 Recognition 的职责）

---

## 2. 数据契约

### 2.1 输入

从配置文件读取：
```yaml
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
    - **/*Mapper.xml

db:
  platform: postgresql
  dsn: postgresql://user:password@localhost:5432/dbname
```

**为什么需要数据库连接**：Init 阶段需要查询数据库获取表结构和索引信息，Optimize/Recognition 阶段需要这些信息来解释执行计划。

### 2.2 输出 Schema

#### 2.2.1 sql_units.json

**关键**：这里存储的是**原始 XML 片段**，不是展开后的 SQL。动态展开由 Parse 阶段完成。

```json
// init/sql_units.json
[
  {
    "sqlKey": "com.example.UserMapper.selectByEmail",
    "namespace": "com.example.UserMapper",
    "statementId": "selectByEmail",
    "statementType": "SELECT",
    "xmlPath": "/path/to/UserMapper.xml",
    "xmlContent": "<select id=\"selectByEmail\" resultType=\"User\">\n  SELECT * FROM users WHERE email = #{email}\n</select>",
    "parameterMappings": [
      {"name": "email", "jdbcType": "VARCHAR"}
    ],
    "paramExample": {"email": "test@example.com"},
    "dynamicFeatures": []
  },
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "statementId": "search",
    "statementType": "SELECT",
    "xmlPath": "/path/to/UserMapper.xml",
    "xmlContent": "<select id=\"search\" resultType=\"User\">\n  SELECT * FROM users WHERE 1=1\n  <if test=\"name != null\">AND name = #{name}</if>\n  <if test=\"status != null\">AND status = #{status}</if>\n  <include refid=\"common/whereClause\"/>\n</select>",
    "parameterMappings": [
      {"name": "name", "jdbcType": "VARCHAR"},
      {"name": "status", "jdbcType": "INTEGER"}
    ],
    "paramExample": {"name": "test", "status": 1},
    "dynamicFeatures": ["IF", "INCLUDE"]
  }
]
```

#### 2.2.2 sql_fragments.json

**关键**：存储所有 `<sql id="">` 片段定义，被 `<include refid="xxx">` 引用。

```json
// init/sql_fragments.json
[
  {
    "fragmentId": "common/whereClause",
    "xmlPath": "/path/to/UserMapper.xml",
    "startLine": 15,
    "endLine": 20,
    "xmlContent": "<sql id=\"whereClause\">\n  <where>\n    <if test=\"_parameter != null\">\n      ${{fragment.field}} -- 引用外部变量\n    </if>\n  </where>\n</sql>"
  },
  {
    "fragmentId": "userColumns",
    "xmlPath": "/path/to/UserMapper.xml",
    "startLine": 22,
    "endLine": 24,
    "xmlContent": "<sql id=\"userColumns\">\n  id, name, email, status, created_at\n</sql>"
  }
]
```

#### 2.2.3 table_schemas.json

**关键**：包含表的统计信息，用于 Optimize 阶段判断优化价值。

```json
// init/table_schemas.json
{
  "users": {
    "columns": [
      {"name": "id", "type": "INTEGER", "nullable": false, "primaryKey": true},
      {"name": "email", "type": "VARCHAR(255)", "nullable": false, "unique": true},
      {"name": "name", "type": "VARCHAR(100)", "nullable": true},
      {"name": "status", "type": "INTEGER", "nullable": true, "default": 1}
    ],
    "indexes": [
      {"name": "idx_user_email", "columns": ["email"], "unique": true, "type": "UNIQUE"},
      {"name": "idx_user_name", "columns": ["name"], "unique": false, "type": "INDEX"}
    ],
    "database": "postgresql",
    "statistics": {
      "rowCount": 1520347,
      "totalSizeBytes": 104857600,
      "lastVacuumTime": "2026-03-20T10:30:00Z",
      "lastAnalyzeTime": "2026-03-22T14:00:00Z",
      "deadTuples": 1234,
      "deadTuplesPercent": 0.08
    }
  }
}
```

**关键**：记录原始 XML 文件中每个片段的 **XPath 路径**，用于 Patch 阶段精确定位和修改。

```json
// init/xml_mappings.json
{
  "files": [
    {
      "xmlPath": "/path/to/UserMapper.xml",
      "fragments": [
        {
          "fragmentId": "common/whereClause",
          "sqlKey": null,
          "xpath": "/mapper/sql[@id='whereClause']",
          "tagName": "sql",
          "idAttr": "whereClause",
          "originalContent": "<sql id=\"whereClause\">\n  <where>...</where>\n</sql>"
        },
        {
          "fragmentId": "userColumns",
          "sqlKey": null,
          "xpath": "/mapper/sql[@id='userColumns']",
          "tagName": "sql",
          "idAttr": "userColumns",
          "originalContent": "<sql id=\"userColumns\">...</sql>"
        }
      ],
      "statements": [
        {
          "sqlKey": "com.example.UserMapper.search",
          "statementId": "search",
          "xpath": "/mapper/select[@id='search']",
          "tagName": "select",
          "idAttr": "search",
          "originalContent": "<select id=\"search\">...</select>"
        }
      ]
    }
  ]
}
```

**用途**：Patch 阶段根据 XPath 定位原始 XML 文件中的标签，生成补丁。

**为什么用 XPath 而不是行号**：
- 行号会因为批量修改而变化
- XPath 通过标签路径 + id 属性精确定位，不受其他修改影响
- 例如：`/mapper/select[@id='search']` 永远指向 namespace=search 的 select 标签

### 2.3 关键字段说明

#### sql_units.json 字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `sqlKey` | 唯一标识 | `com.example.UserMapper.selectByEmail` |
| `namespace` | MyBatis namespace | `com.example.UserMapper` |
| `statementId` | SQL ID | `selectByEmail` |
| `statementType` | 语句类型 | `SELECT`, `INSERT`, `UPDATE`, `DELETE` |
| `xmlPath` | XML 文件路径 | `/path/to/UserMapper.xml` |
| `xmlContent` | **原始 XML 片段（含标签）** | `<select>...<if test="...">...</if></select>` |
| `parameterMappings` | 参数映射 | `[{"name": "email", "jdbcType": "VARCHAR"}]` |
| `paramExample` | 示例参数 | `{"email": "test@example.com"}` |
| `dynamicFeatures` | 动态标签类型 | `["IF", "INCLUDE", "WHERE", "CHOOSE", "FOREACH"]` |

**注意**：`xmlContent` 是**原始 XML 片段**，包含 `<if>`, `<include>` 等标签。Parse 阶段负责解析这些标签并展开。

#### sql_fragments.json 字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `fragmentId` | 片段唯一标识 | `common/whereClause`, `userColumns` |
| `xmlPath` | 定义片段的 XML 文件路径 | `/path/to/UserMapper.xml` |
| `startLine` | 片段在 XML 中的起始行号 | `15` |
| `endLine` | 片段在 XML 中的结束行号 | `20` |
| `xmlContent` | 片段的原始 XML 内容 | `<sql id="whereClause">...</sql>` |

**注意**：`fragmentId` 可能是跨文件的引用（如 `otherMapper/someFragment`），需要按 `namespace/id` 解析。

#### xml_mappings.json 字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `files[].xmlPath` | XML 文件路径 | `/path/to/UserMapper.xml` |
| `files[].fragments` | 该文件中的片段位置 | `[{...}, {...}]` |
| `files[].statements` | 该文件中的语句位置 | `[{...}, {...}]` |
| `fragment.fragmentId` | 片段 ID | `common/whereClause` |
| `fragment.xpath` | **XPath 路径**（Patch 用） | `/mapper/sql[@id='whereClause']` |
| `fragment.tagName` | 标签名 | `sql`, `select` |
| `fragment.idAttr` | id 属性名 | `whereClause` |
| `fragment.originalContent` | 原始 XML 内容 | `<sql id="...">...</sql>` |

**注意**：Init 阶段用行号做静态分析没问题，但 `xml_mappings.json` 存储的是 **XPath 路径**，供 Patch 阶段使用。

#### table_schemas.json 字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `表名` | 表名作为 key | `users` |
| `columns` | 列信息列表 | `[{"name": "id", "type": "INTEGER", ...}]` |
| `indexes` | 索引信息列表 | `[{...}, {...}]` |
| `database` | 数据库平台 | `postgresql`, `mysql` |
| `statistics.rowCount` | **表行数**（Optimize 用） | `1520347` |
| `statistics.totalSizeBytes` | 表总大小 | `104857600` |
| `statistics.lastVacuumTime` | 最后 VACUUM 时间 | ISO 时间戳 |
| `statistics.lastAnalyzeTime` | 最后 ANALYZE 时间 | ISO 时间戳 |

**注意**：`statistics.rowCount` 是 Optimize 阶段判断优化价值的关键数据。比如 100 行的表全表扫描很快，优化意义不大；但 1500 万行的表全表扫描很慢，优化很有价值。

---

## 3. 目录结构

```
init/
├── __init__.py
├── api.py              # 阶段 API（必须）
│                        # - validate_config()
│                        # - run(config) -> InitResult
├── run.py              # 入口实现
├── scanner.py          # XML 文件扫描
├── parser.py           # SQL 提取解析（含 <sql> 片段提取）
├── table_extractor.py   # 表结构提取（核心）
├── validator.py        # 输出验证
├── README.md           # 本文档
└── STAGE.md            # 阶段设计文档（详细）
```

**职责分配**：
- `parser.py` — 同时提取 `<select>` 等语句和 `<sql id="">` 片段
- `table_extractor.py` — 查询数据库获取表结构和索引

---

## 4. 快速调测

### 4.1 准备测试环境

```bash
# 1. 创建测试 XML 文件
mkdir -p /tmp/sqlopt-test
cat > /tmp/sqlopt-test/UserMapper.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" 
  "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.UserMapper">
  
  <select id="selectByEmail" resultType="User">
    SELECT * FROM users WHERE email = #{email}
  </select>
  
  <select id="search" resultType="User">
    SELECT * FROM users WHERE 1=1
    <if test="name != null">
      AND name = #{name}
    </if>
    <if test="status != null">
      AND status = #{status}
    </if>
  </select>
  
</mapper>
EOF

# 2. 创建测试配置
cat > /tmp/sqlopt-test/sqlopt.yml << 'EOF'
config_version: v1
scan:
  mapper_globs:
    - /tmp/sqlopt-test/*.xml
db:
  platform: postgresql
  dsn: postgresql://user:password@localhost:5432/testdb
EOF

# 3. 创建测试运行目录
export SQLOPT_RUN_DIR=/tmp/sqlopt-test/runs/test-run
mkdir -p $SQLOPT_RUN_DIR/init
```

### 4.2 编写测试代码

```python
# /tmp/sqlopt-test/test_init.py
import sys
sys.path.insert(0, '/path/to/python')

from sqlopt.init.api import run, validate_config
from sqlopt.common.config import load_config
import json

# 加载配置
config = load_config('/tmp/sqlopt-test/sqlopt.yml')

# 验证配置
errors = validate_config(config)
if errors:
    print(f"Config errors: {errors}")
    sys.exit(1)

# 运行 Init
result = run(config)

# 检查结果
print(f"Success: {result.success}")
print(f"SQL Units: {result.sql_units_count}")
print(f"Tables: {result.tables_count}")
print(f"Errors: {result.errors}")

# 验证 SQL Units 输出
if result.sql_units_file.exists():
    with open(result.sql_units_file) as f:
        data = json.load(f)
        print(f"SQL Units: {len(data)}")

# 验证 Table Schemas 输出
if result.table_schemas_file.exists():
    with open(result.table_schemas_file) as f:
        data = json.load(f)
        print(f"Table Schemas: {list(data.keys())}")
```

### 4.3 运行测试

```bash
cd /tmp/sqlopt-test
python test_init.py

# 检查 SQL Units 输出
cat /tmp/sqlopt-test/runs/test-run/init/sql_units.json | python -m json.tool

# 检查 Table Schemas 输出
cat /tmp/sqlopt-test/runs/test-run/init/table_schemas.json | python -m json.tool
```

### 4.4 预期输出

```json
// sql_units.json
[
  {
    "sqlKey": "com.example.UserMapper.selectByEmail",
    "namespace": "com.example.UserMapper",
    "statementId": "selectByEmail",
    "statementType": "SELECT",
    "xmlPath": "/tmp/sqlopt-test/UserMapper.xml",
    "sql": "SELECT * FROM users WHERE email = #{email}",
    "parameterMappings": [
      {"name": "email", "jdbcType": "VARCHAR"}
    ],
    "paramExample": {"email": "test@example.com"},
    "dynamicFeatures": []
  },
  {
    "sqlKey": "com.example.UserMapper.search",
    "namespace": "com.example.UserMapper",
    "statementId": "search",
    "statementType": "SELECT",
    "xmlPath": "/tmp/sqlopt-test/UserMapper.xml",
    "sql": "SELECT * FROM users WHERE 1=1\n    AND name = #{name}\n    AND status = #{status}",
    "parameterMappings": [
      {"name": "name", "jdbcType": "VARCHAR"},
      {"name": "status", "jdbcType": "INTEGER"}
    ],
    "paramExample": {"name": "test", "status": 1},
    "dynamicFeatures": ["IF"]
  }
]

// table_schemas.json
{
  "users": {
    "columns": [
      {"name": "id", "type": "INTEGER", "nullable": false, "primaryKey": true},
      {"name": "email", "type": "VARCHAR(255)", "nullable": false, "unique": true},
      {"name": "name", "type": "VARCHAR(100)", "nullable": true},
      {"name": "status", "type": "INTEGER", "nullable": true, "default": 1}
    ],
    "indexes": [
      {"name": "idx_user_email", "columns": ["email"], "unique": true, "type": "UNIQUE"},
      {"name": "idx_user_name", "columns": ["name"], "unique": false, "type": "INDEX"}
    ],
    "database": "postgresql"
  }
}
```

---

## 5. 修改指南

### 5.1 改 XML 解析逻辑

**文件**：`parser.py`

**原因**：XML 解析不对，SQL 提取有误

**修改**：编辑 `parser.py` 中的解析逻辑

```python
# parser.py
def parse_mapper_file(xml_path: Path) -> list[dict]:
    # 这里是 XML 解析逻辑
    # 如果解析不对，改这里
    ...
```

### 5.2 改文件扫描逻辑

**文件**：`scanner.py`

**原因**：扫描不到文件，glob 模式不对

**修改**：编辑 `scanner.py` 中的扫描逻辑

```python
# scanner.py
def scan_mapper_files(patterns: list[str]) -> list[Path]:
    # 这里是文件扫描逻辑
    # 如果扫描不到文件，改这里
    ...
```

### 5.3 改表结构提取逻辑

**文件**：`table_extractor.py`

**原因**：表结构提取不对，索引信息不全

**修改**：编辑 `table_extractor.py` 中的提取逻辑

```python
# table_extractor.py
def extract_table_schemas(sql_units: list[dict], db_config: dict) -> dict:
    # 1. 从 SQL 中提取表名
    # 2. 查询数据库获取表结构
    # 3. 查询数据库获取索引信息
    # 如果提取不对，改这里
    ...
```

### 5.4 改输出格式

**文件**：`api.py` + `STAGE.md`

**原因**：需要添加/删除/修改输出字段

**修改**：
1. 编辑 `api.py` 中的数据结构
2. 更新 `STAGE.md` 中的 Schema 说明
3. 更新 `contracts/schemas/sqlunit.schema.json`

---

## 6. API 定义

### 6.1 validate_config()

```python
def validate_config(config: dict) -> list[str]:
    """
    验证配置是否有效
    
    Args:
        config: 配置字典
    
    Returns:
        错误列表，空表示配置有效
    """
```

### 6.2 run()

```python
@dataclass
class InitResult:
    success: bool
    sql_units_file: Path        # init/sql_units.json
    table_schemas_file: Path    # init/table_schemas.json
    sql_units_count: int
    tables_count: int
    errors: list[str]

def run(config: dict) -> InitResult:
    """
    运行 Init 阶段
    
    Args:
        config: 配置字典，包含 scan.mapper_globs 和 db 连接信息
    
    Returns:
        InitResult: 包含输出文件路径和统计信息
    """
```

---

## 7. 依赖关系

```
Init 阶段依赖：
├── common/contracts.py       # 契约验证
├── common/run_paths.py      # 路径管理
├── common/config.py         # 配置加载
├── common/errors.py         # 错误定义
├── common/db_connector.py   # 数据库连接
```

**无阶段间依赖** — Init 是起始阶段，不依赖其他阶段。

**对数据库的依赖**：
- 需要连接数据库查询表结构和索引信息
- 数据库连接信息来自配置 `db.dsn`

---

## 8. 常见问题

### Q: 扫描不到 XML 文件？
**A**: 检查 `mapper_globs` 路径是否正确，确认文件是否存在

### Q: SQL 参数解析不对？
**A**: 检查 `parser.py` 中的参数正则表达式

### Q: dynamicFeatures 检测不对？
**A**: 检查 `parser.py` 中的动态标签检测逻辑
