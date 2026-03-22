# 已知问题 (Known Issues)

## 2026-03-22

### 1. MyBatis Include 片段展开问题

**严重程度**: 高

**问题描述**:
`<include refid="..."/>` 标签展开不正确，导致生成的 SQL 无效。

**复现步骤**:
```bash
cd D:\01_workspace\test\mybatis-test
sqlopt.exe --verbose run --config sqlopt.yaml --to-stage init --run-id test
```

**预期行为**:
```sql
SELECT id, order_no, user_id, status, amount, created_at, updated_at
FROM orders o
```

**实际行为**:
```sql
SELECT 
        ,
        ,
           
FROM orders o
```

**影响阶段**:
- init 阶段: SQL 单元的 `sql` 字段包含未展开的 include 或错误的空白
- parse 阶段: 分支继承自 init 的无效 SQL
- recognition 阶段: EXPLAIN 执行失败（语法错误）
- optimize 阶段: 可能生成错误的优化建议

**根因分析**:
`python/sqlopt/application/v9_stages/init.py` 中的 `_render_logical_text` 函数在处理 `<include>` 标签时：
1. 可能没有正确递归展开片段
2. 空白处理可能导致列名之间产生多余逗号和换行

**涉及文件**:
- `python/sqlopt/application/v9_stages/init.py`
- `python/sqlopt/shared/xml_utils.py` (如果有)

**相关 XML 文件**:
- `tests/real/mybatis-test/src/main/resources/mapper/OrderMapper.xml`
- `tests/real/mybatis-test/src/main/resources/mapper/CommonMapper.xml`

**可能的修复方向**:
1. 检查 `_render_logical_text` 中的递归展开逻辑
2. 验证 `fragments` 字典是否正确包含所有片段
3. 修复空白处理逻辑

---

### 2. 列名不匹配 (user_type vs type)

**严重程度**: 中

**问题描述**:
MyBatis XML 中使用的列名与数据库实际列名不一致。

**示例**:
- XML 使用: `type`
- 数据库列: `user_type`

**影响**:
- `UserMapper.xml` 中的 `testChooseWithMultipleIf` 等 SQL 可能失败

---

### 3. 动态 SQL 参数展开问题

**严重程度**: 中

**问题描述**:
含有 `${}` 动态表达式的 SQL 在 EXPLAIN 时会失败。

**示例**:
```sql
ORDER BY ${sortColumn} ${sortOrder}
```

**影响**:
- recognition 阶段的 EXPLAIN 执行会报错

---

## 历史问题

暂无

