# SQL 优化完整流程演示结果

**Run ID**: run_8c1719c37556  
**执行时间**: 2026-03-10  
**数据库**: MySQL (100.101.41.123:3306/sql_optimizer_test)

---

## 执行摘要

| 阶段 | 状态 | SQL 数量 |
|------|------|----------|
| preflight | ✅ DONE | - |
| scan | ✅ DONE | 92 |
| optimize | ✅ DONE | 92 |
| validate | ✅ DONE | 92 |
| patch_generate | ✅ DONE | 92 |
| report | ✅ DONE | - |

---

## 目标 SQL 详情

**SQL ID**: `com.test.mapper.UserMapper.testWhereMultipleIf#v12`

### 原始 SQL

```xml
<select id="testWhereMultipleIf" resultType="User">
    SELECT * FROM users
    <where>
        <if test="name != null">AND name LIKE CONCAT('%', #{name}, '%')</if>
        <if test="email != null">AND email LIKE CONCAT('%', #{email}, '%')</if>
        <if test="status != null">AND status = #{status}</if>
        <if test="type != null">AND type = #{type}</if>
    </where>
</select>
```

### 解析后的 SQL

```sql
SELECT * FROM users AND name LIKE CONCAT('%', #{name}, '%') AND email LIKE CONCAT('%', #{email}, '%') AND status = #{status} AND type = #{type}
```

---

## 发现的问题

| 代码 | 严重性 | 描述 |
|------|--------|------|
| SELECT_STAR | warn | 避免 SELECT *，应明确指定列 |
| FULL_SCAN_RISK | warn | 无 WHERE 过滤 - 可能导致全表扫描 |
| NO_LIMIT | warn | SELECT 无 LIMIT 可能返回大量结果 |

---

## 优化建议

### LLM 建议

```sql
SELECT id FROM users AND name LIKE CONCAT('%', #{name}, '%') AND email LIKE CONCAT('%', #{email}, '%') AND status = #{status} AND type = #{type}
```

**重写策略**: projection_minimization (列投影最小化)  
**语义风险**: low  
**置信度**: medium

---

## 验证结果

| 检查项 | 结果 |
|--------|------|
| 状态 | PASS |
| 语义等价 | ✅ MATCH (行数一致) |
| 安全检查 | ✅ dollar_substitution 已移除 |
| 语义风险 | low |

### 数据库证据

- **表**: users
- **估计行数**: 29
- **索引**: PRIMARY (id)
- **查询成本**: 3.15
- **执行计划**: Table scan on users

---

## 补丁信息

| 属性 | 值 |
|------|-----|
| 选中的候选 | llm:c1 |
| 语义等价 | 是 |
| 可应用性 | MEDIUM (70分) |
| 交付就绪度 | READY |

### 重写物化

- **模式**: UNMATERIALIZABLE
- **原因**: 存在动态子树 (DYNAMIC_SUBTREE_PRESENT)
- **说明**: 动态 SQL 无法安全地物化为模板

---

## 总结

对于 `testWhereMultipleIf` (4个IF条件，16个分支场景):

1. **扫描**: ✅ 成功解析 MyBatis 动态 SQL
2. **优化**: ✅ LLM 生成了优化建议 (SELECT id 替代 SELECT *)
3. **验证**: ✅ 语义等价验证通过
4. **补丁**: ⚠️ 由于存在动态 SQL 片段，补丁不可物化到模板

### 优化效果

- **优化前**: `SELECT *` (7列)
- **优化后**: `SELECT id` (1列)
- **预估提升**: 减少网络传输和内存占用

---

## 完整报告

详见: `runs/run_8c1719c37556/report.md`
