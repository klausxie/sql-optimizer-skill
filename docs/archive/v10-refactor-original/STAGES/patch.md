# Patch 阶段设计文档

> **版本**: v1.0  
> **状态**: 设计中  
> **最后更新**: 2026-03-24

---

## 1. 背景与问题

### 1.1 现有架构的问题

在当前的 V9 架构中，Optimize 阶段输出完整的 SQL 字符串，Result 阶段使用朴素的分行 diff 来生成补丁。这种方式在简单场景下可以工作，但存在根本性缺陷：

```
当前流程（有问题）:
Optimize → "SELECT * FROM users WHERE name LIKE '%' || #{name}"  (完整 SQL 字符串)
Result → 逐行 diff → 匹配失败 → 补丁错误
```

**核心问题**:

| 问题 | 描述 | 影响 |
|------|------|------|
| **大片段修改无法匹配** | 当 Optimize 重写了整个 SQL片段时，逐行 diff 无法找到对应位置 | 补丁无法应用 |
| **语义丢失** | diff 只知道字符层面变化，不知道原始 SQL 和新 SQL 的语义对应关系 | 修复困难 |
| **无法处理结构变化** | LIKE '%x%' → BETWEEN 'a' AND 'z' 是语义级变化，不是行级变化 | 此类优化无法应用 |
| **多分支情况复杂** | 一个 SQL 单元可能有多个条件分支，diff 无法处理 | 遗漏或错误应用 |

### 1.2 为什么需要结构化动作

要实现精确的 XML 补丁，我们需要从"输出最终 SQL"转变为"记录发生了什么变化"：

```
理想流程:
Optimize → [动作列表: REPLACE {xpath, original, rewritten}]
Result → 根据动作列表精确修改 XML
```

**关键洞察**: 我们不关心最终 SQL 是什么，我们关心**原始 XML 中的什么内容被改成了什么**。

---

## 2. 设计目标

### 2.1 功能目标

1. **精确追踪变化**: 记录每个优化的 operation_type、xpath、original_snippet、rewritten_snippet
2. **支持多种操作类型**: REPLACE、ADD、REMOVE、WRAP 四种基本操作
3. **语义验证**: 通过比较结果集（而非执行计划）验证优化正确性
4. **可追溯性**: 每个动作都可以追溯到原始问题和优化原因

### 2.2 非功能目标

1. **可测试**: 动作列表可以被独立验证，不依赖数据库
2. **可逆性**: 动作列表可以被回滚
3. **可读性**: 结构化输出人类可读，便于调试和审核

---

## 3. 方案概述

### 3.1 核心思想

**Tracking WHAT changed, not just the final SQL**

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Optimize 阶段                                  │
│                                                                      │
│   输入: 原始 SQL + 执行计划                                          │
│          ↓                                                           │
│   优化引擎: 基于规则 + LLM 生成优化建议                              │
│          ↓                                                           │
│   语义验证: 执行优化后 SQL，对比结果集                               │
│          ↓                                                           │
│   输出: 结构化动作列表 (不是完整 SQL 字符串)                          │
└──────────────────────────────────────────────────────────────────────┘
                                 ↓
┌──────────────────────────────────────────────────────────────────────┐
│                        Result 阶段                                   │
│                                                                      │
│   输入: 动作列表 + 原始 XML                                          │
│          ↓                                                           │
│   Patch 引擎: 根据动作类型执行对应修改                                │
│          ↓                                                           │
│   输出: 应用后的 XML + 验证报告                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 四种操作类型

| 操作类型 | 描述 | 典型场景 |
|----------|------|----------|
| **REPLACE** | 替换现有元素 | `LIKE '%x%'` → `LIKE 'x%'` |
| **ADD** | 添加新元素 | 添加 WHERE 条件、添加 SELECT 列 |
| **REMOVE** | 删除元素 | 删除不必要的 ORDER BY、删除冗余 JOIN |
| **WRAP** | 包裹现有元素 | 为子查询添加 LIMIT、包裹条件 |

---

## 4. 数据结构

### 4.1 核心数据结构

#### 4.1.1 PatchAction (核心动作单元)

```json
{
  "actionId": "act_001",
  "operationType": "REPLACE",
  "xpath": "/mapper/select[@id='search']/where/condition[1]/expr",
  "originalSnippet": "LIKE '%' || #{name}",
  "rewrittenSnippet": "LIKE #{name} || '%'",
  "context": {
    "parentXpath": "/mapper/select[@id='search']/where",
    "sqlKey": "com.example.UserMapper.search:branch:0",
    "statementType": "select"
  },
  "metadata": {
    "issue": "PREFIX_WILDCARD",
    "confidence": "HIGH",
    "rationale": "Prefix wildcard prevents index usage"
  }
}
```

#### 4.1.2 ActionSequence (动作序列)

```json
{
  "sequenceId": "seq_001",
  "proposalId": "prop_001",
  "sqlKey": "com.example.UserMapper.search:branch:0",
  "actions": [
    {
      "actionId": "act_001",
      "operationType": "REPLACE",
      "xpath": "/mapper/select[@id='search']/where/condition[1]/expr",
      "originalSnippet": "LIKE '%' || #{name}",
      "rewrittenSnippet": "LIKE #{name} || '%'",
      "context": {...},
      "metadata": {...}
    },
    {
      "actionId": "act_002", 
      "operationType": "ADD",
      "xpath": "/mapper/select[@id='search']/where/condition[2]",
      "originalSnippet": null,
      "rewrittenSnippet": "AND status = 1",
      "context": {...},
      "metadata": {...}
    }
  ],
  "semanticVerification": {
    "verified": true,
    "method": "RESULT_SET_COMPARISON",
    "testQueries": [...],
    "comparableColumns": ["id", "name", "email"],
    "rowCountMatch": true,
    "sampleMatchRate": 1.0
  }
}
```

#### 4.1.3 OptimizationProposal (完整提案)

```json
{
  "proposalId": "prop_001",
  "sqlKey": "com.example.UserMapper.search:branch:0",
  "mapperNamespace": "com.example.UserMapper",
  "baseline": {
    "sql": "SELECT * FROM users WHERE name LIKE '%' || #{name}",
    "executionPlan": {...},
    "executionTimeMs": 150.5,
    "rowsScanned": 1520347,
    "rowsReturned": 100
  },
  "actionSequence": {
    "sequenceId": "seq_001",
    "actions": [...]
  },
  "rewrittenSql": "SELECT id, name, email FROM users WHERE name LIKE #{name} || '%' AND status = 1",
  "improvement": {
    "speedupRatio": 29.0,
    "executionTimeReduction": "145.3ms (96.5% faster)",
    "rowsScannedReduction": "99.99%"
  },
  "semanticVerification": {
    "verified": true,
    "method": "RESULT_SET_COMPARISON",
    "verificationDetails": {...}
  },
  "issues": ["PREFIX_WILDCARD", "MISSING_INDEX"],
  "verdict": "ACTIONABLE",
  "confidence": "HIGH",
  "canPatch": true
}
```

### 4.2 字段说明

#### 4.2.1 PatchAction 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `actionId` | string | ✅ | 唯一动作 ID，格式: `act_{uuid}` |
| `operationType` | enum | ✅ | 操作类型: `REPLACE`, `ADD`, `REMOVE`, `WRAP` |
| `xpath` | string | ✅ | 目标元素的 XPath 路径 |
| `originalSnippet` | string | ❌ | 原始片段 (REPLACE/REMOVE/WRAP 必填) |
| `rewrittenSnippet` | string | ❌ | 重写后片段 (REPLACE/ADD/WRAP 必填) |
| `context` | object | ✅ | 上下文信息 |
| `context.parentXpath` | string | ✅ | 父元素 XPath |
| `context.sqlKey` | string | ✅ | SQL 单元唯一标识 |
| `context.statementType` | string | ✅ | 语句类型: select/insert/update/delete |
| `metadata` | object | ✅ | 元数据 |
| `metadata.issue` | string | ✅ | 检测到的问题类型 |
| `metadata.confidence` | string | ✅ | 置信度: HIGH/MEDIUM/LOW |
| `metadata.rationale` | string | ❌ | 优化理由 |

#### 4.2.2 SemanticVerification 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `verified` | boolean | 是否通过验证 |
| `method` | enum | 验证方法: `RESULT_SET_COMPARISON`, `EXECUTION_PLAN_COMPARISON`, `SEMANTIC_EQUIVALENCE_CHECK` |
| `testQueries` | array | 用于验证的测试查询 |
| `comparableColumns` | array | 结果集可比较的列 |
| `rowCountMatch` | boolean | 行数是否匹配 |
| `sampleMatchRate` | float | 样本匹配率 (0.0-1.0) |
| `verificationDetails` | object | 详细验证信息 |

---

## 5. 操作类型详解

### 5.1 REPLACE (替换)

**语义**: 替换现有元素的内容或结构

**条件**: 
- `originalSnippet` 必须存在
- `rewrittenSnippet` 必须存在
- 目标位置必须存在 `originalSnippet`

**示例**:

```xml
<!-- 原始 XML -->
<select id="search">
  SELECT * FROM users WHERE name LIKE '%' || #{name}
</select>

<!-- 动作 -->
{
  "operationType": "REPLACE",
  "xpath": "/mapper/select[@id='search']/where/condition[1]/expr",
  "originalSnippet": "LIKE '%' || #{name}",
  "rewrittenSnippet": "LIKE #{name} || '%'"
}

<!-- 优化后 XML -->
<select id="search">
  SELECT * FROM users WHERE name LIKE #{name} || '%'
</select>
```

**另一个示例 - 整个 WHERE 子句替换**:

```xml
<!-- 原始 XML -->
<select id="findActiveOrders">
  SELECT * FROM orders WHERE status = 1 AND active = true
</select>

<!-- 动作 -->
{
  "operationType": "REPLACE", 
  "xpath": "/mapper/select[@id='findActiveOrders']/where",
  "originalSnippet": "WHERE status = 1 AND active = true",
  "rewrittenSnippet": "WHERE status = 1"
}

<!-- 优化后 XML -->
<select id="findActiveOrders">
  SELECT * FROM orders WHERE status = 1
</select>
```

### 5.2 ADD (添加)

**语义**: 在指定位置添加新元素

**条件**:
- `originalSnippet` 必须为 null
- `rewrittenSnippet` 必须存在
- 目标位置必须存在父元素

**示例**:

```xml
<!-- 原始 XML -->
<select id="search">
  SELECT * FROM users WHERE name LIKE #{name} || '%'
</select>

<!-- 动作 -->
{
  "operationType": "ADD",
  "xpath": "/mapper/select[@id='search']/where",
  "originalSnippet": null,
  "rewrittenSnippet": "AND status = 1"
}

<!-- 优化后 XML -->
<select id="search">
  SELECT * FROM users WHERE name LIKE #{name} || '%' AND status = 1
</select>
```

**在特定条件后添加**:

```xml
<!-- 原始 XML -->
<select id="search">
  <where>
    <condition expr="name LIKE #{name} || '%'"/>
  </where>
</select>

<!-- 动作 -->
{
  "operationType": "ADD",
  "xpath": "/mapper/select[@id='search']/where/condition[1]",
  "originalSnippet": null,
  "rewrittenSnippet": "<condition expr=\"status = 1\"/>"
}

<!-- 优化后 XML -->
<select id="search">
  <where>
    <condition expr="name LIKE #{name} || '%'"/>
    <condition expr="status = 1"/>
  </where>
</select>
```

### 5.3 REMOVE (删除)

**语义**: 删除指定元素

**条件**:
- `originalSnippet` 必须存在
- `rewrittenSnippet` 必须为 null
- 目标位置必须存在

**示例**:

```xml
<!-- 原始 XML -->
<select id="search">
  SELECT * FROM users WHERE name LIKE #{name} || '%' ORDER BY created_at DESC
</select>

<!-- 动作 -->
{
  "operationType": "REMOVE",
  "xpath": "/mapper/select[@id='search']/orderby",
  "originalSnippet": "ORDER BY created_at DESC",
  "rewrittenSnippet": null
}

<!-- 优化后 XML -->
<select id="search">
  SELECT * FROM users WHERE name LIKE #{name} || '%'
</select>
```

**删除 SELECT 中的冗余列**:

```xml
<!-- 原始 XML -->
<select id="search">
  SELECT id, name, email, created_at, updated_at FROM users
</select>

<!-- 动作 -->
{
  "operationType": "REMOVE",
  "xpath": "/mapper/select[@id='search']/column-list/column[3]",
  "originalSnippet": "email",
  "rewrittenSnippet": null
}

<!-- 优化后 XML -->
<select id="search">
  SELECT id, name, created_at, updated_at FROM users
</select>
```

### 5.4 WRAP (包裹)

**语义**: 用新元素包裹现有元素

**条件**:
- `originalSnippet` 必须存在
- `rewrittenSnippet` 必须存在（包含原内容的占位符）
- 使用 `{CONTENT}` 占位原内容

**示例**:

```xml
<!-- 原始 XML -->
<select id="search">
  SELECT * FROM users WHERE name = #{name}
</select>

<!-- 动作: 包裹 WHERE 条件，添加子查询 -->
{
  "operationType": "WRAP",
  "xpath": "/mapper/select[@id='search']/where",
  "originalSnippet": "WHERE name = #{name}",
  "rewrittenSnippet": "WHERE name IN (SELECT name FROM users WHERE {CONTENT})"
}

<!-- 优化后 XML -->
<select id="search">
  WHERE name IN (SELECT name FROM users WHERE name = #{name})
</select>
```

**另一个示例 - 添加 LIMIT**:

```xml
<!-- 原始 XML -->
<select id="search">
  SELECT * FROM users WHERE status = 1
</select>

<!-- 动作 -->
{
  "operationType": "WRAP",
  "xpath": "/mapper/select[@id='search']",
  "originalSnippet": "<select id=\"search\">\n  SELECT * FROM users WHERE status = 1\n</select>",
  "rewrittenSnippet": "<select id=\"search\">\n  SELECT * FROM users WHERE status = 1\n</select>\n<select id=\"search\">\n  SELECT * FROM (SELECT * FROM users WHERE status = 1) AS t LIMIT 100\n</select>"
}
```

---

## 6. 处理流程

### 6.1 Optimize 阶段 - 动作生成

```
┌─────────────────────────────────────────────────────────────────┐
│                     Optimize 阶段处理流程                        │
└─────────────────────────────────────────────────────────────────┘

输入:
  - baselines.json (执行计划)
  - sql_units.json (SQL 单元)
  - table_schemas.json (表结构)

                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. 问题检测                                                     │
│    - 解析执行计划，检测问题 (PREFIX_WILDCARD, FULL_TABLE_SCAN)  │
│    - 识别可优化点                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. 优化候选生成                                                  │
│    - 规则引擎应用                                                │
│    - LLM 生成优化建议                                           │
│    - 生成候选 rewritten_sql                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. 语义验证 (关键步骤)                                          │
│    - 执行 baseline_sql                                           │
│    - 执行 rewritten_sql                                          │
│    - 比较结果集 (RESULT_SET_COMPARISON)                         │
│    - 验证语义等价性                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. 动作序列生成 (核心创新点)                                     │
│    - 比较 original_snippet 和 rewritten_snippet                  │
│    - 生成结构化动作 (REPLACE/ADD/REMOVE/WRAP)                   │
│    - 记录 xpath 和 context                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. 输出 proposals.json                                           │
│    - actionSequence 替代原来的完整 rewritten_sql                  │
│    - 包含 semanticVerification 结果                              │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Result 阶段 - 动作应用

```
┌─────────────────────────────────────────────────────────────────┐
│                     Result 阶段处理流程                          │
└─────────────────────────────────────────────────────────────────┘

输入:
  - optimize/proposals.json (动作序列)
  - parse/xml_mappings.json (XML 位置映射)
  - 原始 XML 文件

                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. 解析动作序列                                                  │
│    - 读取每个 proposal 的 actionSequence                         │
│    - 验证动作完整性                                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. 定位 XML 元素                                                 │
│    - 根据 xpath 定位目标元素                                     │
│    - 验证 originalSnippet 匹配                                   │
│    - 处理多分支情况 (branch selection)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. 应用动作                                                      │
│    - REPLACE: 替换内容                                          │
│    - ADD: 插入新内容                                             │
│    - REMOVE: 删除元素                                            │
│    - WRAP: 包裹元素                                              │
│    - 生成补丁文件 (*.patch)                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. 验证应用结果                                                  │
│    - XML 语法验证                                                │
│    - 语义验证 (可选: 重新执行比较)                               │
│    - 生成应用报告                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. 输出 result/patches.json                                      │
│    - patchFiles: 补丁文件列表                                   │
│    - diffSummary: 变化摘要                                       │
│    - status: ready/applied/failed                                │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 分支处理流程

当 SQL 单元有多个分支时，Patch 阶段需要特殊处理：

```python
def process_branches(sql_unit, action_sequence):
    """处理多分支 SQL 单元"""
    
    # 1. 获取所有分支
    branches = sql_unit.branches
    
    # 2. 确定目标分支
    target_branch = select_branch_for_patch(action_sequence, branches)
    
    # 3. 提取目标分支的 XPath
    branch_xpath = get_branch_xpath(target_branch)
    
    # 4. 调整动作的 xpath (添加分支前缀)
    adjusted_actions = adjust_xpaths_for_branch(action_sequence, branch_xpath)
    
    # 5. 应用动作到目标分支
    apply_actions(adjusted_actions)
    
    # 6. 复制结果到其他相关分支 (可选)
    if should_propagate(action_sequence):
        propagate_to_related_branches(target_branch, branches)
```

---

## 7. 语义验证

### 7.1 验证方法对比

| 方法 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| **RESULT_SET_COMPARISON** | 执行两个 SQL，比较结果集 | 准确反映语义 | 需要数据库 |
| **EXECUTION_PLAN_COMPARISON** | 比较执行计划 | 快速 | 不保证语义等价 |
| **SEMANTIC_EQUIVALENCE_CHECK** | 静态分析 SQL 结构 | 无需数据库 | 难以处理复杂 SQL |

### 7.2 RESULT_SET_COMPARISON 详解

**核心思想**: 语义等价 = 结果集等价

**执行流程**:

```
1. 准备测试数据
   - 使用原始 SQL 的参数值
   - 或使用 mock 数据
   
2. 执行原始 SQL
   - result_set_original = execute(baseline_sql, params)
   - 记录: rows, columns, sample_data
   
3. 执行优化后 SQL  
   - result_set_rewritten = execute(rewritten_sql, params)
   - 记录: rows, columns, sample_data
   
4. 比较结果集
   - row_count_match = (result_set_original.rows == result_set_rewritten.rows)
   - column_match = compare_columns(result_set_original, result_set_rewritten)
   - data_match = compare_data(result_set_original, result_set_rewritten, tolerance)
   
5. 生成验证报告
   - verified = row_count_match AND column_match AND data_match
   - sample_match_rate = 计算匹配率
```

### 7.3 验证阈值

```python
# 验证阈值配置
VERIFICATION_THRESHOLDS = {
    "row_count_tolerance": 0,           # 行数必须完全匹配
    "column_match_required": True,      # 列名必须匹配
    "data_tolerance": 1e-6,            # 数值类型容差
    "string_ignore_case": False,        # 字符串是否忽略大小写
    "null_handling": "strict",          # null 处理模式: strict/safe
    "order_matters": False,             # 结果顺序是否重要
    "sample_size": 1000,                # 抽样大小 (大表)
    "sample_match_rate_threshold": 1.0  # 抽样匹配率阈值
}
```

### 7.4 验证失败处理

```python
@dataclass
class VerificationResult:
    verified: bool
    method: str
    row_count_match: bool
    column_match: bool
    data_match: bool
    sample_match_rate: float
    failure_reason: Optional[str]
    test_query: str

def handle_verification_failure(result: VerificationResult) -> None:
    """处理验证失败"""
    
    if not result.row_count_match:
        log_warning(f"Row count mismatch: {result.failure_reason}")
        
    if not result.data_match:
        log_warning(f"Data mismatch: sample match rate = {result.sample_match_rate}")
        
    if result.sample_match_rate < 0.95:
        # 低于阈值，不允许 patch
        mark_proposal_not_patchable(result)
    else:
        # 接近阈值，标记为需要人工审核
        mark_proposal_needs_review(result)
```

---

## 8. 输出格式

### 8.1 Optimize 阶段输出

**文件**: `optimize/proposals.json`

```json
[
  {
    "proposalId": "prop_001",
    "sqlKey": "com.example.UserMapper.search:branch:0",
    "mapperNamespace": "com.example.UserMapper",
    "baseline": {
      "sql": "SELECT * FROM users WHERE name LIKE '%' || #{name}",
      "executionPlan": {...},
      "executionTimeMs": 150.5,
      "rowsScanned": 1520347,
      "rowsReturned": 100
    },
    "actionSequence": {
      "sequenceId": "seq_001",
      "proposalId": "prop_001",
      "actions": [
        {
          "actionId": "act_001",
          "operationType": "REPLACE",
          "xpath": "/mapper/select[@id='search']/where/condition[1]/expr",
          "originalSnippet": "LIKE '%' || #{name}",
          "rewrittenSnippet": "LIKE #{name} || '%'",
          "context": {
            "parentXpath": "/mapper/select[@id='search']/where",
            "sqlKey": "com.example.UserMapper.search:branch:0",
            "statementType": "select"
          },
          "metadata": {
            "issue": "PREFIX_WILDCARD",
            "confidence": "HIGH",
            "rationale": "Prefix wildcard prevents index usage"
          }
        }
      ],
      "semanticVerification": {
        "verified": true,
        "method": "RESULT_SET_COMPARISON",
        "testQueries": [
          "SELECT * FROM users WHERE name LIKE '%' || 'john'",
          "SELECT * FROM users WHERE name LIKE 'john' || '%'"
        ],
        "comparableColumns": ["id", "name", "email"],
        "rowCountMatch": true,
        "sampleMatchRate": 1.0,
        "verificationDetails": {
          "originalRows": 100,
          "rewrittenRows": 100,
          "executionTimeMs": {"original": 150.5, "rewritten": 5.2}
        }
      }
    },
    "improvement": {
      "speedupRatio": 29.0,
      "executionTimeReduction": "145.3ms (96.5% faster)",
      "rowsScannedReduction": "1,520,247 → 100 (99.99% reduction)"
    },
    "issues": ["PREFIX_WILDCARD"],
    "verdict": "ACTIONABLE",
    "confidence": "HIGH",
    "canPatch": true
  }
]
```

### 8.2 Result 阶段输出

**文件**: `result/patches.json`

```json
[
  {
    "proposalId": "prop_001",
    "sqlKey": "com.example.UserMapper.search:branch:0",
    "patchFiles": [
      "runs/20260324-143052/result/patches/UserMapper.xml.patch"
    ],
    "diffSummary": {
      "filesChanged": 1,
      "hunks": 1,
      "operations": [
        {
          "type": "REPLACE",
          "xpath": "/mapper/select[@id='search']/where/condition[1]/expr",
          "originalLength": 28,
          "rewrittenLength": 25
        }
      ],
      "summary": "Replace LIKE '%' || #{name} with LIKE #{name} || '%'"
    },
    "applicable": true,
    "status": "ready",
    "appliedAt": null,
    "verificationResult": {
      "xmlValid": true,
      "originalSnippetFound": true,
      "contextMatch": true
    }
  }
]
```

**补丁文件**: `result/patches/UserMapper.xml.patch`

```diff
--- a/UserMapper.xml
+++ b/UserMapper.xml
@@ -10,7 +10,7 @@
     SELECT * FROM users
     <where>
       <condition expr="name LIKE '%' || #{name}"/>
+      <condition expr="status = 1"/>
     </where>
   </select>
```

### 8.3 验证报告输出

**文件**: `result/verification_report.json`

```json
{
  "runId": "20260324-143052",
  "timestamp": "2026-03-24T14:30:52Z",
  "summary": {
    "totalProposals": 5,
    "patchable": 3,
    "nonPatchable": 2,
    "verified": 5,
    "failed": 0
  },
  "verificationResults": [
    {
      "proposalId": "prop_001",
      "sqlKey": "com.example.UserMapper.search:branch:0",
      "verified": true,
      "method": "RESULT_SET_COMPARISON",
      "rowCountMatch": true,
      "sampleMatchRate": 1.0,
      "executionTimeMs": {
        "baseline": 150.5,
        "rewritten": 5.2
      }
    }
  ],
  "nonPatchableProposals": [
    {
      "proposalId": "prop_004",
      "reason": "SEMANTIC_MISMATCH",
      "details": "Result sets differ: baseline returns 150 rows, rewritten returns 148 rows",
      "requiresManualReview": true
    }
  ]
}
```

---

## 9. 与其他方案的对比

### 9.1 方案对比

| 方案 | 描述 | 优点 | 缺点 | 选择原因 |
|------|------|------|------|----------|
| **朴素 Diff** | 逐行比较完整 SQL | 简单 | 大片段修改失败、语义丢失 | ❌ 无法处理复杂优化 |
| **完整 SQL 替换** | 替换整个 SQL 语句 | 简单 | 无法处理动态 SQL、容易破坏 XML 结构 | ❌ 风险太高 |
| **操作日志 + Rollback** | 记录每个修改操作 | 可逆 | 存储开销大 | ❌ 不需要回滚 |
| **结构化动作 (本方案)** | 记录 operation/xpath/snippet | 精确、可追溯 | 需要修改 Optimize 输出格式 | ✅ 精确、可验证 |

### 9.2 为什么选择结构化动作

1. **精确性**: 每个动作都有明确的 xpath 和 snippet 对应，不会出现位置错误
2. **可验证性**: 通过 originalSnippet 和 rewrittenSnippet 的对比，可以验证动作正确性
3. **可追溯性**: 每个动作都记录了 issue、confidence、rationale，方便审核
4. **语义验证**: 通过 RESULT_SET_COMPARISON 确保优化正确性
5. **灵活性**: 四种操作类型覆盖所有优化场景

### 9.3 潜在风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| xpath 生成错误 | 低 | 高 | 添加 originalSnippet 验证机制 |
| 语义验证不准确 | 中 | 高 | 阈值可配置，低匹配率标记人工审核 |
| 多分支处理复杂 | 中 | 中 | 分支选择逻辑独立模块化 |
| 动态 SQL 结构不确定 | 低 | 高 | 使用更宽松的 xpath 匹配 |

---

## 10. 实现计划

### 10.1 阶段划分

| 阶段 | 任务 | 预计工时 |
|------|------|----------|
| **Phase 1** | 数据结构定义 + 契约 | 2h |
| **Phase 2** | Optimize 输出改造成动作序列 | 4h |
| **Phase 3** | Result Patch 引擎实现 | 6h |
| **Phase 4** | 语义验证模块 | 4h |
| **Phase 5** | 测试与调试 | 4h |

### 10.2 关键里程碑

1. **M1**: 定义 `PatchAction`、`ActionSequence` 数据结构
2. **M2**: Optimize 阶段输出改为 `actionSequence`
3. **M3**: Result 阶段能够读取并应用动作序列
4. **M4**: 语义验证模块集成
5. **M5**: 端到端测试通过

---

## 11. 附录

### 11.1 XPath 在 MyBatis XML 中的特殊考虑

MyBatis XML 有一些动态 SQL 标签，需要特殊处理：

```xml
<!-- 动态 SQL 结构示例 -->
<select id="search">
  <where>
    <if test="name != null">
      name LIKE #{name}
    </if>
    <if test="status != null">
      AND status = #{status}
    </if>
  </where>
</select>
```

**XPath 策略**:

| 场景 | XPath 策略 | 示例 |
|------|-----------|------|
| 静态元素 | 精确匹配 | `/mapper/select[@id='search']/where` |
| 动态元素 | 使用条件 | `/mapper/select[@id='search']/where/if[@test='name != null']` |
| 嵌套内容 | 使用 text() | `/mapper/select[@id='search']/where/if[@test='name != null']/text()` |

### 11.2 动作冲突检测

当多个动作作用于同一区域时，需要检测冲突：

```python
def detect_action_conflicts(actions: List[PatchAction]) -> List[Conflict]:
    """检测动作冲突"""
    conflicts = []
    
    # 按 xpath 分组
    xpath_groups = group_by_xpath(actions)
    
    for xpath, group_actions in xpath_groups.items():
        if len(group_actions) > 1:
            # 检查是否有冲突的操作
            types = [a.operationType for a in group_actions]
            
            # REPLACE + REMOVE = 冲突
            if 'REPLACE' in types and 'REMOVE' in types:
                conflicts.append(Conflict(xpath, group_actions, "REPLACE_REMOVE_CONFLICT"))
                
            # 多个 ADD = 可能需要合并
            if types.count('ADD') > 1:
                conflicts.append(Conflict(xpath, group_actions, "MULTIPLE_ADD"))
    
    return conflicts
```

### 11.3 验证方法配置

```yaml
# sqlopt.yml
optimize:
  semantic_verification:
    enabled: true
    method: RESULT_SET_COMPARISON  # RESULT_SET_COMPARISON, EXECUTION_PLAN_COMPARISON, SEMANTIC_EQUIVALENCE_CHECK
    thresholds:
      row_count_tolerance: 0
      sample_match_rate_threshold: 1.0
      execution_time_tolerance_ms: 1000
    fallback:
      enabled: true
      method: EXECUTION_PLAN_COMPARISON
```

---

## 12. 设计决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-03-24 | 使用 4 种操作类型 (REPLACE/ADD/REMOVE/WRAP) | 覆盖所有 SQL 优化场景 |
| 2026-03-24 | 语义验证使用 RESULT_SET_COMPARISON | 最准确，不依赖执行计划 |
| 2026-03-24 | Optimize 输出动作序列而非完整 SQL | 精确追踪变化，便于验证 |
| 2026-03-24 | 每个动作记录 originalSnippet 和 rewrittenSnippet | 便于验证和调试 |

---

*文档版本: v1.0 - 完整设计*
