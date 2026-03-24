# 分支展开能力概览

## 1. MyBatis 动态SQL标签体系

MyBatis XML 支持以下动态SQL标签：

| 标签 | 描述 | 组合特性 |
|------|------|----------|
| `<if>` | 条件判断 | 独立，可嵌套 |
| `<choose>/<when>/<otherwise>` | 多选一 | 互斥，只能选一个 |
| `<where>` | 动态WHERE | 自动处理AND/OR |
| `<set>` | 动态SET | 用于UPDATE |
| `<trim>` | 前后缀处理 | 可替代where/set |
| `<foreach>` | 循环遍历 | 列表展开 |
| `<bind>` | 变量绑定 | 创建变量 |

---

## 2. 当前实现现状

### 2.1 已实现能力

| 能力 | 状态 | 说明 |
|------|------|------|
| `<if>`展开 | ✅ 已实现 | 每个if生成一个分支 + default |
| 无动态标签SQL | ✅ 已实现 | 直接返回清理后的SQL |
| `<where>`清理 | ✅ 已实现 | 移除多余标签 |
| `<choose>`处理 | ❌ 未实现 | 检测到但未展开 |
| `<when>`处理 | ❌ 未实现 | 未实现 |
| `<otherwise>`处理 | ❌ 未实现 | 未实现 |
| 嵌套`<if>` | ⚠️ 有bug | 内层被当作文本直接拼接 |
| `<foreach>`展开 | ❌ 未实现 | 未实现 |
| 条件互斥分析 | ❌ 未实现 | choose结构应互斥 |
| 死代码识别 | ❌ 未实现 | 未实现 |

### 2.2 当前展开逻辑

```python
# 当前逻辑（简化）
def expand_branches(sql_text):
    if 没有动态标签:
        return [清理后的SQL]
    
    # 只处理了if标签
    branches = []
    for idx, if_match in enumerate(if标签列表):
        branch = 展开该if + 保留其他内容
        branches.append(branch)
    
    branches.append(default分支)  # 不含任何if的版本
    return branches
```

### 2.3 当前问题

1. **choose/when/otherwise完全没处理**
2. **嵌套if处理错误**（直接拼接而非递归展开）
3. **没有条件互斥分析**（choose结构应互斥，不需要展开成所有组合）
4. **没有死代码识别**（如`test="1=0"`永假条件）
5. **没有等价分支合并**（相同SQL可能多次出现）

---

## 3. 目标能力体系

### 3.1 标签展开能力

| 标签 | 展开逻辑 | 示例 |
|------|----------|------|
| `<if>` | 每个if生成T/F组合 | `test="isVIP"` → isVIP分支 + default分支 |
| `<choose>` | 所有when + otherwise互斥展开 | 只能选一个生效 |
| `<when>` | 作为choose的候选分支 | 互斥，不组合 |
| `<otherwise>` | choose的最后备选 | 互斥 |
| `<where>` | 自动处理前后AND/OR | 清理冗余逻辑 |
| `<set>` | 动态SET处理 | 用于UPDATE |
| `<trim>` | 前后缀裁剪 | 自定义前后缀 |
| `<foreach>` | 列表展开 | `IN (1,2,3)` 展开 |

### 3.2 辅助能力

| 能力 | 描述 | 阶段 |
|------|------|------|
| 死代码识别 | 检测永真/永假条件 | Parse |
| 条件互斥分析 | choose结构只保留一个生效分支 | Parse |
| 嵌套条件展开 | 正确处理嵌套if的递归展开 | Parse |
| 等价分支合并 | 文本相同的SQL只保留一个 | Parse |
| 采样压缩 | 组合爆炸时按策略采样 | Parse |
| 血缘追踪 | 记录分支展开路径 | Parse |

---

## 4. 各标签展开详解

### 4.1 `<if>` 标签展开

**语法**：
```xml
<if test="condition">SQL片段</if>
```

**展开逻辑**：
```
条件为true → 包含该SQL片段
条件为false → 不包含该SQL片段
```

**示例**：
```xml
<if test="isVIP">AND is_vip = 1</if>
<if test="hasCoupon">AND coupon_id IS NOT NULL</if>
```

**展开结果**：
| 组合 | isVIP | hasCoupon | 展开SQL |
|------|-------|-----------|---------|
| 1 | T | T | `... AND is_vip = 1 AND coupon_id IS NOT NULL` |
| 2 | T | F | `... AND is_vip = 1` |
| 3 | F | T | `... AND coupon_id IS NOT NULL` |
| 4 | F | F | `...` |

**N个独立if** → **2^N种组合**

---

### 4.2 `<choose>/<when>/<otherwise>` 展开

**语法**：
```xml
<choose>
  <when test="condition1">SQL片段1</when>
  <when test="condition2">SQL片段2</when>
  <when test="condition3">SQL片段3</when>
  <otherwise>默认SQL片段</otherwise>
</choose>
```

**展开逻辑**：
- `<choose>`结构是**互斥**的，同一时刻只能有一个when生效
- 如果condition1为true，只生效SQL片段1
- 如果所有when都不满足，生效otherwise

**示例**：
```xml
<choose>
  <when test="type == 'A'">AND type = 'A'</when>
  <when test="type == 'B'">AND type = 'B'</when>
  <when test="type == 'C'">AND type = 'C'</when>
  <otherwise>AND type IN ('A','B','C')</otherwise>
</choose>
```

**展开结果**：
| 分支 | 条件 | 展开SQL |
|------|------|---------|
| when_A | type=='A' | `... AND type = 'A'` |
| when_B | type=='B' | `... AND type = 'B'` |
| when_C | type=='C' | `... AND type = 'C'` |
| otherwise | 其他 | `... AND type IN ('A','B','C')` |

**注意**：choose结构展开后是**4个互斥分支**，不是2^4=16个组合

---

### 4.3 嵌套 `<if>` 展开

**问题场景**：
```xml
<if test="isVIP">
  <if test="hasCoupon">
    AND vip_coupon = 1
  </if>
</if>
```

**错误处理（当前）**：
```python
# 当前直接拼接，内层if被当作文本
expanded = base_sql + "内层if内容作为文本" + after_sql
```

**正确处理（目标）**：
```
isVIP=true, hasCoupon=true → 包含内层片段
isVIP=true, hasCoupon=false → 不包含内层片段
isVIP=false → 整个块不生效，内层不用判断
```

**递归展开逻辑**：
```python
def expand_nested_if(sql_text, depth=0):
    if 没有嵌套if:
        return [当前层展开结果]
    
    # 找到外层if
    outer_if = find_outer_if(sql_text)
    for outer_val in [T, F]:
        if outer_val == F:
            # 外层false，内层不用展开
            yield base_sql + after_sql
        else:
            # 外层true，继续展开内层
            inner_content = extract_inner_if(outer_if)
            yield from expand_nested_if(inner_content, depth+1)
```

---

### 4.4 `<foreach>` 展开

**语法**：
```xml
<foreach collection="ids" item="id" open="(" separator="," close=")">
  #{id}
</foreach>
```

**示例**：
```xml
SELECT * FROM orders WHERE id IN
<foreach collection="orderIds" item="id" open="(" separator="," close=")">
  #{id}
</foreach>
```

**展开逻辑**：
- 列表有N个元素 → 展开成N个值
- 如`orderIds=[1,2,3]` → `IN (1, 2, 3)`

**常见场景**：
```xml
<!-- 批量插入 -->
INSERT INTO orders (id, name) VALUES
<foreach collection="list" item="item" separator=",">
  (#{item.id}, #{item.name})
</foreach>
```

---

### 4.5 `<where>` 标签

**作用**：自动处理WHERE子句中的多余AND/OR

**示例**：
```xml
<where>
  <if test="status != null">AND status = #{status}</if>
  <if test="name != null">AND name = #{name}</if>
</where>
```

**效果**：
- 如果只有status条件 → `WHERE status = ?`
- 如果只有name条件 → `WHERE name = ?`
- 如果都没有 → 无WHERE子句
- 自动去除多余的AND

---

### 4.6 `<set>` 标签

**作用**：动态SET子句，用于UPDATE

**示例**：
```xml
<set>
  <if test="name != null">name = #{name},</if>
  <if test="status != null">status = #{status},</if>
</set>
```

**效果**：
- 自动处理最后一个逗号
- 只会包含非null的字段

---

## 5. 组合场景

### 5.1 if + choose 组合

```xml
<if test="isVIP">
  <choose>
    <when test="type == 'A'">...A...</when>
    <when test="type == 'B'">...B...</when>
  </choose>
</if>
```

**展开逻辑**：
```
isVIP=F → 不进入choose，使用外层default
isVIP=T, type='A' → choose的when_A
isVIP=T, type='B' → choose的when_B
```

---

### 5.2 多层嵌套

```xml
<choose>
  <when test="level == 1">
    <if test="isVIP">...VIP...</if>
    <if test="hasCoupon">...Coupon...</if>
  </when>
  <when test="level == 2">
    ...
  </when>
</choose>
```

**展开**：先按choose互斥展开，再按各分支内的if展开

---

## 6. 标签支持优先级

| 优先级 | 标签 | 状态 | 备注 |
|--------|------|------|------|
| P0 | `<if>` | ✅ 已有 | 基础，必须 |
| P0 | `<choose>/<when>/<otherwise>` | 🔧 待开发 | 常用，需实现互斥展开 |
| P0 | 嵌套`<if>`修复 | 🔧 待开发 | 当前有bug |
| P1 | `<where>`清理 | 🔧 待开发 | 自动处理AND/OR |
| P1 | `<set>`清理 | 🔧 待开发 | UPDATE用 |
| P2 | `<foreach>`展开 | 🔧 待规划 | 需明确定义展开策略 |
| P2 | `<trim>`处理 | 🔧 待规划 | 前后缀处理 |
| P3 | `<bind>`处理 | 🔧 待规划 | 变量绑定 |

---

## 7. 总结

### 当前能力
- ✅ `<if>`基础展开（有bug）
- ❌ `<choose>`未实现
- ❌ 嵌套if处理错误
- ❌ 辅助策略全无

### 目标能力
- ✅ `<if>`正确展开
- ✅ `<choose>`互斥展开
- ✅ 嵌套if递归展开
- ✅ 死代码识别
- ✅ 条件互斥分析
- ✅ 等价分支合并
- 🔧 采样压缩
- 🔧 `<foreach>`展开

---

*文档版本：v1.0*
*更新日期：2026-03-24*
