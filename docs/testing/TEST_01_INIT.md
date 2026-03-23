# TEST_01: Init 阶段测试

## 阶段概述

**Init 阶段**是 V9 流水线的第一个阶段，负责：
1. 连接数据库验证可达性
2. 扫描 MyBatis XML mapper 文件
3. 解析并提取 SQL 单元（SqlUnit）
4. 生成初始的 SQL 单元列表

**输入：** `sqlopt.yml` 配置文件
**输出：** `runs/<run_id>/init/sql_units.json`

---

## 测试目标

| 目标 | 说明 |
|------|------|
| XML 解析 | 正确解析 UserMapper.xml, OrderMapper.xml, CommonMapper.xml |
| SQL 提取 | 提取所有 SELECT/INSERT/UPDATE/DELETE 语句 |
| 片段解析 | 正确解析 `<sql>` 片段定义 |
| 跨文件引用 | 正确解析 `<include refid="">` 跨文件引用 |
| 契约验证 | 输出符合 `sqlunit.schema.json` |

---

## 测试前置条件

### 1. 数据库配置

```yaml
db:
  platform: postgresql
  dsn: postgresql://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable

scan:
  mapper_globs:
    - src/main/resources/mapper/*.xml
  statement_types:
    - SELECT
```

> **说明：** `statement_types` 默认仅扫描 SELECT 语句。这可以减少 INSERT/UPDATE/DELETE 语句的干扰，因为这些语句通常不涉及查询优化。如需扫描所有语句类型，可配置为 `["SELECT", "INSERT", "UPDATE", "DELETE"]`。

### 2. 测试文件路径

```
tests/real/mybatis-test/src/main/resources/mapper/
├── UserMapper.xml    (70+ SQL statements)
├── OrderMapper.xml   (5 SQL statements)
└── CommonMapper.xml  (6 SQL fragments)
```

---

## 测试用例

### TC-INIT-01: 验证配置和数据库连接

**命令：**
```bash
sqlopt-cli validate-config --config sqlopt-test.yml
```

**预期结果：**
```json
{
  "valid": true,
  "config_version": "v1",
  "db_reachable": true,
  "llm_configured": true
}
```

---

### TC-INIT-02: 运行 Init 阶段（PostgreSQL）

**命令：**
```bash
sqlopt-cli run --config sqlopt-test.yml --run-id test_init_pg --to-stage init

# 或使用 diagnose 命令（包含 init + parse）
sqlopt-cli diagnose --config sqlopt-test.yml --run-id test_init_pg
```

**预期结果：**
```json
{
  "run_id": "test_init_pg",
  "engine": "v9",
  "result": {
    "init": {
      "success": true,
      "output_files": ["runs/test_init_pg/init/sql_units.json"],
      "sql_unit_count": 75
    }
  },
  "completed": true
}
```

---

### TC-INIT-03: 检查 sql_units.json 输出

**命令：**
```bash
cat runs/test_init_pg/init/sql_units.json | jq '. | length'
```

**预期结果：**
```
75
```

---

### TC-INIT-04: 检查特定 SQL 的提取

**命令：**
```bash
cat runs/test_init_pg/init/sql_units.json | jq '.[] | select(.sqlKey == "com.test.mapper.UserMapper.testSingleIf")'
```

**预期输出：**
```json
{
  "sqlKey": "com.test.mapper.UserMapper.testSingleIf",
  "xmlPath": "tests/real/mybatis-test/src/main/resources/mapper/UserMapper.xml",
  "namespace": "com.test.mapper",
  "statementId": "testSingleIf",
  "statementType": "SELECT",
  "variantId": "v1",
  "sql": "SELECT * FROM users\n    <where>\n        <if test=\"name != null\">AND name = #{name}</if>\n    </where>",
  "parameterMappings": [
    {"name": "name", "type": "String", " jdbcType": null}
  ],
  "paramExample": {"name": "test"},
  "locators": {
    "statementId": "testSingleIf"
  },
  "riskFlags": [],
  "templateSql": "SELECT * FROM users",
  "dynamicFeatures": ["IF", "WHERE"],
  "branchCount": 2
}
```

---

### TC-INIT-05: 检查跨文件 SQL 片段引用解析

**命令：**
```bash
cat runs/test_init_pg/init/sql_units.json | jq '.[] | select(.sqlKey == "com.test.mapper.UserMapper.testCrossFileInclude")'
```

**预期输出：**
```json
{
  "sqlKey": "com.test.mapper.UserMapper.testCrossFileInclude",
  "statementType": "SELECT",
  "dynamicFeatures": ["INCLUDE"],
  "includeBindings": [
    {
      "refId": "com.test.mapper.CommonMapper.userBaseColumns",
      "sourceXml": "CommonMapper.xml"
    },
    {
      "refId": "com.test.mapper.CommonMapper.activeStatusCondition",
      "sourceXml": "CommonMapper.xml"
    }
  ]
}
```

---

### TC-INIT-06: 检查带动态条件的 SQL

**命令：**
```bash
cat runs/test_init_pg/init/sql_units.json | jq '.[] | select(.sqlKey == "com.test.mapper.UserMapper.testChooseNestedChoose")'
```

**预期输出：**
```json
{
  "sqlKey": "com.test.mapper.UserMapper.testChooseNestedChoose",
  "statementType": "SELECT",
  "dynamicFeatures": ["IF", "CHOOSE", "WHERE"],
  "branchCount": 6
}
```

---

### TC-INIT-07: 检查 SQL 片段（sql fragment）定义

**命令：**
```bash
cat runs/test_init_pg/init/sql_units.json | jq '.[] | select(.statementType == "FRAGMENT")'
```

**预期结果：** 包含 CommonMapper.xml 中定义的 6 个 SQL 片段

---

## Init 阶段产物结构

```
runs/<run_id>/init/
└── sql_units.json
```

### sqlunit.schema.json 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `sqlKey` | string | 唯一标识：`namespace.statementId` |
| `xmlPath` | string | XML 文件路径 |
| `namespace` | string | MyBatis namespace |
| `statementId` | string | SQL 语句 ID |
| `statementType` | string | SELECT/INSERT/UPDATE/DELETE/FRAGMENT |
| `sql` | string | 原始 SQL 内容（含动态标签） |
| `parameterMappings` | array | 参数映射 |
| `paramExample` | object | 示例参数 |
| `riskFlags` | array | 风险标记 |
| `templateSql` | string | 模板 SQL（静态部分） |
| `dynamicFeatures` | array | 动态特征：`["IF", "WHERE", "CHOOSE", "INCLUDE"]` |
| `branchCount` | integer | 预估分支数 |

---

## 风险标记说明

Init 阶段会对 SQL 进行初步风险检测：

| 风险标记 | 说明 | 严重程度 |
|----------|------|----------|
| `DOLLAR_SUBSTITUTION` | 使用 `${}` 而非 `#{}` | 高 |
| `LEADING_WILDCARD` | 前缀通配符如 `'%' + value` | 高 |
| `PREFIX_WILDCARD` | LIKE 前缀匹配 | 中 |
| `POTENTIAL_SQL_INJECTION` | 可能的 SQL 注入 | 高 |

---

## 测试场景 SQL 清单

以下 SQL 在 UserMapper.xml 中定义，应在 Init 阶段被正确提取：

### 基础场景 (1-10)

| sqlKey | statementType | dynamicFeatures | 预期分支数 |
|--------|---------------|----------------|------------|
| testSingleIf | SELECT | IF | 2 |
| testTwoIf | SELECT | IF, IF | 4 |
| testThreeIf | SELECT | IF, IF, IF | 8 |
| testFourIf | SELECT | IF, IF, IF, IF | 16 |
| testChooseWhen | SELECT | CHOOSE | 2 |
| testChooseOtherwise | SELECT | CHOOSE | 3 |
| testWhereIf | SELECT | IF, WHERE | 2 |
| testSetIf | UPDATE | IF, SET | 2 |
| testForeachIn | SELECT | FOREACH | 1 |
| testTrim | SELECT | TRIM | 2 |

### 组合场景 (11-20)

| sqlKey | statementType | dynamicFeatures | 预期分支数 |
|--------|---------------|----------------|------------|
| testIfChoose | SELECT | IF, CHOOSE | 4-6 |
| testWhereMultipleIf | SELECT | IF × 4 | 16 |
| testChooseMultipleIf | SELECT | CHOOSE, IF | 5-7 |
| testIfForeach | SELECT | IF, FOREACH | 4 |
| testWhereChooseWhen | SELECT | CHOOSE | 4-6 |
| testChooseWithMultipleIf | SELECT | CHOOSE, IF | 5-7 |

### 高级场景 (21+)

| sqlKey | statementType | dynamicFeatures | 预期分支数 |
|--------|---------------|----------------|------------|
| testFiveIf | SELECT | IF × 5 | 32 |
| testChooseNestedChoose | SELECT | CHOOSE嵌套 | 7-9 |
| testComplexConditions | SELECT | IF, CHOOSE | 8-12 |
| testDynamicOrderBy | SELECT | IF | 2 |
| testBindIf | SELECT | IF, BIND | 4 |

---

## 常见问题排查

### 问题 1: SQL 未被提取

**症状：** 预期的 SQL 未出现在 sql_units.json 中

**排查：**
1. 检查 XML 文件是否在 `mapper_globs` 范围内
2. 检查 `<select>`/`<insert>`/`<update>`/`<delete>` 标签是否正确闭合
3. 检查 namespace 和 statementId 是否唯一

### 问题 2: 参数映射错误

**症状：** parameterMappings 为空或不正确

**排查：**
1. 检查 `#{}` 和 `${}` 语法是否正确
2. 确认参数名与测试数据匹配

### 问题 3: 分支数计算错误

**症状：** branchCount 与预期不符

**排查：**
1. 检查动态标签是否被正确识别
2. 确认嵌套结构的分支计算逻辑

---

## 后续测试

Init 阶段完成后，产物将作为 **Parse 阶段** 的输入。继续：

- [TEST_02_PARSE.md](TEST_02_PARSE.md) - Parse 阶段测试
