# 参数替换优化设计文档

**日期**: 2026-04-06
**状态**: Draft

---

## 1. 目标

优化 Recognition 阶段的参数替换功能，解决以下问题：
1. `${}` 字符串替换未处理
2. VARCHAR 类型未显式处理
3. 嵌套属性匹配不完善
4. 样本值过于简单
5. LIKE 参数值缺少通配符

## 2. 背景

`_resolve_mybatis_params_for_explain()` 函数已支持：
- `#{}` 预编译参数替换
- 热门值 (top-1) 优先替换
- Fallback 到静态样本值

但存在上述优化点需要改进。

## 3. 设计方案

### 3.1 改动点

| 文件 | 改动 |
|------|------|
| `recognition/stage.py` | 优化 `_resolve_mybatis_params_for_explain()` 函数 |

### 3.2 优化 1: `${}` 字符串替换处理

**问题**: `${}` 原样保留会导致 EXPLAIN 报错

**方案**: 替换为合理的占位值

```python
def _resolve_dollar_params(sql: str) -> str:
    """处理 ${} 字符串替换"""
    def replacer(match):
        var_name = match.group(1)
        # 根据变量名推断类型
        var_lower = var_name.lower()
        if any(k in var_lower for k in ["name", "title", "desc"]):
            return "'table_name'"
        if any(k in var_lower for k in ["id", "num"]):
            return "1"
        return "'value'"

    return re.sub(r"\$\{([^}]+)\}", replacer, sql)
```

### 3.3 优化 2: VARCHAR 类型处理

**问题**: 当前没有显式处理 VARCHAR

**方案**: 添加 VARCHAR/CHAR/TEXT 到类型检测

```python
# 在 get_sample_value 中添加
if any(t in col_type for t in ["VARCHAR", "CHAR", "TEXT", "NVARCHAR"]):
    return "'test'"
```

### 3.4 优化 3: 嵌套属性匹配

**问题**: `#{user.id}` 只取 `user` 部分

**方案**: 增强匹配逻辑

```python
# 在 get_column_type_from_context 中
# 不仅匹配 param_lower, param_snake
# 还尝试匹配原始参数名和常见变体
```

### 3.5 优化 4: 样本值智能选择

**问题**: 数字永远用 `1`

**方案**: 根据参数名场景选择

```python
# 新增参数名匹配规则
if any(k in param_lower for k in ["limit", "page_size"]):
    return "100"
if any(k in param_lower for k in ["offset", "page"]):
    return "0"
if any(k in param_lower for k in ["id", "num"]):
    return "1"
```

### 3.6 优化 5: LIKE 参数值

**问题**: `#{keyword}` 在 LIKE 中应该是 `'%keyword%'`

**方案**: 检测 LIKE 上下文，加通配符

```python
def _detect_like_context(sql_lower: str, param_name: str) -> bool:
    """检测参数是否在 LIKE 上下文中"""
    # 匹配 like '%#{param}' 或 like #{param}%
    pattern = rf"like\s+['\"%]?#\{{{re.escape(param_name)}\}}?['\"%]?"
    return bool(re.search(pattern, sql_lower, re.IGNORECASE))

def _add_wildcard(value: str) -> str:
    """为 LIKE 查询添加通配符"""
    return f"%{value}%"
```

## 4. 数据流

```
原始 SQL
    ↓
处理 ${} (新增)
    ↓
处理 #{} (增强)
    ├── 热门值替换 (已有)
    ├── LIKE 上下文检测 (新增)
    ├── 类型推断 (增强)
    └── 参数名推断 (增强)
    ↓
可执行 SQL for EXPLAIN
```

## 5. 向后兼容

- 不改变现有热门值替换逻辑
- 增强而非替换现有功能
- 保持原有函数签名

## 6. 错误处理

| 场景 | 处理 |
|------|------|
| `${}` 处理失败 | 记录 debug 日志，跳过 |
| LIKE 上下文检测失败 | 保持原值 |
| 类型推断失败 | 使用参数名推断 |

## 7. 测试场景

| 场景 | 预期 |
|------|------|
| `${table_name}` | → `'table_name'` |
| VARCHAR 类型参数 | → `'test'` |
| `#{user.id}` 嵌套属性 | 正确匹配 `user` 列 |
| `limit` 参数 | → `100` (非 1) |
| LIKE 中的 `#{keyword}` | → `'%keyword%'` |