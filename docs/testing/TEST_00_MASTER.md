# V9 五阶段集成测试指南

## 概述

本文档描述如何使用真实数据库和 LLM 对 SQL Optimizer V9 架构的五阶段流水线进行完整的集成测试。

**V9 五阶段流水线：**
```
init → parse → recognition → optimize → patch
```

**测试目标：**
- 验证每个阶段的输入/输出契约正确性
- 使用真实的 MyBatis XML 文件进行测试
- 使用真实数据库（PostgreSQL/MySQL）验证 EXPLAIN 和优化建议
- 使用 LLM 生成和验证优化建议

---

## 测试环境准备

### 1. 测试数据库配置

#### PostgreSQL

```yaml
db:
  platform: postgresql
  dsn: postgresql://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable
```

**测试数据库准备：**
```sql
-- 创建测试用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(255),
    status VARCHAR(20),
    type VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 创建测试订单表
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(50),
    user_id INTEGER REFERENCES users(id),
    status VARCHAR(20),
    amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引（用于测试索引建议）
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_name ON users(name);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
```

#### MySQL

```yaml
db:
  platform: mysql
  dsn: mysql://root:root@127.0.0.1:3306/sqlopt_test
```

**测试数据库准备：**
```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(255),
    status VARCHAR(20),
    type VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_name (name),
    INDEX idx_status (status)
);

CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_no VARCHAR(50),
    user_id INT,
    status VARCHAR(20),
    amount DECIMAL(10, 2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 2. LLM 配置

```yaml
llm:
  enabled: true
  provider: opencode_run        # 使用 OpenCode 运行
  timeout_ms: 80000

# 或使用 OpenAI 兼容接口
# llm:
#   enabled: true
#   provider: direct_openai_compatible
#   api_base: https://api.openai.com/v1
#   api_key: sk-xxxx
#   api_model: gpt-4o-mini
#   api_timeout_ms: 30000
```

### 3. 测试配置文件

在项目根目录创建 `sqlopt-test.yml`：

```yaml
config_version: v1

project:
  root_path: tests/real/mybatis-test

scan:
  mapper_globs:
    - src/main/resources/mapper/*.xml
  statement_types:              # 要扫描的语句类型 (默认仅 SELECT)
    - SELECT                    # 可选: SELECT, INSERT, UPDATE, DELETE

db:
  platform: postgresql
  dsn: postgresql://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable

validate:
  db_reachable: true
  validation_profile: balanced
  allow_db_unreachable_fallback: false

runtime:
  profile: balanced

llm:
  enabled: true
  provider: opencode_run
  timeout_ms: 80000
```

---

## 测试的 MyBatis XML 文件

项目使用 `tests/real/mybatis-test/` 中的真实 MyBatis XML 文件：

### XML 文件清单

| 文件 | SQL 数量 | 主要场景 |
|------|----------|----------|
| `UserMapper.xml` | 70+ | 用户 CRUD、动态条件、多表关联 |
| `OrderMapper.xml` | 5 | 订单查询、跨文件引用 |
| `CommonMapper.xml` | 6 | 公共 SQL 片段定义 |

### 关键测试 SQL 场景

#### 场景 1: 基础 if 条件 (UserMapper.xml)

```xml
<select id="testSingleIf" resultType="User">
    SELECT * FROM users
    <where>
        <if test="name != null">AND name = #{name}</if>
    </where>
</select>
```

#### 场景 2: 前缀通配符 (性能问题)

```xml
<select id="testWhereMultipleIf" resultType="User">
    SELECT id, name, email, status, type, created_at
    FROM users
    <where>
        <if test="name != null">AND name LIKE CONCAT('%', #{name}, '%')</if>
        <if test="email != null">AND email LIKE CONCAT('%', #{email}, '%')</if>
        ...
    </where>
    LIMIT 1000
</select>
```

#### 场景 3: 跨文件 SQL 片段引用

```xml
<select id="testCrossFileInclude" resultType="User">
    SELECT <include refid="com.test.mapper.CommonMapper.userBaseColumns"/>
    FROM users
    <where>
        <include refid="com.test.mapper.CommonMapper.activeStatusCondition"/>
    </where>
</select>
```

#### 场景 4: 嵌套 choose/if 复杂条件

```xml
<select id="testChooseNestedChoose" resultType="User">
    SELECT * FROM users
    <where>
        <choose>
            <when test="status != null and status == '1'">
                <choose>
                    <when test="type == 'VIP'">AND status = '1' AND type = 'VIP'</when>
                    <when test="type == 'NORMAL'">AND status = '1' AND type = 'NORMAL'</when>
                    <otherwise>AND status = '1'</otherwise>
                </choose>
            </when>
            <otherwise>AND status IN ('1', '2')</otherwise>
        </choose>
    </where>
</select>
```

#### 场景 5: foreach 批量查询

```xml
<select id="testForeachIn" resultType="User">
    SELECT * FROM users WHERE id IN
    <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</select>
```

---

## CLI 命令参考

### 完整流程运行

```bash
# 验证配置
sqlopt-cli validate-config --config sqlopt-test.yml

# 完整流程 (init → parse → recognition → optimize → patch)
sqlopt-cli run --config sqlopt-test.yml

# 指定 run_id
sqlopt-cli run --config sqlopt-test.yml --run-id test_run_001

# 仅运行到某个阶段
sqlopt-cli run --config sqlopt-test.yml --to-stage recognition

# 诊断模式 (init + parse)
sqlopt-cli diagnose --config sqlopt-test.yml
```

### 单 SQL 执行

```bash
# 仅执行指定 SQL
sqlopt-cli run --config sqlopt-test.yml --sql-key testSingleIf
sqlopt-cli run --config sqlopt-test.yml --sql-key testWhereMultipleIf
```

### 状态查看与恢复

```bash
# 查看状态
sqlopt-cli status --run-id test_run_001

# 恢复中断的运行
sqlopt-cli resume --run-id test_run_001

# 查看验证结果
sqlopt-cli verify --run-id test_run_001 --sql-key testSingleIf

# 应用补丁
sqlopt-cli apply --run-id test_run_001
```

---

## 阶段产物目录结构

每个 run 完成后，在 `runs/<run_id>/` 下生成以下产物：

```
runs/<run_id>/
├── config.resolved.json        # 解析后的配置
├── state.json                  # 运行状态
├── manifest.jsonl              # 运行清单
│
├── init/
│   └── sql_units.json          # 提取的 SQL 单元列表
│
├── parse/
│   ├── sql_units_with_branches.json   # 带分支的 SQL 单元
│   └── risks.json             # 风险检测结果
│
├── recognition/
│   └── baselines.json          # 性能基线 (EXPLAIN 结果)
│
├── optimize/
│   └── proposals.json         # 优化建议
│
├── patch/
│   ├── patches.json           # 补丁清单
│   └── patches/               # 补丁文件目录
│
├── supervisor/
│   └── (状态快照)
│
├── report.json                # JSON 格式报告
├── report.md                  # Markdown 格式报告
└── report.summary.md          # 摘要报告
```

---

## 数据契约

### Init 阶段输出: sqlunit.schema.json

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
    {"name": "name", "type": "String"}
  ],
  "paramExample": {"name": "test"},
  "locators": {"statementId": "testSingleIf"},
  "riskFlags": [],
  "templateSql": "SELECT * FROM users WHERE name = #{name}",
  "dynamicFeatures": ["IF", "WHERE"],
  "branchCount": 2
}
```

### Parse 阶段输出: sql_units_with_branches.json

```json
{
  "sqlKey": "com.test.mapper.UserMapper.testSingleIf",
  "branches": [
    {
      "id": 0,
      "conditions": ["name = null"],
      "sql": "SELECT * FROM users",
      "type": "static"
    },
    {
      "id": 1,
      "conditions": ["name != null"],
      "sql": "SELECT * FROM users WHERE name = #{name}",
      "type": "conditional"
    }
  ],
  "branchCount": 2
}
```

### Recognition 阶段输出: baselines.json

```json
{
  "sql_key": "com.test.mapper.UserMapper.testSingleIf#b1",
  "execution_time_ms": 12.5,
  "rows_scanned": 1000,
  "rows_returned": 1,
  "execution_plan": {
    "node_type": "Index Scan",
    "index_used": "idx_name",
    "cost": 5.2
  },
  "database_platform": "postgresql",
  "sample_params": {"name": "test"}
}
```

### Optimize 阶段输出: proposals.json

```json
{
  "sqlKey": "com.test.mapper.UserMapper.testSingleIf",
  "issues": ["PREFIX_WILDCARD"],
  "suggestions": [
    {
      "type": "INDEX_HINT",
      "originalSql": "SELECT * FROM users WHERE name LIKE '%' || #{name} || '%'",
      "suggestedSql": "SELECT * FROM users WHERE name LIKE #{name} || '%'",
      "rationale": "Remove leading wildcard to enable index usage"
    }
  ],
  "verdict": "ACTIONABLE",
  "estimatedBenefit": "HIGH",
  "confidence": "HIGH"
}
```

---

## 测试文档索引

| 文档 | 内容 |
|------|------|
| `docs/testing/TEST_01_INIT.md` | Init 阶段测试详解 |
| `docs/testing/TEST_02_PARSE.md` | Parse 阶段测试详解 |
| `docs/testing/TEST_03_RECOGNITION.md` | Recognition 阶段测试详解 |
| `docs/testing/TEST_04_OPTIMIZE.md` | Optimize 阶段测试详解 |
| `docs/testing/TEST_05_PATCH.md` | Patch 阶段测试详解 |

---

## 快速开始

### 1. 准备测试环境

```bash
# 启动 PostgreSQL (Docker)
docker run -d \
  --name sqlopt-pg \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=postgres \
  -p 5432:5432 \
  postgres:15

# 等待启动完成
sleep 5

# 创建测试表
docker exec -i sqlopt-pg psql -U postgres -d postgres < tests/real/mybatis-test/schema.sql
```

### 2. 创建测试配置

```bash
cp sqlopt.yml sqlopt-test.yml
# 编辑 sqlopt-test.yml，修改 db.dsn 为实际连接串
```

### 3. 运行完整测试

```bash
# 验证配置
sqlopt-cli validate-config --config sqlopt-test.yml

# 完整流程
sqlopt-cli run --config sqlopt-test.yml --run-id test_v9_full

# 查看结果
sqlopt-cli status --run-id test_v9_full
```

### 4. 查看产物

```bash
# 查看生成的 SQL 单元
cat runs/test_v9_full/init/sql_units.json | jq '.[] | .sqlKey'

# 查看识别的分支
cat runs/test_v9_full/parse/sql_units_with_branches.json | jq '.[].branchCount'

# 查看性能基线
cat runs/test_v9_full/recognition/baselines.json | jq '.'

# 查看优化建议
cat runs/test_v9_full/optimize/proposals.json | jq '.'
```

---

## 常见问题

### Q: 数据库连接失败

```
Error: connection refused
```

**解决：**
1. 确认数据库正在运行：`docker ps | grep postgres`
2. 检查连接串是否正确
3. 确认防火墙设置

### Q: LLM 超时

```
Error: LLM request timeout after 80000ms
```

**解决：**
1. 检查网络连接
2. 增加 `llm.timeout_ms` 配置
3. 减少测试 SQL 数量

### Q: XML 文件解析失败

```
Error: Failed to parse XML mapper
```

**解决：**
1. 确认 XML 文件格式正确
2. 检查 namespace 和 statementId 唯一性
3. 查看 `runs/<run_id>/manifest.jsonl` 获取详细错误

---

## 后续改进指南

本文档作为指导文件，供后续改进代码使用：

1. **阶段实现修改**：修改某个阶段后，对应测试文档应首先运行验证
2. **新功能添加**：新功能应先通过对应阶段测试验证正确性
3. **回归测试**：每次代码变更后，运行 `pytest tests/integration/` 确保无回归
4. **性能基准**：记录每次运行的 performance metrics，用于对比优化效果
